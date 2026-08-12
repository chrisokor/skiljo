from typing import cast

from skiljo_core.testing import FakeLLMClient, TEST_CITATION

from skiljo_core.extraction.rules import RULE_EXTRACTION_PROMPT_V1, CandidateRuleList, extract_rules
from skiljo_core.extraction.segmentation import Segment
from skiljo_core.schemas.rule_schema import Citation, Condition, ConditionOrPredicate, DeterministicRule, Operator, Predicate, Span


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
                        citation=TEST_CITATION,
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
    assert rules[0].citation == TEST_CITATION
    assert fake_client.calls[0]["prompt_version"] == "rule_extraction_v1"


def test_rule_extraction_prompt_requires_section_relative_citations() -> None:
    """Pass 2 tells the model to return exact, section-relative citations."""
    assert "character offsets" in RULE_EXTRACTION_PROMPT_V1
    assert "zero-based" in RULE_EXTRACTION_PROMPT_V1
    assert "SECTION TEXT" in RULE_EXTRACTION_PROMPT_V1
    assert "quoted_text" in RULE_EXTRACTION_PROMPT_V1
    assert "SECTION TEXT[start:end]" in RULE_EXTRACTION_PROMPT_V1


def test_extract_rules_preserves_section_relative_citation() -> None:
    section_text = "We offer refunds within 30 days of purchase."
    quoted_text = "refunds within 30 days"
    citation = Citation(
        span=Span(start=section_text.index(quoted_text), end=section_text.index(quoted_text) + len(quoted_text)),
        quoted_text=quoted_text,
    )
    fake_client = FakeLLMClient(
        [
            CandidateRuleList(
                rules=[
                    DeterministicRule(
                        condition=Condition(all=[ConditionOrPredicate(root=Predicate(field="days_since_purchase", op=Operator.lte, value=30))]),
                        action="refund",
                        citation=citation,
                    )
                ]
            )
        ]
    )

    rules = extract_rules(fake_client, Segment(segment_type="refund_policy", text=section_text))

    assert len(rules) == 1
    assert rules[0].citation.span.start == 9
    assert rules[0].citation.span.end == 31
    assert rules[0].citation.quoted_text == quoted_text
