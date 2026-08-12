import pytest
from pydantic import ValidationError

from skiljo_core.schemas import Citation, Rule, Span
from skiljo_core.schemas.rule_schema import (
    DeterministicRule,
    HumanOnlyRule,
    LLMAssistedRule,
)


def test_rule_with_citation() -> None:
    """A rule accepts a citation with a character span and source quote."""
    citation = Citation(
        span=Span(start=10, end=25),
        quoted_text="refund within 30",
    )
    rule = Rule(
        id="test-rule",
        decision_zone="deterministic",
        action="approve",
        condition={"field": "order_age", "op": "lte", "value": 30},
        citation=citation,
    )

    assert rule.citation.span.start == 10
    assert rule.citation.quoted_text == "refund within 30"


def test_rule_requires_citation() -> None:
    """A rule without source evidence is rejected."""
    with pytest.raises(ValidationError):
        Rule(
            id="test-rule",
            decision_zone="deterministic",
            action="approve",
            condition={"field": "order_age", "op": "lte", "value": 30},
        )


def test_span_rejects_negative_start() -> None:
    """A citation span cannot begin before the source document."""
    with pytest.raises(ValidationError):
        Span(start=-1, end=10)


def test_span_rejects_negative_end() -> None:
    """A citation span cannot end before the source document."""
    with pytest.raises(ValidationError):
        Span(start=0, end=-1)


@pytest.mark.parametrize(
    ("rule_model", "extra_fields"),
    [
        (DeterministicRule, {}),
        (LLMAssistedRule, {"requires_human_approval": True}),
        (HumanOnlyRule, {}),
    ],
)
def test_decision_zone_rule_requires_and_retains_citation(
    rule_model: type[DeterministicRule | LLMAssistedRule | HumanOnlyRule],
    extra_fields: dict[str, bool],
) -> None:
    """Each stored decision-zone rule requires and retains source evidence."""
    fields = {
        "condition": {"all": [{"field": "order_age", "op": "lte", "value": 30}]},
        "action": "approve",
        **extra_fields,
    }
    citation = Citation(span=Span(start=10, end=25), quoted_text="refund within 30")

    with pytest.raises(ValidationError):
        rule_model(**fields)

    rule = rule_model(citation=citation, **fields)

    assert rule.citation == citation
