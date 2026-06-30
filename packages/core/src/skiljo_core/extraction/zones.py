from typing import Literal

from pydantic import BaseModel

from skiljo_core import config
from skiljo_core.llm.base import LLMClient
from skiljo_core.schemas.rule_schema import (
    DeterministicRule,
    HumanOnlyRule,
    LLMAssistedRule,
)
from skiljo_core.schemas.skill_schema import DecisionZones

ZONE_CLASSIFICATION_PROMPT_V1 = """Classify the following policy rule into exactly one decision zone:

- deterministic: mechanically evaluable from structured ticket data alone
  (numeric thresholds, exact matches, simple boolean conditions).
- llm_assisted: requires interpreting ambiguous or subjective criteria
  (e.g. "goodwill", "reasonable", "anomalous use") before a decision can be made,
  but is not so high-stakes that it requires a human to decide.
- human_only: too high-stakes, legally sensitive, or judgment-heavy to automate
  even with LLM assistance (e.g. fraud disputes, legal threats, large amounts).

Rule condition: {condition_json}
Rule action: {action}
"""


class ZoneClassification(BaseModel):
    zone: Literal["deterministic", "llm_assisted", "human_only"]


def classify_zone(
    llm_client: LLMClient,
    rule: DeterministicRule,
    model: str = config.DEFAULT_MODEL,
) -> str:
    prompt = ZONE_CLASSIFICATION_PROMPT_V1.format(
        condition_json=rule.condition.model_dump_json(),
        action=rule.action,
    )
    response = llm_client.generate_structured(
        prompt=prompt,
        schema=ZoneClassification,
        model=model,
        prompt_version="zone_classification_v1",
    )
    return response.data.zone


def classify_rules(
    llm_client: LLMClient,
    rules: list[DeterministicRule],
    model: str = config.DEFAULT_MODEL,
) -> DecisionZones:
    deterministic: list[DeterministicRule] = []
    llm_assisted: list[LLMAssistedRule] = []
    human_only: list[HumanOnlyRule] = []
    for rule in rules:
        zone = classify_zone(llm_client, rule, model=model)
        if zone == "deterministic":
            deterministic.append(rule)
        elif zone == "llm_assisted":
            llm_assisted.append(
                LLMAssistedRule(
                    condition=rule.condition,
                    action=rule.action,
                    requires_human_approval=True,
                )
            )
        else:
            human_only.append(
                HumanOnlyRule(condition=rule.condition, action=rule.action)
            )
    return DecisionZones(
        deterministic=deterministic,
        llm_assisted=llm_assisted,
        human_only=human_only,
    )
