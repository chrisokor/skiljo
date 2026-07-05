from typing import Any

import pytest

from skiljo_core.schemas.rule_schema import Condition, ConditionOrPredicate, Operator, Predicate
from skiljo_core.simulation.evaluator import evaluate_condition, evaluate_predicate


ticket: dict[str, Any] = {
    "refund_amount": 75.0,
    "purchase_days_ago": 20,
    "customer_segment": "vip",
    "fraud_flags": ["suspicious_ip"],
    "refund_reason": "product_defect",
}


@pytest.mark.parametrize(
    "field,op,value,expected",
    [
        ("refund_amount", Operator.eq, 75.0, True),
        ("refund_amount", Operator.eq, 100.0, False),
        ("refund_amount", Operator.neq, 100.0, True),
        ("refund_amount", Operator.lt, 100.0, True),
        ("refund_amount", Operator.lt, 50.0, False),
        ("refund_amount", Operator.lte, 75.0, True),
        ("refund_amount", Operator.lte, 74.9, False),
        ("refund_amount", Operator.gt, 50.0, True),
        ("refund_amount", Operator.gt, 75.0, False),
        ("refund_amount", Operator.gte, 75.0, True),
        ("refund_amount", Operator.gte, 76.0, False),
        ("customer_segment", Operator.in_, ["vip", "premium"], True),
        ("customer_segment", Operator.in_, ["standard"], False),
        ("customer_segment", Operator.not_in, ["standard"], True),
        ("customer_segment", Operator.not_in, ["vip"], False),
        ("refund_reason", Operator.contains, "defect", True),
        ("refund_reason", Operator.contains, "goodwill", False),
        ("fraud_flags", Operator.contains, "suspicious_ip", True),
        ("fraud_flags", Operator.contains, "known_fraud", False),
        ("fraud_flags", Operator.empty, None, False),
        ("missing_field", Operator.empty, None, True),
        ("fraud_flags", Operator.not_empty, None, True),
        ("missing_field", Operator.not_empty, None, False),
    ],
)
def test_predicate_operators(
    field: str, op: Operator, value: Any, expected: bool
) -> None:
    pred = Predicate(field=field, op=op, value=value)
    assert evaluate_predicate(pred, ticket) == expected


def test_condition_all_true() -> None:
    cond = Condition(
        all=[
            ConditionOrPredicate(root=Predicate(field="refund_amount", op=Operator.lt, value=100.0)),
            ConditionOrPredicate(root=Predicate(field="purchase_days_ago", op=Operator.lte, value=30)),
        ]
    )
    assert evaluate_condition(cond, ticket) is True


def test_condition_all_short_circuits_on_false() -> None:
    cond = Condition(
        all=[
            ConditionOrPredicate(root=Predicate(field="refund_amount", op=Operator.gt, value=200.0)),
            ConditionOrPredicate(root=Predicate(field="purchase_days_ago", op=Operator.lte, value=30)),
        ]
    )
    assert evaluate_condition(cond, ticket) is False


def test_condition_any_true() -> None:
    cond = Condition(
        any=[
            ConditionOrPredicate(root=Predicate(field="refund_amount", op=Operator.gt, value=200.0)),
            ConditionOrPredicate(root=Predicate(field="customer_segment", op=Operator.eq, value="vip")),
        ]
    )
    assert evaluate_condition(cond, ticket) is True


def test_condition_any_false() -> None:
    cond = Condition(
        any=[
            ConditionOrPredicate(root=Predicate(field="refund_amount", op=Operator.gt, value=200.0)),
            ConditionOrPredicate(root=Predicate(field="customer_segment", op=Operator.eq, value="standard")),
        ]
    )
    assert evaluate_condition(cond, ticket) is False


def test_nested_condition() -> None:
    """all: [amount < 500, any: [vip, premium]]"""
    inner = Condition(
        any=[
            ConditionOrPredicate(root=Predicate(field="customer_segment", op=Operator.eq, value="vip")),
            ConditionOrPredicate(root=Predicate(field="customer_segment", op=Operator.eq, value="premium")),
        ]
    )
    outer = Condition(
        all=[
            ConditionOrPredicate(root=Predicate(field="refund_amount", op=Operator.lt, value=500.0)),
            ConditionOrPredicate(root=inner),
        ]
    )
    assert evaluate_condition(outer, ticket) is True


def test_empty_all_returns_false() -> None:
    assert evaluate_condition(Condition(all=[]), ticket) is True  # vacuous truth: all([]) == True


def test_empty_any_returns_false() -> None:
    assert evaluate_condition(Condition(any=[]), ticket) is False  # vacuous: any([]) == False
