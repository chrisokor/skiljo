from skiljo_core.testing import FakeLLMClient, TEST_CITATION

from skiljo_core.extraction.pipeline import run_extraction_pipeline
from skiljo_core.extraction.rules import CandidateRuleList
from skiljo_core.extraction.segmentation import Segment, SegmentationResult
from skiljo_core.extraction.zones import ZoneClassification
from skiljo_core.schemas.rule_schema import Condition, ConditionOrPredicate, DeterministicRule, Operator, Predicate


def test_pipeline_runs_all_four_passes_and_produces_schema_valid_skill() -> None:
    fake_client = FakeLLMClient(
        [
            SegmentationResult(
                segments=[
                    Segment(segment_type="thresholds", text="Refunds under $100 within 30 days are approved.")
                ]
            ),
            CandidateRuleList(
                rules=[
                    DeterministicRule(
                        condition=Condition(all=[ConditionOrPredicate(root=Predicate(field="refund_amount", op=Operator.lt, value=100))]),
                        action="approve_refund",
                        citation=TEST_CITATION,
                    )
                ]
            ),
            ZoneClassification(zone="deterministic"),
        ]
    )

    skill = run_extraction_pipeline(
        fake_client,
        policy_text="Refunds under $100 within 30 days are approved.",
        skill_name="process_refund_request",
        trigger="customer_requests_refund",
    )

    assert skill.skill_name == "process_refund_request"
    assert len(skill.decision_zones.deterministic) == 1
    assert len(fake_client.calls) == 3  # segmentation, rule extraction, zone classification; assembly needs none


def test_pipeline_accumulates_rules_across_multiple_segments() -> None:
    fake_client = FakeLLMClient(
        [
            SegmentationResult(
                segments=[
                    Segment(segment_type="thresholds", text="Refunds under $100 within 30 days are approved."),
                    Segment(segment_type="exceptions", text="Goodwill exceptions may be granted by support leads."),
                ]
            ),
            CandidateRuleList(
                rules=[
                    DeterministicRule(
                        condition=Condition(all=[ConditionOrPredicate(root=Predicate(field="refund_amount", op=Operator.lt, value=100))]),
                        action="approve_refund",
                        citation=TEST_CITATION,
                    )
                ]
            ),
            CandidateRuleList(
                rules=[
                    DeterministicRule(
                        condition=Condition(all=[ConditionOrPredicate(root=Predicate(field="goodwill_requested", op=Operator.eq, value=True))]),
                        action="goodwill_exception",
                        citation=TEST_CITATION,
                    )
                ]
            ),
            ZoneClassification(zone="deterministic"),
            ZoneClassification(zone="llm_assisted"),
        ]
    )

    skill = run_extraction_pipeline(
        fake_client,
        policy_text="(full policy text)",
        skill_name="process_refund_request",
        trigger="customer_requests_refund",
    )

    assert len(skill.decision_zones.deterministic) == 1
    assert len(skill.decision_zones.llm_assisted) == 1
    assert len(fake_client.calls) == 5
