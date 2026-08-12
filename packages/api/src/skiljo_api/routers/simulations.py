import asyncio
import os
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import HTMLResponse
from jinja2 import Environment, FileSystemLoader
from pydantic import BaseModel

from skiljo_api.dependencies import get_llm_client, verify_api_key
from skiljo_core.db.models import Job, SimulationResult, SimulationRun, SkillVersion
from skiljo_core.db.session import SessionLocal
from skiljo_core.llm.base import LLMClient
from skiljo_core.schemas.simulation_report_schema import (
    Contradiction as ReportContradiction,
    EstimatedFinancialImpact,
    SimulationReport,
)
from skiljo_core.schemas.skill_schema import Skill
from skiljo_core.schemas.ticket_schema import Ticket
from skiljo_core.simulation.contradictions import (
    Contradiction as DetectedContradiction,
    detect_contradictions,
)
from skiljo_core.simulation.cross_document import (
    CrossDocumentContradiction,
    PolicyDocument,
    detect_cross_document_contradictions,
)
from skiljo_core.simulation.engine import compute_report, simulate_batch

_TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "../templates")
_jinja_env = Environment(loader=FileSystemLoader(_TEMPLATES_DIR), autoescape=True)

router = APIRouter(dependencies=[Depends(verify_api_key)])


class SimulationRequest(BaseModel):
    skill_version_id: uuid.UUID
    tickets: list[dict[str, Any]]


class SimulationResponse(BaseModel):
    job_id: uuid.UUID
    status: str


def _report_contradictions(
    contradictions: list[DetectedContradiction],
) -> list[ReportContradiction]:
    """Convert detector output without inventing rule execution provenance.

    Simulation Result does not currently carry an executed rule identity. An
    action string can also come from an LLM recommendation or the default
    escalation path, so it is not sufficient evidence for a source citation.
    """
    return [
        ReportContradiction(
            cluster_key=contradiction.cluster_key,
            written_decision=contradiction.written_decision,
            observed_decision=contradiction.observed_decision,
            frequency=contradiction.frequency,
            ticket_count=contradiction.ticket_count,
            affected_ticket_ids=contradiction.affected_ticket_ids,
            citation=None,
            estimated_financial_impact=(
                EstimatedFinancialImpact(
                    divergent_ticket_count=contradiction.estimated_financial_impact.divergent_ticket_count,
                    average_refund_amount=contradiction.estimated_financial_impact.average_refund_amount,
                    estimated_impact_usd=contradiction.estimated_financial_impact.estimated_impact_usd,
                )
                if contradiction.estimated_financial_impact is not None
                else None
            ),
        )
        for contradiction in contradictions
    ]


def _run_simulation_job(
    job_id: uuid.UUID,
    sim_run_id: uuid.UUID,
    skill_version_id: uuid.UUID,
    tickets_raw: list[dict[str, Any]],
    llm_client: LLMClient,
) -> None:
    with SessionLocal() as session:
        job = session.get(Job, job_id)
        sim_run = session.get(SimulationRun, sim_run_id)
        if job is None or sim_run is None:
            return
        job.status = "running"
        job.started_at = datetime.now(UTC)
        sim_run.status = "running"
        sim_run.started_at = datetime.now(UTC)
        session.commit()

        try:
            sv = session.get(SkillVersion, skill_version_id)
            if sv is None:
                raise ValueError(f"SkillVersion {skill_version_id} not found")
            skill = Skill.model_validate(sv.spec)
            tickets = [Ticket.model_validate(t) for t in tickets_raw]

            # asyncio.run() creates a new event loop here because BackgroundTasks
            # executes this function in a sync thread pool (starlette's run_in_threadpool),
            # outside the main async event loop — calling await directly would fail.
            results = asyncio.run(simulate_batch(skill, tickets, llm_client))
            report = compute_report(skill_version_id, results, tickets)
            contradictions = detect_contradictions(results, tickets)
            report = report.model_copy(
                update={
                    "contradiction_count": len(contradictions),
                    "contradictions": _report_contradictions(contradictions),
                }
            )

            ticket_map = {str(t.ticket_id): t for t in tickets}
            for r in results:
                ticket = ticket_map.get(str(r.ticket_id))
                session.add(
                    SimulationResult(
                        run_id=sim_run_id,
                        ticket_id=r.ticket_id,
                        ticket_data=ticket.model_dump(mode="json") if ticket else {},
                        decision=r.decision,
                        zone=r.zone.value,
                        matched_human_decision=r.matched_human_decision,
                        reasoning=r.reasoning,
                    )
                )

            sim_run.status = "completed"
            sim_run.completed_at = datetime.now(UTC)
            sim_run.summary = report.model_dump(mode="json")
            job.status = "completed"
            job.result_ref = sim_run_id
            job.completed_at = datetime.now(UTC)
            session.commit()

        except Exception as exc:
            sim_run.status = "failed"
            job.status = "failed"
            job.error = str(exc)
            job.completed_at = datetime.now(UTC)
            session.commit()
            raise


