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
from skiljo_core.schemas.simulation_report_schema import SimulationReport
from skiljo_core.schemas.skill_schema import Skill
from skiljo_core.schemas.ticket_schema import Ticket
from skiljo_core.simulation.contradictions import detect_contradictions
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
            report = report.model_copy(update={"contradiction_count": len(contradictions)})

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

    template = _jinja_env.get_template("report.html")
    return template.render(report=report)
