import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from skiljo_api.dependencies import verify_api_key
from skiljo_core.db.models import Job
from skiljo_core.db.session import SessionLocal

router = APIRouter(dependencies=[Depends(verify_api_key)])


class JobResponse(BaseModel):
    job_id: uuid.UUID
    status: str
    result_ref: uuid.UUID | None = None
    error: str | None = None


@router.get("/jobs/{job_id}")
def get_job(job_id: uuid.UUID) -> JobResponse:
    with SessionLocal() as session:
        job = session.get(Job, job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="job not found")
        return JobResponse(job_id=job.id, status=job.status, result_ref=job.result_ref, error=job.error)