@router.post("/simulations", status_code=202)
def create_simulation(
    request: SimulationRequest,
    background_tasks: BackgroundTasks,
    llm_client: LLMClient = Depends(get_llm_client),
) -> SimulationResponse:
    with SessionLocal() as session:
        sv = session.get(SkillVersion, request.skill_version_id)
        if sv is None:
            raise HTTPException(status_code=404, detail="skill version not found")

        ticket_batch_id = uuid.uuid4()
        sim_run = SimulationRun(
            skill_version_id=request.skill_version_id,
            ticket_batch_id=ticket_batch_id,
            status="pending",
        )
        session.add(sim_run)
        session.flush()

        job = Job(
            kind="simulation",
            status="pending",
            payload={"sim_run_id": str(sim_run.id)},
        )
        session.add(job)
        session.commit()
        job_id = job.id
        sim_run_id = sim_run.id

    background_tasks.add_task(
        _run_simulation_job,
        job_id,
        sim_run_id,
        request.skill_version_id,
        request.tickets,
        llm_client,
    )
    return SimulationResponse(job_id=job_id, status="pending")


class SimulationStatusResponse(BaseModel):
    id: uuid.UUID
    status: str
    summary: dict[str, Any] | None


@router.get("/simulations/{sim_id}")
def get_simulation(sim_id: uuid.UUID) -> SimulationStatusResponse:
    with SessionLocal() as session:
        run = session.get(SimulationRun, sim_id)
        if run is None:
            raise HTTPException(status_code=404, detail="simulation not found")
        return SimulationStatusResponse(id=run.id, status=run.status, summary=run.summary)


@router.get("/simulations/{sim_id}/report")
def get_simulation_report(sim_id: uuid.UUID) -> dict[str, Any]:
    with SessionLocal() as session:
        run = session.get(SimulationRun, sim_id)
        if run is None:
            raise HTTPException(status_code=404, detail="simulation not found")
        if run.status != "completed" or run.summary is None:
            raise HTTPException(status_code=409, detail="simulation not yet completed")
        return run.summary


@router.get("/simulations/{sim_id}/report.html", response_class=HTMLResponse)
def get_simulation_report_html(sim_id: uuid.UUID) -> str:
    """Render simulation report as a print-friendly standalone HTML page."""
    with SessionLocal() as session:
        run = session.get(SimulationRun, sim_id)
        if run is None:
            raise HTTPException(status_code=404, detail="simulation not found")
        if run.status != "completed" or run.summary is None:
            raise HTTPException(status_code=409, detail="simulation not yet completed")
        report = SimulationReport.model_validate(run.summary)
        skill_version = session.get(SkillVersion, run.skill_version_id)
        skill = Skill.model_validate(skill_version.spec) if skill_version is not None else None

    template = _jinja_env.get_template("report.html")
    extracted_rule_count = (
        len(skill.decision_zones.deterministic)
        + len(skill.decision_zones.llm_assisted)
        + len(skill.decision_zones.human_only)
        if skill is not None
        else None
    )
    return template.render(
        report=report,
        skill_name=skill.skill_name if skill is not None else "Unavailable",
        extracted_rule_count=extracted_rule_count,
        generated_at=run.completed_at,
    )


class CrossDocumentContradictionRequest(BaseModel):
    skill_version_ids: list[uuid.UUID]


class CrossDocumentCitationResponse(BaseModel):
    policy_id: str
    zone: str
    rule_index: int
    action: str


class CrossDocumentContradictionResponse(BaseModel):
    decision_surface: str
    policy_1: str
    policy_2: str
    action_1: str
    action_2: str
    rationale: str
    citation_1: CrossDocumentCitationResponse
    citation_2: CrossDocumentCitationResponse


def _to_response(contradiction: CrossDocumentContradiction) -> CrossDocumentContradictionResponse:
    return CrossDocumentContradictionResponse(
        decision_surface=contradiction.decision_surface,
        policy_1=contradiction.policy_1,
        policy_2=contradiction.policy_2,
        action_1=contradiction.action_1,
        action_2=contradiction.action_2,
        rationale=contradiction.rationale,
        citation_1=CrossDocumentCitationResponse(
            policy_id=contradiction.citation_1.policy_id,
            zone=contradiction.citation_1.zone,
            rule_index=contradiction.citation_1.rule_index,
            action=contradiction.citation_1.action,
        ),
        citation_2=CrossDocumentCitationResponse(
            policy_id=contradiction.citation_2.policy_id,
            zone=contradiction.citation_2.zone,
            rule_index=contradiction.citation_2.rule_index,
            action=contradiction.citation_2.action,
        ),
    )


@router.post("/cross-document-contradictions")
def detect_conflicts(
    request: CrossDocumentContradictionRequest,
    llm_client: LLMClient = Depends(get_llm_client),
) -> list[CrossDocumentContradictionResponse]:
    """Detect contradictions across two or more policy documents (scope A3).

    Synchronous by design: unlike /simulations, this aligns already-extracted
    skill specs rather than simulating a ticket batch, so the LLM call count
    is bounded by the number of rules and same-surface cross-document pairs,
    not by ticket volume.
    """
    if len(request.skill_version_ids) < 2:
        raise HTTPException(status_code=400, detail="at least 2 skill_version_ids are required")

    with SessionLocal() as session:
        policies: list[PolicyDocument] = []
        for version_id in request.skill_version_ids:
            sv = session.get(SkillVersion, version_id)
            if sv is None:
                raise HTTPException(status_code=404, detail=f"skill version {version_id} not found")
            policy_id = str(sv.source_policy_id) if sv.source_policy_id is not None else str(sv.id)
            policies.append(PolicyDocument(policy_id=policy_id, skill=Skill.model_validate(sv.spec)))

    contradictions = detect_cross_document_contradictions(policies, llm_client)
    return [_to_response(c) for c in contradictions]
