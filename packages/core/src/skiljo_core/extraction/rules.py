from pydantic import BaseModel

from skiljo_core import config
from skiljo_core.extraction.segmentation import Segment
from skiljo_core.llm.base import LLMClient
from skiljo_core.schemas.rule_schema import DeterministicRule

RULE_EXTRACTION_PROMPT_V1 = """You are extracting structured rules from a "{segment_type}" section of a refund/credit/billing policy.

For each distinct rule you find, produce:
- a condition using the predicate language: "all"/"any" composition of {{field, op, value}} predicates, where op is one of eq, neq, lt, lte, gt, gte, in, not_in, contains, empty, not_empty
- an action describing what happens when the condition is met
- a citation with:
  - span: character offsets (start, end) pointing to the exact evidence in the source
  - quoted_text: a verbatim excerpt from the source document

CRITICAL: The span offsets must be zero-based character positions within the
SECTION TEXT provided below. `start` is where the evidence begins, `end` is
exclusive, and `quoted_text` must equal the exact substring
`SECTION TEXT[start:end]`.

SECTION TEXT:
---
{segment_text}
---
"""


class CandidateRuleList(BaseModel):
    rules: list[DeterministicRule]


def extract_rules(
    llm_client: LLMClient, segment: Segment, model: str = config.DEFAULT_MODEL
) -> list[DeterministicRule]:
    prompt = RULE_EXTRACTION_PROMPT_V1.format(segment_type=segment.segment_type, segment_text=segment.text)
    response = llm_client.generate_structured(
        prompt=prompt,
        schema=CandidateRuleList,
        model=model,
        prompt_version="rule_extraction_v1",
    )
    return response.data.rules
