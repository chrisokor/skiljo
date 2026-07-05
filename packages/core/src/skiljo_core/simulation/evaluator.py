from typing import Any

from skiljo_core.schemas.rule_schema import Condition, ConditionOrPredicate, Operator, Predicate


def evaluate_predicate(predicate: Predicate, ticket: dict[str, Any]) -> bool:
    v = predicate.value
    fv = ticket.get(predicate.field)
    op = predicate.op

    if op == Operator.eq:
        return fv == v
    if op == Operator.neq:
        return fv != v
    if op == Operator.lt:
        return fv is not None and fv < v
    if op == Operator.lte:
        return fv is not None and fv <= v
    if op == Operator.gt:
        return fv is not None and fv > v
    if op == Operator.gte:
        return fv is not None and fv >= v
    if op == Operator.in_:
        return fv in (v if v is not None else [])
    if op == Operator.not_in:
        return fv not in (v if v is not None else [])
    if op == Operator.contains:
        if isinstance(fv, str):
            return str(v) in fv
        if isinstance(fv, list):
            return v in fv
        return False
    if op == Operator.empty:
        return fv is None or fv == [] or fv == ""
    if op == Operator.not_empty:
        return fv is not None and fv != [] and fv != ""
    raise ValueError(f"Unknown operator: {op}")


def evaluate_condition_or_predicate(cop: ConditionOrPredicate, ticket: dict[str, Any]) -> bool:
    if isinstance(cop.root, Predicate):
        return evaluate_predicate(cop.root, ticket)
    return evaluate_condition(cop.root, ticket)


def evaluate_condition(condition: Condition, ticket: dict[str, Any]) -> bool:
    if condition.all is not None:
        return all(evaluate_condition_or_predicate(c, ticket) for c in condition.all)
    if condition.any is not None:
        return any(evaluate_condition_or_predicate(c, ticket) for c in condition.any)
    return False
