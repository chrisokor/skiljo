from skiljo_core.testing import FakeLLMClient

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
