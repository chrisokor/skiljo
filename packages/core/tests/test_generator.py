import pytest

from skiljo_core.schemas.rule_schema import Condition, ConditionOrPredicate, Operator, Predicate
from skiljo_core.schemas.skill_schema import DecisionZones, Input, Skill, Type
from skiljo_core.schemas.rule_schema import DeterministicRule, LLMAssistedRule, HumanOnlyRule
from skiljo_core.simulation.generator import DivergenceSpec, generate_ticket_batch


def _base_skill() -> Skill:
    return Skill(
        skill_name="process_refund_request",
        version=1,
        trigger="customer_requests_refund",
        inputs=[
            Input(name="refund_amount", type=Type.number),
            Input(name="purchase_days_ago", type=Type.integer),
        ],
        decision_zones=DecisionZones(
            deterministic=[
                DeterministicRule(
                    condition=Condition(
                        all=[
                            ConditionOrPredicate(root=Predicate(field="refund_amount", op=Operator.lte, value=100.0)),
                            ConditionOrPredicate(root=Predicate(field="purchase_days_ago", op=Operator.lte, value=30)),
                        ]
                    ),
                    action="approve_refund",
                ),
                DeterministicRule(
                    condition=Condition(
                        all=[ConditionOrPredicate(root=Predicate(field="refund_amount", op=Operator.gt, value=500.0))]
                    ),
                    action="escalate_to_human",
                ),
            ],
            llm_assisted=[
                LLMAssistedRule(
                    condition=Condition(
                        all=[ConditionOrPredicate(root=Predicate(field="refund_reason", op=Operator.contains, value="goodwill"))]
                    ),
                    action="draft_recommendation",
                    requires_human_approval=True,
                )
            ],
            human_only=[
                HumanOnlyRule(
                    condition=Condition(
                        all=[ConditionOrPredicate(root=Predicate(field="refund_amount", op=Operator.gt, value=500.0))]
                    ),
                    action="escalate_to_finance",
                )
            ],
        ),
    )


def test_generate_ticket_batch_returns_correct_count() -> None:
    tickets = generate_ticket_batch(_base_skill(), divergences=[], count=50, seed=42)
    assert len(tickets) == 50


def test_generate_ticket_batch_all_have_required_fields() -> None:
    tickets = generate_ticket_batch(_base_skill(), divergences=[], count=20, seed=1)
    for t in tickets:
        assert t.ticket_id is not None
        assert isinstance(t.refund_amount, float)
        assert isinstance(t.purchase_days_ago, int)
        assert t.ground_truth_decision != ""


def test_generate_ticket_batch_is_reproducible() -> None:
    batch_a = generate_ticket_batch(_base_skill(), divergences=[], count=10, seed=99)
    batch_b = generate_ticket_batch(_base_skill(), divergences=[], count=10, seed=99)
    assert [str(t.ticket_id) for t in batch_a] == [str(t.ticket_id) for t in batch_b]
    assert [t.refund_amount for t in batch_a] == [t.refund_amount for t in batch_b]


def test_divergence_overrides_base_decision_at_expected_frequency() -> None:
    """VIP exception: customer_segment==vip AND refund_amount>100 → approve_refund at 100% frequency."""
    vip_exception = DivergenceSpec(
        rule_id="vip_exception",
        condition=Condition(
            all=[
                ConditionOrPredicate(root=Predicate(field="customer_segment", op=Operator.eq, value="vip")),
                ConditionOrPredicate(root=Predicate(field="refund_amount", op=Operator.gt, value=100.0)),
            ]
        ),
        base_decision="deny_refund",
        shadow_decision="approve_refund",
        frequency=1.0,
    )
    tickets = generate_ticket_batch(_base_skill(), divergences=[vip_exception], count=200, seed=7)
    vip_over_threshold = [
        t for t in tickets
        if t.customer_segment == "vip" and t.refund_amount > 100.0
    ]
    assert len(vip_over_threshold) > 0, "no VIP tickets generated; adjust seed or count"
    assert all(t.ground_truth_decision == "approve_refund" for t in vip_over_threshold)


def test_base_policy_applied_when_no_divergence_matches() -> None:
    """Tickets that match the base deterministic rule get the correct base decision."""
    tickets = generate_ticket_batch(_base_skill(), divergences=[], count=200, seed=3)
    eligible = [
        t for t in tickets
        if t.refund_amount <= 100.0 and t.purchase_days_ago <= 30
    ]
    assert len(eligible) > 0
    assert all(t.ground_truth_decision == "approve_refund" for t in eligible)


def test_planted_divergences_present_at_expected_rate() -> None:
    """50% frequency divergence should appear roughly 50% of the time in matching tickets."""
    near_threshold = DivergenceSpec(
        rule_id="near_threshold",
        condition=Condition(
            all=[
                ConditionOrPredicate(root=Predicate(field="refund_amount", op=Operator.gte, value=100.0)),
                ConditionOrPredicate(root=Predicate(field="refund_amount", op=Operator.lte, value=120.0)),
            ]
        ),
        base_decision="deny_refund",
        shadow_decision="approve_refund",
        frequency=0.5,
    )
    tickets = generate_ticket_batch(_base_skill(), divergences=[near_threshold], count=500, seed=0)
    matching = [t for t in tickets if 100.0 <= t.refund_amount <= 120.0]
    if len(matching) == 0:
        pytest.skip("no matching tickets in this batch; increase count")
    approved = [t for t in matching if t.ground_truth_decision == "approve_refund"]
    rate = len(approved) / len(matching)
    # With 500 tickets and 0.5 frequency, rate should be ~50% ± 20% (generous tolerance)
    assert 0.30 <= rate <= 0.70, f"expected ~50% divergence rate, got {rate:.2f}"
