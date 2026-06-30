from typing import cast

from skiljo_core.testing import FakeLLMClient

from skiljo_core.extraction.rules import CandidateRuleList, extract_rules
from skiljo_core.extraction.segmentation import Segment
from skiljo_core.schemas.rule_schema import Condition, ConditionOrPredicate, DeterministicRule, Operator, Predicate


def test_extract_rules_returns_expected_condition_structure() -> None:
    fake_client = FakeLLMClient(
        [
            CandidateRuleList(
                rules=[
                    DeterministicRule(
                        condition=Condition(
                            all=[
                                ConditionOrPredicate(root=Predicate(field="refund_amount", op=Operator.lt, value=100)),
                                ConditionOrPredicate(root=Predicate(field="purchase_days_ago", op=Operator.lte, value=30)),
                            ]
                        ),
                        action="approve_refund",
                    )
                ]
            )
        ]
    )
    segment = Segment(
        segment_type="thresholds",
        text="Refunds under $100 within 30 days of purchase are automatically approved.",
    )

    rules = extract_rules(fake_client, segment)

    assert len(rules) == 1
    condition = rules[0].condition
    all_conditions = cast(list[ConditionOrPredicate], condition.all)
    assert len(all_conditions) == 2
    first_predicate = cast(Predicate, all_conditions[0].root)
    second_predicate = cast(Predicate, all_conditions[1].root)
    assert first_predicate.field == "refund_amount"
    assert first_predicate.op == Operator.lt
    assert second_predicate.field == "purchase_days_ago"
    assert rules[0].action == "approve_refund"
    assert fake_client.calls[0]["prompt_version"] == "rule_extraction_v1"
