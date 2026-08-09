import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from skiljo_api.dependencies import verify_api_key
from skiljo_core.db.models import EvalRun
from skiljo_core.db.session import SessionLocal

router = APIRouter(dependencies=[Depends(verify_api_key)])


class EvalRunCreate(BaseModel):
    commit_sha: str
    dataset_version: str
    model: str
    metrics: dict[str, Any]


class EvalRunResponse(BaseModel):
    id: uuid.UUID
    commit_sha: str
    dataset_version: str
    model: str
    metrics: dict[str, Any]
    ran_at: datetime


@router.post("/eval-runs", status_code=201)
def record_eval_run(run: EvalRunCreate) -> EvalRunResponse:
    """Record an eval run's result (commit SHA, dataset version, model, metrics)."""
    with SessionLocal() as session:
        eval_run = EvalRun(
            commit_sha=run.commit_sha,
            dataset_version=run.dataset_version,
            model=run.model,
            metrics=run.metrics,
        )
        session.add(eval_run)
        session.commit()
        session.refresh(eval_run)
        return EvalRunResponse.model_validate(eval_run, from_attributes=True)


@router.get("/eval-runs")
def list_eval_runs(
    model: str | None = Query(default=None, description="Filter by model name"),
    commit_sha: str | None = Query(default=None, description="Filter by commit SHA"),
    limit: int = Query(default=100, gt=0, le=500),
) -> list[EvalRunResponse]:
    """List eval run history, most recent first. Supports filtering by model or commit SHA."""
    with SessionLocal() as session:
        query = session.query(EvalRun)
        if model is not None:
            query = query.filter(EvalRun.model == model)
        if commit_sha is not None:
            query = query.filter(EvalRun.commit_sha == commit_sha)
        runs = query.order_by(EvalRun.ran_at.desc()).limit(limit).all()
        return [EvalRunResponse.model_validate(r, from_attributes=True) for r in runs]
