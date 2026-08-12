import pytest

from skiljo_core.testing import FakeLLMClient

from skiljo_core.extraction.pipeline import run_extraction_pipeline
from skiljo_core.extraction.rules import CandidateRuleList
from skiljo_core.extraction.segmentation import Segment, SegmentationResult
from skiljo_core.extraction.zones import ZoneClassification
from skiljo_core.extraction.citation_validator import validate_citation
from skiljo_core.schemas.rule_schema import (
    Citation,
    Condition,
    ConditionOrPredicate,
    DeterministicRule,
    Operator,
    Predicate,
    Span,
)


def test_pipeline_runs_all_four_passes_and_produces_schema_valid_skill() -> None:
    segment_text = "Refunds under $100 within 30 days are approved."
    policy_text = f"Refund policy:\n{segment_text}"
    fake_client = FakeLLMClient(
        [
            SegmentationResult(
                segments=[
                    Segment(segment_type="thresholds", text=segment_text)
                ]
            ),
            CandidateRuleList(
                rules=[
                    DeterministicRule(
                        condition=Condition(all=[ConditionOrPredicate(root=Predicate(field="refund_amount", op=Operator.lt, value=100))]),
                        action="approve_refund",
                        citation=Citation(
                            span=Span(start=0, end=7), quoted_text="Refunds"
                        ),
                    )
                ]
            ),
            ZoneClassification(zone="deterministic"),
        ]
    )

    skill = run_extraction_pipeline(
        fake_client,
        policy_text=policy_text,
        skill_name="process_refund_request",
        trigger="customer_requests_refund",
    )

    assert skill.skill_name == "process_refund_request"
    assert len(skill.decision_zones.deterministic) == 1
    citation = skill.decision_zones.deterministic[0].citation
    assert citation.span.start == len("Refund policy:\n")
    assert validate_citation(citation, policy_text) is True
    assert len(fake_client.calls) == 3  # segmentation, rule extraction, zone classification; assembly needs none


def test_pipeline_accumulates_rules_across_multiple_segments() -> None:
    first_segment = "Refunds under $100 within 30 days are approved."
    second_segment = "Goodwill exceptions may be granted by support leads."
    fake_client = FakeLLMClient(
        [
            SegmentationResult(
                segments=[
                        Segment(segment_type="thresholds", text=first_segment),
                        Segment(segment_type="exceptions", text=second_segment),
                ]
            ),
            CandidateRuleList(
                rules=[
                    DeterministicRule(
                        condition=Condition(all=[ConditionOrPredicate(root=Predicate(field="refund_amount", op=Operator.lt, value=100))]),
                        action="approve_refund",
                        citation=Citation(
                            span=Span(start=0, end=7), quoted_text="Refunds"
                        ),
                    )
                ]
            ),
            CandidateRuleList(
                rules=[
                    DeterministicRule(
                        condition=Condition(all=[ConditionOrPredicate(root=Predicate(field="goodwill_requested", op=Operator.eq, value=True))]),
                        action="goodwill_exception",
                        citation=Citation(
                            span=Span(start=0, end=8), quoted_text="Goodwill"
                        ),
                    )
                ]
            ),
            ZoneClassification(zone="deterministic"),
            ZoneClassification(zone="llm_assisted"),
        ]
    )

    skill = run_extraction_pipeline(
        fake_client,
        policy_text=f"{first_segment}\n\n{second_segment}",
        skill_name="process_refund_request",
        trigger="customer_requests_refund",
    )

    assert len(skill.decision_zones.deterministic) == 1
    assert len(skill.decision_zones.llm_assisted) == 1
    assert skill.decision_zones.llm_assisted[0].citation.span.start == len(first_segment) + 2
    assert len(fake_client.calls) == 5


def test_pipeline_rejects_citation_not_valid_for_its_segment_text() -> None:
    segment_text = "Refunds under $100 within 30 days are approved."
    fake_client = FakeLLMClient(
        [
            SegmentationResult(
                segments=[Segment(segment_type="thresholds", text=segment_text)]
            ),
            CandidateRuleList(
                rules=[
                    DeterministicRule(
                        condition=Condition(
                            all=[
                                ConditionOrPredicate(
                                    root=Predicate(
                                        field="refund_amount", op=Operator.lt, value=100
                                    )
                                )
                            ]
                        ),
                        action="approve_refund",
                        citation=Citation(
                            span=Span(start=0, end=7), quoted_text="Credits"
                        ),
                    )
                ]
            ),
        ]
    )

    with pytest.raises(ValueError, match="no candidate rules with valid citations"):
        run_extraction_pipeline(
            fake_client,
            policy_text=segment_text,
            skill_name="process_refund_request",
            trigger="customer_requests_refund",
        )


def test_pipeline_drops_invalid_candidate_when_valid_rule_remains() -> None:
    segment_text = "Refunds under $100 are approved. Claims after 30 days are denied."
    fake_client = FakeLLMClient(
        [
            SegmentationResult(
                segments=[Segment(segment_type="thresholds", text=segment_text)]
            ),
            CandidateRuleList(
                rules=[
                    DeterministicRule(
                        condition=Condition(
                            all=[
                                ConditionOrPredicate(
                                    root=Predicate(
                                        field="refund_amount", op=Operator.lt, value=100
                                    )
                                )
                            ]
                        ),
                        action="approve_refund",
                        citation=Citation(
                            span=Span(start=0, end=7), quoted_text="Refunds"
                        ),
                    ),
                    DeterministicRule(
                        condition=Condition(
                            all=[
                                ConditionOrPredicate(
                                    root=Predicate(
                                        field="purchase_days_ago", op=Operator.gt, value=30
                                    )
                                )
                            ]
                        ),
                        action="deny_refund",
                        citation=Citation(
                            span=Span(start=33, end=39), quoted_text="Credits"
                        ),
                    ),
                ]
            ),
            ZoneClassification(zone="deterministic"),
        ]
    )

    skill = run_extraction_pipeline(
        fake_client,
        policy_text=segment_text,
        skill_name="process_refund_request",
        trigger="customer_requests_refund",
    )

    assert [rule.action for rule in skill.decision_zones.deterministic] == [
        "approve_refund"
    ]
    assert len(fake_client.calls) == 3


def test_pipeline_rejects_segment_text_not_resolvable_in_policy() -> None:
    fake_client = FakeLLMClient(
        [
            SegmentationResult(
                segments=[Segment(segment_type="thresholds", text="Segment text")]
            ),
            CandidateRuleList(rules=[]),
        ]
    )

    with pytest.raises(ValueError, match="could not be resolved"):
        run_extraction_pipeline(
            fake_client,
            policy_text="Different policy text",
            skill_name="process_refund_request",
            trigger="customer_requests_refund",
        )
