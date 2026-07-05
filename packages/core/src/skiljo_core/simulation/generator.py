from __future__ import annotations

import random
import uuid
from typing import Any

from pydantic import BaseModel

from skiljo_core.schemas.rule_schema import Condition
from skiljo_core.schemas.skill_schema import Skill
from skiljo_core.schemas.ticket_schema import Ticket
from skiljo_core.simulation.evaluator import evaluate_condition


class DivergenceSpec(BaseModel):
    rule_id: str
    condition: Condition
    base_decision: str
    shadow_decision: str
    frequency: float  # 0.0–1.0


class TicketFieldRanges(BaseModel):
    refund_amount_min: float = 0.0
    refund_amount_max: float = 500.0
    purchase_days_min: int = 0
    purchase_days_max: int = 90
    customer_segments: list[str] = ["standard", "premium", "vip"]
    segment_weights: list[float] = [0.6, 0.3, 0.1]
    refund_reasons: list[str] = ["product_defect", "not_as_described", "changed_mind", "goodwill"]
    fraud_flag_probability: float = 0.1


def _shadow_ground_truth(
    ticket_dict: dict[str, Any],
    base_skill: Skill,
    divergences: list[DivergenceSpec],
    rng: random.Random,
) -> str:
    # Check divergences first (highest priority)
    for div in divergences:
        if evaluate_condition(div.condition, ticket_dict) and rng.random() < div.frequency:
            return div.shadow_decision

    # Fall back to base skill deterministic rules
    for det_rule in base_skill.decision_zones.deterministic:
        if evaluate_condition(det_rule.condition, ticket_dict):
            return det_rule.action

    # Fall back to LLM-assisted rules
    for llm_rule in base_skill.decision_zones.llm_assisted:
        if evaluate_condition(llm_rule.condition, ticket_dict):
            return "requires_human_review"

    # Final fallback
    return "escalate_to_human"


def generate_ticket_batch(
    base_skill: Skill,
    divergences: list[DivergenceSpec],
    count: int = 100,
    seed: int | None = 42,
    ranges: TicketFieldRanges | None = None,
) -> list[Ticket]:
    rng = random.Random(seed)
    r = ranges or TicketFieldRanges()
    tickets = []

    for _ in range(count):
        refund_amount = round(rng.uniform(r.refund_amount_min, r.refund_amount_max), 2)
        purchase_days_ago = rng.randint(r.purchase_days_min, r.purchase_days_max)
        customer_segment = rng.choices(r.customer_segments, weights=r.segment_weights, k=1)[0]
        fraud_flags = ["suspicious_activity"] if rng.random() < r.fraud_flag_probability else []
        refund_reason = rng.choice(r.refund_reasons)

        ticket_dict: dict[str, Any] = {
            "refund_amount": refund_amount,
            "purchase_days_ago": purchase_days_ago,
            "customer_segment": customer_segment,
            "fraud_flags": fraud_flags,
            "refund_reason": refund_reason,
        }
        ground_truth = _shadow_ground_truth(ticket_dict, base_skill, divergences, rng)

        tickets.append(
            Ticket(
                ticket_id=uuid.UUID(int=rng.getrandbits(128)),
                ground_truth_decision=ground_truth,
                **ticket_dict,
            )
        )
    return tickets
