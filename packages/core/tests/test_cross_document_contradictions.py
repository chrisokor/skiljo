from skiljo_core.schemas.rule_schema import (
    Condition,
    ConditionOrPredicate,
    DeterministicRule,
    HumanOnlyRule,
    Operator,
    Predicate,
)
from skiljo_core.schemas.skill_schema import DecisionZones, Input, Skill, Type
from skiljo_core.simulation.cross_document import (
    ConflictCheck,
    DecisionSurfaceClassification,
    PolicyDocument,
    detect_cross_document_contradictions,
)
from skiljo_core.testing import FakeLLMClient, TEST_CITATION


def _condition() -> Condition:
    return Condition(
        all=[ConditionOrPredicate(root=Predicate(field="days_since_purchase", op=Operator.gt, value=0))]
    )


def _skill(action: str, zone: str = "deterministic") -> Skill:
    deterministic = [DeterministicRule(condition=_condition(), action=action, citation=TEST_CITATION)] if zone == "deterministic" else []
    human_only = [HumanOnlyRule(condition=_condition(), action=action, citation=TEST_CITATION)] if zone == "human_only" else []
    return Skill(
        skill_name="process_refund_request",
        version=1,
        trigger="customer_requests_refund",
        inputs=[Input(name="days_since_purchase", type=Type.integer)],
        decision_zones=DecisionZones(deterministic=deterministic, llm_assisted=[], human_only=human_only),
    )


def test_detects_refund_policy_conflict() -> None:
    """Shopify ToS ("no refunds") vs help-center ("case-by-case review")."""
    tos = PolicyDocument(policy_id="shopify_tos", skill=_skill("deny_refund_no_refunds_policy", "deterministic"))
    help_center = PolicyDocument(
        policy_id="shopify_help_center",
        skill=_skill("escalate_case_by_case_review", "human_only"),
    )

    fake_client = FakeLLMClient(
        [
            DecisionSurfaceClassification(decision_surface="refund_eligibility"),
            DecisionSurfaceClassification(decision_surface="refund_eligibility"),
            ConflictCheck(
                is_conflict=True,
                rationale="ToS forbids refunds outright while help center allows case-by-case review.",
            ),
        ]
    )

    contradictions = detect_cross_document_contradictions([tos, help_center], fake_client)

    assert len(contradictions) == 1
    contradiction = contradictions[0]
    assert contradiction.decision_surface == "refund_eligibility"
    assert {contradiction.policy_1, contradiction.policy_2} == {"shopify_tos", "shopify_help_center"}
    assert {contradiction.action_1, contradiction.action_2} == {
        "deny_refund_no_refunds_policy",
        "escalate_case_by_case_review",
    }
    assert contradiction.citation_1.policy_id == contradiction.policy_1
    assert contradiction.citation_2.policy_id == contradiction.policy_2
    assert "case-by-case" in contradiction.rationale


