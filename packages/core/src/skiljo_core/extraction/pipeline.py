from skiljo_core import config
from skiljo_core.extraction.assembly import assemble_skill
from skiljo_core.extraction.citation_validator import validate_citation
from skiljo_core.extraction.rules import extract_rules
from skiljo_core.extraction.segmentation import segment_policy
from skiljo_core.extraction.zones import classify_rules
from skiljo_core.llm.base import LLMClient
from skiljo_core.schemas.rule_schema import Citation, DeterministicRule, Span
from skiljo_core.schemas.skill_schema import Skill


def _find_segment_start(segment_text: str, policy_text: str) -> int:
    if not segment_text:
        raise ValueError("Citation source segment text is empty")

    segment_start = policy_text.find(segment_text)
    if segment_start == -1 or segment_start != policy_text.rfind(segment_text):
        raise ValueError(
            "Citation source segment text could not be resolved uniquely in policy text"
        )
    return segment_start


def _to_document_relative_rule(
    rule: DeterministicRule, segment_text: str, segment_start: int, policy_text: str
) -> DeterministicRule:
    """Convert a section-relative citation to a policy-document-relative citation."""

    validate_citation(rule.citation, segment_text)
    citation = rule.citation
    document_citation = Citation(
        span=Span(
            start=segment_start + citation.span.start,
            end=segment_start + citation.span.end,
        ),
        quoted_text=citation.quoted_text,
    )
    validate_citation(document_citation, policy_text)
    return rule.model_copy(update={"citation": document_citation})


def run_extraction_pipeline(
    llm_client: LLMClient,
    policy_text: str,
    skill_name: str,
    trigger: str,
    model: str = config.DEFAULT_MODEL,
) -> Skill:
    segments = segment_policy(llm_client, policy_text, model=model)
    candidate_rules: list[DeterministicRule] = []
    for segment in segments:
        segment_start = _find_segment_start(segment.text, policy_text)
        rules = extract_rules(llm_client, segment, model=model)
        for rule in rules:
            candidate_rules.append(
                _to_document_relative_rule(
                    rule, segment.text, segment_start, policy_text
                )
            )
    decision_zones = classify_rules(llm_client, candidate_rules, model=model)
    return assemble_skill(
        llm_client,
        skill_name=skill_name,
        trigger=trigger,
        decision_zones=decision_zones,
        source_text=policy_text,
        model=model,
    )
