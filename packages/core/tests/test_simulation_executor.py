import uuid

from skiljo_core.schemas.rule_schema import (
    Condition,
    ConditionOrPredicate,
    DeterministicRule,
    LLMAssistedRule,
    Operator,
    Predicate,
)
from skiljo_core.schemas.simulation_report_schema import Zone
from skiljo_core.schemas.skill_schema import DecisionZones, Input, Skill, Type
from skiljo_core.schemas.ticket_schema import Ticket
from skiljo_core.simulation.executor import LLMRecommendation, simulate_ticket
from skiljo_core.testing import FakeLLMClient


def _ticket(
    refund_amount: float = 50.0,
    purchase_days_ago: int = 10,
    customer_segment: str = "standard",
    refund_reason: str = "product_defect",
    ground_truth: str = "approve_refund",
) -> Ticket:
    return Ticket(
        ticket_id=uuid.uuid4(),
        refund_amount=refund_amount,
        purchase_days_ago=purchase_days_ago,
        customer_segment=customer_segment,
        fraud_flags=[],
        refund_reason=refund_reason,
        ground_truth_decision=ground_truth,
    )


def _skill_with_deterministic_rule() -> Skill:
    return Skill(
        skill_name="process_refund_request",
        version=1,
        trigger="customer_requests_refund",
        inputs=[Input(name="refund_amount", type=Type.number)],
        decision_zones=DecisionZones(
            deterministic=[
                DeterministicRule(
                    condition=Condition(
                        all=[ConditionOrPredicate(root=Predicate(field="refund_amount", op=Operator.lte, value=100.0))]
                    ),
                    action="approve_refund",
                )
            ],
            llm_assisted=[],
            human_only=[],
        ),
    )


def _skill_with_llm_assisted_rule() -> Skill:
    return Skill(
        skill_name="process_refund_request",
        version=1,
        trigger="customer_requests_refund",
        inputs=[Input(name="refund_reason", type=Type.string)],
        decision_zones=DecisionZones(
            deterministic=[],
            llm_assisted=[
                LLMAssistedRule(
                    condition=Condition(
                        all=[ConditionOrPredicate(root=Predicate(field="refund_reason", op=Operator.contains, value="goodwill"))]
                    ),
                    action="draft_recommendation",
                    requires_human_approval=True,
                )
            ],
            human_only=[],
        ),
    )


def _skill_empty() -> Skill:
    return Skill(
        skill_name="process_refund_request",
        version=1,
        trigger="customer_requests_refund",
        inputs=[],
        decision_zones=DecisionZones(deterministic=[], llm_assisted=[], human_only=[]),
    )


def test_deterministic_rule_match_returns_correct_decision() -> None:
    skill = _skill_with_deterministic_rule()
    ticket = _ticket(refund_amount=50.0, ground_truth="approve_refund")
    result = simulate_ticket(skill, ticket, FakeLLMClient([]))
    assert result.decision == "approve_refund"
    assert result.zone == Zone.deterministic
    assert result.matched_human_decision is True


def test_deterministic_rule_no_match_falls_through() -> None:
    skill = _skill_with_deterministic_rule()
    ticket = _ticket(refund_amount=200.0, ground_truth="escalate_to_human")
    result = simulate_ticket(skill, ticket, FakeLLMClient([]))
    assert result.zone == Zone.human_only
    assert result.decision == "escalate_to_human"


def test_llm_assisted_rule_invokes_llm_and_uses_recommendation() -> None:
    skill = _skill_with_llm_assisted_rule()
    ticket = _ticket(refund_reason="goodwill request", ground_truth="approve_refund")
    fake = FakeLLMClient([LLMRecommendation(action="approve_refund", reasoning="Customer is long-term.")])
    result = simulate_ticket(skill, ticket, fake)
    assert result.zone == Zone.llm_assisted
    assert result.decision == "approve_refund"
    assert result.reasoning == "Customer is long-term."
    assert len(fake.calls) == 1


def test_no_rule_match_escalates_to_human_only() -> None:
    skill = _skill_empty()
    ticket = _ticket(ground_truth="escalate_to_human")
    result = simulate_ticket(skill, ticket, FakeLLMClient([]))
    assert result.zone == Zone.human_only
    assert result.decision == "escalate_to_human"


def test_matched_human_decision_false_when_wrong_decision() -> None:
    skill = _skill_with_deterministic_rule()
    ticket = _ticket(refund_amount=50.0, ground_truth="deny_refund")
    result = simulate_ticket(skill, ticket, FakeLLMClient([]))
    assert result.matched_human_decision is False
