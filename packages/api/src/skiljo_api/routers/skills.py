import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel

from skiljo_api.dependencies import get_llm_client
from skiljo_core.db.models import Job, Policy, Skill, SkillVersion
from skiljo_core.db.session import SessionLocal
from skiljo_core.extraction.pipeline import run_extraction_pipeline
from skiljo_core.llm.base import LLMClient

router = APIRouter()


class ExtractRequest(BaseModel):
    policy_text: str
    skill_name: str
    trigger: str


class ExtractResponse(BaseModel):
    job_id: uuid.UUID
    status: str


def _run_extraction_job(
    job_id: uuid.UUID, policy_id: uuid.UUID, skill_name: str, trigger: str, llm_client: LLMClient
) -> None:
    with SessionLocal() as session:
        job = session.get(Job, job_id)
        if job is None:
            return  # job was deleted before background task ran; nothing to do
        job.status = "running"
        job.started_at = datetime.now(UTC)
        session.commit()

        try:
            policy = session.get(Policy, policy_id)
            assert policy is not None, f"Policy {policy_id} not found"
            skill_spec = run_extraction_pipeline(
                llm_client, policy_text=policy.raw_text, skill_name=skill_name, trigger=trigger
            )
            skill_row = Skill(name=skill_name)
            session.add(skill_row)
            session.flush()
            version_row = SkillVersion(
                skill_id=skill_row.id,
                version_number=1,
                spec=skill_spec.model_dump(mode="json"),
                source_policy_id=policy_id,
                status="draft",
            )
            session.add(version_row)
            session.flush()

            skill_row.current_version_id = version_row.id

            job.status = "completed"
            job.result_ref = version_row.id
            job.completed_at = datetime.now(UTC)
            session.commit()
        except Exception as exc:
            job.status = "failed"
            job.error = str(exc)
            job.completed_at = datetime.now(UTC)
            session.commit()


@router.post("/skills/extract", status_code=202)
def extract_skill(
    request: ExtractRequest,
    background_tasks: BackgroundTasks,
    llm_client: LLMClient = Depends(get_llm_client),
) -> ExtractResponse:
    with SessionLocal() as session:
        policy = Policy(raw_text=request.policy_text)
        session.add(policy)
        session.flush()

        job = Job(
            kind="extraction",
            status="pending",
            payload={
                "policy_id": str(policy.id),
                "skill_name": request.skill_name,
                "trigger": request.trigger,
            },
        )
        session.add(job)
        session.commit()

        job_id = job.id
        policy_id = policy.id

    background_tasks.add_task(_run_extraction_job, job_id, policy_id, request.skill_name, request.trigger, llm_client)
    return ExtractResponse(job_id=job_id, status="pending")


class SkillSummary(BaseModel):
    id: uuid.UUID
    name: str
    current_version_id: uuid.UUID | None


class SkillVersionSummary(BaseModel):
    id: uuid.UUID
    version_number: int
    status: str
    spec: dict


@router.get("/skills")
def list_skills() -> list[SkillSummary]:
    with SessionLocal() as session:
        rows = session.query(Skill).all()
        return [SkillSummary(id=r.id, name=r.name, current_version_id=r.current_version_id) for r in rows]


@router.get("/skills/{skill_id}")
def get_skill(skill_id: uuid.UUID) -> SkillSummary:
    with SessionLocal() as session:
        skill = session.get(Skill, skill_id)
        if skill is None:
            raise HTTPException(status_code=404, detail="skill not found")
        return SkillSummary(id=skill.id, name=skill.name, current_version_id=skill.current_version_id)


@router.get("/skills/{skill_id}/versions")
def list_skill_versions(skill_id: uuid.UUID) -> list[SkillVersionSummary]:
    with SessionLocal() as session:
        rows = session.query(SkillVersion).filter(SkillVersion.skill_id == skill_id).all()
        return [
            SkillVersionSummary(id=r.id, version_number=r.version_number, status=r.status, spec=r.spec)
            for r in rows
        ]
