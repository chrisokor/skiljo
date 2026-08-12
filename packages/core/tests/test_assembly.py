from skiljo_core.testing import FakeLLMClient, TEST_CITATION

from skiljo_core.extraction.assembly import assemble_skill
from skiljo_core.schemas.rule_schema import Condition, ConditionOrPredicate, DeterministicRule, Operator, Predicate
from skiljo_core.schemas.skill_schema import DecisionZones, Input, Skill, Type


def _decision_zones() -> DecisionZones:
    rule = DeterministicRule(
        condition=Condition(
            all=[
                ConditionOrPredicate(root=Predicate(field="refund_amount", op=Operator.lt, value=100)),
                ConditionOrPredicate(root=Predicate(field="purchase_days_ago", op=Operator.lte, value=30)),
            ]
        ),
        action="approve_refund",
        citation=TEST_CITATION,
    )
    return DecisionZones(deterministic=[rule], llm_assisted=[], human_only=[])


def test_assemble_skill_succeeds_without_llm_call_when_valid() -> None:
    fake_client = FakeLLMClient([])  # no LLM call expected on the happy path

    skill = assemble_skill(
        fake_client,
        skill_name="process_refund_request",
        trigger="customer_requests_refund",
        decision_zones=_decision_zones(),
    )

    assert skill.skill_name == "process_refund_request"
    by_name = {i.name: i.type.value for i in skill.inputs}
    assert by_name == {"refund_amount": "number", "purchase_days_ago": "integer"}
    assert len(fake_client.calls) == 0


def test_assemble_skill_repairs_invalid_skill_name_via_llm() -> None:
    repaired = Skill(
        skill_name="process_refund_request",
        version=1,
        trigger="customer_requests_refund",
        inputs=[Input(name="refund_amount", type=Type.number)],
        decision_zones=_decision_zones(),
    )
    fake_client = FakeLLMClient([repaired])

    skill = assemble_skill(
        fake_client,
        skill_name="ProcessRefundRequest",  # invalid: uppercase violates skill_name's pattern
        trigger="customer_requests_refund",
        decision_zones=_decision_zones(),
    )

    assert skill.skill_name == "process_refund_request"
    assert len(fake_client.calls) == 1
    assert fake_client.calls[0]["prompt_version"] == "assembly_repair_v1"


def test_assemble_skill_handles_nested_conditions_and_array_fields() -> None:
    rule = DeterministicRule(
        condition=Condition(
            any=[
                ConditionOrPredicate(root=Predicate(field="fraud_flags", op=Operator.not_empty, value=None)),
                ConditionOrPredicate(root=Condition(all=[ConditionOrPredicate(root=Predicate(field="refund_amount", op=Operator.gt, value=1000))])),
            ]
        ),
        action="escalate_review",
        citation=TEST_CITATION,
    )
    decision_zones = DecisionZones(deterministic=[rule], llm_assisted=[], human_only=[])
    fake_client = FakeLLMClient([])

    skill = assemble_skill(
        fake_client,
        skill_name="process_refund_request",
        trigger="customer_requests_refund",
        decision_zones=decision_zones,
    )

    by_name = {i.name: i.type.value for i in skill.inputs}
    assert by_name["fraud_flags"] == "array"
    assert by_name["refund_amount"] == "number"
