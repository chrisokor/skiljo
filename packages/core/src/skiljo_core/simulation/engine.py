from __future__ import annotations

import asyncio
from uuid import UUID

from skiljo_core.llm.base import LLMClient
from skiljo_core.schemas.simulation_report_schema import Result, SimulationReport, Zone
from skiljo_core.schemas.skill_schema import Skill
from skiljo_core.schemas.ticket_schema import Ticket
from skiljo_core.simulation.executor import simulate_ticket

_ESCALATION_DECISIONS = frozenset({"escalate_to_human", "human_only", "requires_human_review"})


async def simulate_batch(
    skill: Skill,
    tickets: list[Ticket],
    llm_client: LLMClient,
    max_concurrency: int = 5,
) -> list[Result]:
    sem = asyncio.Semaphore(max_concurrency)

    async def run_one(ticket: Ticket) -> Result:
        async with sem:
            return await asyncio.to_thread(simulate_ticket, skill, ticket, llm_client)

    return list(await asyncio.gather(*[run_one(t) for t in tickets]))


def compute_report(
    skill_version_id: UUID,
    results: list[Result],
    tickets: list[Ticket],
) -> SimulationReport:
    if not results:
        return SimulationReport(
            skill_version_id=skill_version_id,
            match_rate=0.0,
            escalation_accuracy=1.0,
            total_tickets=0,
            results=[],
        )

    matched = sum(1 for r in results if r.matched_human_decision)
    match_rate = matched / len(results)

    escalated = [r for r in results if r.zone == Zone.human_only]
    ticket_map = {str(t.ticket_id): t for t in tickets}
    if escalated:
        correct = sum(
            1
            for r in escalated
            if (t := ticket_map.get(str(r.ticket_id))) is not None
            and t.ground_truth_decision in _ESCALATION_DECISIONS
        )
        escalation_accuracy = correct / len(escalated)
    else:
        escalation_accuracy = 1.0

    automation_candidates = sum(1 for r in results if r.zone == Zone.deterministic)

    return SimulationReport(
        skill_version_id=skill_version_id,
        match_rate=match_rate,
        escalation_accuracy=escalation_accuracy,
        total_tickets=len(results),
        automation_candidate_count=automation_candidates,
        results=results,
    )
