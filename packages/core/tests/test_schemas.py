import pytest
from pydantic import ValidationError

from skiljo_core.schemas import Citation, Rule, Span


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
