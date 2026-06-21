from pydantic import BaseModel

from skiljo_core import config
from skiljo_core.llm.base import LLMClient

SEGMENTATION_PROMPT_V1 = """You are analyzing a refund/credit/billing policy document to prepare it for rule extraction.

Segment the following policy text into logical sections. Use these segment types where applicable: eligibility, thresholds, approvals, exceptions, refund_methods, audit_requirements. If a section doesn't fit any of these, use "other".

For each segment, include the segment_type and the exact text of that section (do not paraphrase or summarize).

Policy text:
---
{policy_text}
---
"""


class Segment(BaseModel):
    segment_type: str
    text: str


class SegmentationResult(BaseModel):
    segments: list[Segment]


def segment_policy(
    llm_client: LLMClient, policy_text: str, model: str = config.DEFAULT_MODEL
) -> list[Segment]:
    prompt = SEGMENTATION_PROMPT_V1.format(policy_text=policy_text)
    response = llm_client.generate_structured(
        prompt=prompt,
        schema=SegmentationResult,
        model=model,
        prompt_version="segmentation_v1",
    )
    return response.data.segments
