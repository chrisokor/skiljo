import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from skiljo_api.dependencies import verify_api_key
from skiljo_core.db.models import Policy
from skiljo_core.db.session import SessionLocal

router = APIRouter(prefix="/policies", tags=["policies"], dependencies=[Depends(verify_api_key)])


class PolicyCreateRequest(BaseModel):
    raw_text: str = Field(min_length=1)
    source_filename: str | None = None


class PolicyResponse(BaseModel):
    id: uuid.UUID
    source_filename: str | None
    raw_text: str
    uploaded_at: datetime


@router.post("", status_code=201)
def upload_policy(request: PolicyCreateRequest) -> PolicyResponse:
    with SessionLocal() as session:
        policy = Policy(raw_text=request.raw_text, source_filename=request.source_filename)
        session.add(policy)
        session.commit()
        session.refresh(policy)
        return PolicyResponse(
            id=policy.id,
            source_filename=policy.source_filename,
            raw_text=policy.raw_text,
            uploaded_at=policy.uploaded_at,
        )


@router.get("/{policy_id}")
def get_policy(policy_id: uuid.UUID) -> PolicyResponse:
    with SessionLocal() as session:
        policy = session.get(Policy, policy_id)
        if policy is None:
            raise HTTPException(status_code=404, detail="policy not found")
        return PolicyResponse(
            id=policy.id,
            source_filename=policy.source_filename,
            raw_text=policy.raw_text,
            uploaded_at=policy.uploaded_at,
        )
