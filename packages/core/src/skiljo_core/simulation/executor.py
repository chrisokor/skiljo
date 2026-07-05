from typing import cast

from pydantic import BaseModel

from skiljo_core import config
from skiljo_core.llm.base import LLMClient
from skiljo_core.schemas.rule_schema import DeterministicRule, HumanOnlyRule, LLMAssistedRule
from skiljo_core.schemas.simulation_report_schema import Result, Zone
from skiljo_core.schemas.skill_schema import Skill
from skiljo_core.schemas.ticket_schema import Ticket
from skiljo_core.simulation.evaluator import evaluate_condition


class LLMRecommendation(BaseModel):
    action: str
    reasoning: str


def simulate_ticket(
    skill: Skill,
    ticket: Ticket,
    llm_client: LLMClient,
    model: str = config.DEFAULT_MODEL,
) -> Result:
    ticket_dict = ticket.model_dump(mode="json")

    # 1. Deterministic zone: first matching rule wins
    for rule in skill.decision_zones.deterministic:
        det_rule = cast(DeterministicRule, rule)
        if evaluate_condition(det_rule.condition, ticket_dict):
            return Result(
                ticket_id=ticket.ticket_id,
                decision=det_rule.action,
                zone=Zone.deterministic,
                matched_human_decision=det_rule.action == ticket.ground_truth_decision,
            )

    # 2. LLM-assisted zone
    for rule in skill.decision_zones.llm_assisted:  # type: ignore[assignment]
        llm_rule = cast(LLMAssistedRule, rule)
        if evaluate_condition(llm_rule.condition, ticket_dict):
            prompt = (
                f"You are evaluating a refund or credit request.\n\n"
                f"Policy rule: {llm_rule.action}\n"
                f"Matched condition: {llm_rule.condition.model_dump()}\n"
                f"Ticket data: {ticket_dict}\n\n"
                "Based on the ticket context and this policy rule, provide a recommendation "
                "with a specific action and a brief reasoning."
            )
            resp = llm_client.generate_structured(
                prompt=prompt,
                schema=LLMRecommendation,
                model=model,
                prompt_version="llm_assisted_zone_v1",
            )
            return Result(
                ticket_id=ticket.ticket_id,
                decision=resp.data.action,
                zone=Zone.llm_assisted,
                matched_human_decision=resp.data.action == ticket.ground_truth_decision,
                reasoning=resp.data.reasoning,
            )

    # 3. Human-only zone
    for rule in skill.decision_zones.human_only:  # type: ignore[assignment]
        human_rule = cast(HumanOnlyRule, rule)
        if evaluate_condition(human_rule.condition, ticket_dict):
            return Result(
                ticket_id=ticket.ticket_id,
                decision=human_rule.action,
                zone=Zone.human_only,
                matched_human_decision=human_rule.action == ticket.ground_truth_decision,
            )

    # Default: no rule matched → escalate
    return Result(
        ticket_id=ticket.ticket_id,
        decision="escalate_to_human",
        zone=Zone.human_only,
        matched_human_decision="escalate_to_human" == ticket.ground_truth_decision,
    )
