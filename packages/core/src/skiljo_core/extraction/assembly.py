from typing import Any, Union

from pydantic import ValidationError

from skiljo_core import config
from skiljo_core.extraction.citation_validator import validate_citation
from skiljo_core.llm.base import LLMClient
from skiljo_core.schemas.rule_schema import (
    Condition,
    DeterministicRule,
    HumanOnlyRule,
    LLMAssistedRule,
    Predicate,
)
from skiljo_core.schemas.skill_schema import DecisionZones, Skill

_AnyRule = Union[DeterministicRule, LLMAssistedRule, HumanOnlyRule]


def _collect_condition_fields(condition: Condition) -> list[str]:
    fields: list[str] = []
    for clause_list in (condition.all, condition.any):
        if clause_list is None:
            continue
        for item in clause_list:
            inner = item.root
            if isinstance(inner, Predicate):
                fields.append(inner.field)
            else:
                fields.extend(_collect_condition_fields(inner))
    return fields


def _collect_fields(decision_zones: DecisionZones) -> list[str]:
    fields: list[str] = []
    all_rules: list[_AnyRule] = [
        *decision_zones.deterministic,
        *decision_zones.llm_assisted,
        *decision_zones.human_only,
    ]
    for rule in all_rules:
        fields.extend(_collect_condition_fields(rule.condition))
    return sorted(set(fields))


def _guess_input_type(field_name: str) -> str:
    lowered = field_name.lower()
    if any(token in lowered for token in ("amount", "price", "fee", "rate", "percent")):
        return "number"
    if any(token in lowered for token in ("days", "count", "version", "tokens")):
        return "integer"
    if any(token in lowered for token in ("flags", "tags", "items")):
        return "array"
    return "string"


def _build_inputs(fields: list[str]) -> list[dict[str, str]]:
    return [{"name": field, "type": _guess_input_type(field)} for field in fields]


def _validate_skill_citations(skill: Skill, source_text: str) -> None:
    rules: list[_AnyRule] = [
        *skill.decision_zones.deterministic,
        *skill.decision_zones.llm_assisted,
        *skill.decision_zones.human_only,
    ]
    for rule in rules:
        validate_citation(rule.citation, source_text)


def assemble_skill(
    llm_client: LLMClient,
    skill_name: str,
    trigger: str,
    decision_zones: DecisionZones,
    source_text: str,
    model: str = config.DEFAULT_MODEL,
) -> Skill:
    fields = _collect_fields(decision_zones)
    candidate: dict[str, Any] = {
        "skill_name": skill_name,
        "version": 1,
        "trigger": trigger,
        "inputs": _build_inputs(fields),
        "decision_zones": decision_zones.model_dump(mode="json"),
    }
    try:
        skill = Skill.model_validate(candidate)
    except ValidationError as exc:
        repair_prompt = (
            "The following draft Skill spec failed JSON Schema validation.\n\n"
            f"Draft:\n{candidate}\n\n"
            f"Validation error:\n{exc}\n\n"
            "Return a corrected Skill spec that fixes this specific violation without changing anything else."
        )
        response = llm_client.generate_structured(
            prompt=repair_prompt,
            schema=Skill,
            model=model,
            prompt_version="assembly_repair_v1",
        )
        skill = response.data

    _validate_skill_citations(skill, source_text)
    return skill
