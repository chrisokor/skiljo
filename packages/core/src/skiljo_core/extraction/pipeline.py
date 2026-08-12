from skiljo_core import config
from skiljo_core.extraction.assembly import assemble_skill
from skiljo_core.extraction.citation_validator import validate_citation
from skiljo_core.extraction.rules import extract_rules
from skiljo_core.extraction.segmentation import segment_policy
from skiljo_core.extraction.zones import classify_rules
from skiljo_core.llm.base import LLMClient
from skiljo_core.schemas.rule_schema import DeterministicRule
from skiljo_core.schemas.skill_schema import Skill


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
        rules = extract_rules(llm_client, segment, model=model)
        for rule in rules:
            validate_citation(rule.citation, segment.text)
        candidate_rules.extend(rules)
    decision_zones = classify_rules(llm_client, candidate_rules, model=model)
    return assemble_skill(
        llm_client,
        skill_name=skill_name,
        trigger=trigger,
        decision_zones=decision_zones,
        model=model,
    )
