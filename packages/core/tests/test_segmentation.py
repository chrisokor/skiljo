from skiljo_core.testing import FakeLLMClient

from skiljo_core.extraction.segmentation import Segment, SegmentationResult, segment_policy


def test_segment_policy_returns_fake_response_segments() -> None:
    fake_client = FakeLLMClient(
        [
            SegmentationResult(
                segments=[
                    Segment(segment_type="thresholds", text="Refunds under $100 within 30 days are approved."),
                    Segment(segment_type="exceptions", text="Goodwill exceptions may be granted by support leads."),
                ]
            )
        ]
    )

    segments = segment_policy(fake_client, policy_text="(full policy text)")

    assert len(segments) == 2
    assert segments[0].segment_type == "thresholds"
    assert segments[1].segment_type == "exceptions"
    assert len(fake_client.calls) == 1
    assert fake_client.calls[0]["prompt_version"] == "segmentation_v1"
