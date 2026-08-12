from skiljo_core.extraction.zones import (
    ZoneClassification,
    classify_rules,
    classify_zone,
)
from skiljo_core.schemas.rule_schema import (
    Citation,
    Condition,
    ConditionOrPredicate,
    DeterministicRule,
    Operator,
    Predicate,
    Span,
)
from skiljo_core.testing import FakeLLMClient


def _rule(action: str) -> DeterministicRule:
    return DeterministicRule(
        condition=Condition(
            all=[
                ConditionOrPredicate(
                    root=Predicate(
                        field="refund_amount", op=Operator.lt, value=100
                    )
                )
            ]
        ),
        action=action,
        citation=Citation(span=Span(start=0, end=1), quoted_text="r"),
    )


def test_classify_zone_returns_fake_response_zone() -> None:
    fake_client = FakeLLMClient([ZoneClassification(zone="deterministic")])

    zone = classify_zone(fake_client, _rule("approve_refund"))

    assert zone == "deterministic"
    assert fake_client.calls[0]["prompt_version"] == "zone_classification_v1"


def test_classify_rules_buckets_into_decision_zones() -> None:
    fake_client = FakeLLMClient(
        [
            ZoneClassification(zone="deterministic"),
            ZoneClassification(zone="llm_assisted"),
            ZoneClassification(zone="human_only"),
        ]
    )
    rules = [
        _rule("approve_refund"),
        _rule("goodwill_exception"),
        _rule("escalate_fraud_dispute"),
    ]

    decision_zones = classify_rules(fake_client, rules)

    assert len(decision_zones.deterministic) == 1
    assert decision_zones.deterministic[0].action == "approve_refund"
    assert len(decision_zones.llm_assisted) == 1
    assert decision_zones.llm_assisted[0].action == "goodwill_exception"
    assert decision_zones.llm_assisted[0].requires_human_approval is True
    assert decision_zones.llm_assisted[0].citation.quoted_text == "r"
    assert len(decision_zones.human_only) == 1
    assert decision_zones.human_only[0].action == "escalate_fraud_dispute"
    assert decision_zones.human_only[0].citation.quoted_text == "r"