def test_aligns_rules_on_same_surface() -> None:
    """Rules on different decision surfaces are never compared for conflict."""
    doc_a = PolicyDocument(
        policy_id="policy_a",
        skill=Skill(
            skill_name="process_refund_request",
            version=1,
            trigger="customer_requests_refund",
            inputs=[Input(name="days_since_purchase", type=Type.integer)],
            decision_zones=DecisionZones(
                deterministic=[
                    DeterministicRule(condition=_condition(), action="deny_refund", citation=TEST_CITATION),
                    DeterministicRule(condition=_condition(), action="grant_sla_credit_10pct", citation=TEST_CITATION),
                ],
                llm_assisted=[],
                human_only=[],
            ),
        ),
    )
    doc_b = PolicyDocument(
        policy_id="policy_b",
        skill=Skill(
            skill_name="process_refund_request",
            version=1,
            trigger="customer_requests_refund",
            inputs=[Input(name="days_since_purchase", type=Type.integer)],
            decision_zones=DecisionZones(
                deterministic=[
                    DeterministicRule(condition=_condition(), action="approve_refund", citation=TEST_CITATION),
                    DeterministicRule(condition=_condition(), action="grant_sla_credit_30pct", citation=TEST_CITATION),
                ],
                llm_assisted=[],
                human_only=[],
            ),
        ),
    )

    fake_client = FakeLLMClient(
        [
            DecisionSurfaceClassification(decision_surface="refund_eligibility"),  # doc_a deny_refund
            DecisionSurfaceClassification(decision_surface="sla_credit"),  # doc_a grant_sla_credit_10pct
            DecisionSurfaceClassification(decision_surface="refund_eligibility"),  # doc_b approve_refund
            DecisionSurfaceClassification(decision_surface="sla_credit"),  # doc_b grant_sla_credit_30pct
            ConflictCheck(is_conflict=True, rationale="deny vs approve on refund_eligibility"),
            ConflictCheck(is_conflict=True, rationale="10pct vs 30pct on sla_credit"),
        ]
    )

    contradictions = detect_cross_document_contradictions([doc_a, doc_b], fake_client)

    # Exactly one conflict-check call per surface group (2 surfaces => 2 checks),
    # never a check across mismatched surfaces (which would be 4 pairs total).
    conflict_check_calls = [c for c in fake_client.calls if c["prompt_version"] == "cross_document_conflict_v1"]
    assert len(conflict_check_calls) == 2
    assert len(contradictions) == 2
    surfaces = {c.decision_surface for c in contradictions}
    assert surfaces == {"refund_eligibility", "sla_credit"}


def test_mechanical_check_skips_identical_actions_without_llm_call() -> None:
    """Identical actions can never be a conflict; the LLM is never asked."""
    doc_a = PolicyDocument(policy_id="policy_a", skill=_skill("approve_refund"))
    doc_b = PolicyDocument(policy_id="policy_b", skill=_skill("approve_refund"))

    fake_client = FakeLLMClient(
        [
            DecisionSurfaceClassification(decision_surface="refund_eligibility"),
            DecisionSurfaceClassification(decision_surface="refund_eligibility"),
        ]
    )

    contradictions = detect_cross_document_contradictions([doc_a, doc_b], fake_client)

    assert contradictions == []
    conflict_check_calls = [c for c in fake_client.calls if c["prompt_version"] == "cross_document_conflict_v1"]
    assert conflict_check_calls == []


def test_ignores_pairs_within_the_same_document() -> None:
    """Same-document divergence is a different problem; only cross-document pairs are checked."""
    doc = PolicyDocument(
        policy_id="single_policy",
        skill=Skill(
            skill_name="process_refund_request",
            version=1,
            trigger="customer_requests_refund",
            inputs=[Input(name="days_since_purchase", type=Type.integer)],
            decision_zones=DecisionZones(
                deterministic=[
                    DeterministicRule(condition=_condition(), action="deny_refund", citation=TEST_CITATION),
                    DeterministicRule(condition=_condition(), action="approve_refund", citation=TEST_CITATION),
                ],
                llm_assisted=[],
                human_only=[],
            ),
        ),
    )
    other = PolicyDocument(policy_id="other_policy", skill=_skill("grant_sla_credit"))

    fake_client = FakeLLMClient(
        [
            DecisionSurfaceClassification(decision_surface="refund_eligibility"),
            DecisionSurfaceClassification(decision_surface="refund_eligibility"),
            DecisionSurfaceClassification(decision_surface="sla_credit"),
        ]
    )

    contradictions = detect_cross_document_contradictions([doc, other], fake_client)

    # doc's two rules share a surface but are in the same document, so no
    # conflict check is issued for that pair; the other-doc pair is on a
    # different surface, so it isn't checked either.
    conflict_check_calls = [c for c in fake_client.calls if c["prompt_version"] == "cross_document_conflict_v1"]
    assert conflict_check_calls == []
    assert contradictions == []


def test_fewer_than_two_policies_returns_empty_without_llm_calls() -> None:
    doc = PolicyDocument(policy_id="only_policy", skill=_skill("approve_refund"))
    fake_client = FakeLLMClient([])

    assert detect_cross_document_contradictions([], fake_client) == []
    assert detect_cross_document_contradictions([doc], fake_client) == []
    assert fake_client.calls == []
