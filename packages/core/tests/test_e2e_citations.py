"""End-to-end citation coverage for the extraction pipeline."""

from skiljo_core.extraction.citation_validator import validate_citation
from skiljo_core.extraction.pipeline import run_extraction_pipeline
from skiljo_core.extraction.rules import CandidateRuleList
from skiljo_core.extraction.segmentation import Segment, SegmentationResult
from skiljo_core.extraction.zones import ZoneClassification
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


def _candidate_rule(
    field: str, action: str, segment_text: str, quoted_text: str
) -> DeterministicRule:
    start = segment_text.index(quoted_text)
    return DeterministicRule(
        condition=Condition(
            all=[
                ConditionOrPredicate(
                    root=Predicate(field=field, op=Operator.eq, value=True)
                )
            ]
        ),
        action=action,
        citation=Citation(
            span=Span(start=start, end=start + len(quoted_text)),
            quoted_text=quoted_text,
        ),
    )


def test_pipeline_resolves_citations_for_rules_in_every_decision_zone() -> None:
    """Section-relative citations survive all four passes as document offsets."""
    eligibility = "Refunds are approved within 30 days of purchase."
    exceptions = "Digital products are non-refundable."
    approvals = "Goodwill refunds require support lead review."
    policy_text = "\n\n".join([eligibility, exceptions, approvals])
    fake_client = FakeLLMClient(
        [
            SegmentationResult(
                segments=[
                    Segment(segment_type="eligibility", text=eligibility),
                    Segment(segment_type="exceptions", text=exceptions),
                    Segment(segment_type="approvals", text=approvals),
                ]
            ),
            CandidateRuleList(
                rules=[
                    _candidate_rule(
                        "within_refund_window",
                        "approve_refund",
                        eligibility,
                        "within 30 days",
                    )
                ]
            ),
            CandidateRuleList(
                rules=[
                    _candidate_rule(
                        "is_digital_product",
                        "deny_refund",
                        exceptions,
                        "Digital products are non-refundable.",
                    )
                ]
            ),
            CandidateRuleList(
                rules=[
                    _candidate_rule(
                        "goodwill_requested",
                        "review_goodwill_refund",
                        approvals,
                        "Goodwill refunds require support lead review.",
                    )
                ]
            ),
            ZoneClassification(zone="deterministic"),
            ZoneClassification(zone="llm_assisted"),
            ZoneClassification(zone="human_only"),
        ]
    )

    skill = run_extraction_pipeline(
        fake_client,
        policy_text=policy_text,
        skill_name="process_refund_request",
        trigger="customer_requests_refund",
    )

    rules = [
        *skill.decision_zones.deterministic,
        *skill.decision_zones.llm_assisted,
        *skill.decision_zones.human_only,
    ]
    assert len(rules) == 3
    assert len(fake_client.calls) == 7

    for rule in rules:
        citation = rule.citation
        assert validate_citation(citation, policy_text) is True
        assert policy_text[citation.span.start : citation.span.end] == citation.quoted_text
