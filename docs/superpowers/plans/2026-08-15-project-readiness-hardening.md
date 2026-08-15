# Project Readiness Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Skiljo demonstrably portfolio/interview/demo ready by proving the complete diagnostic workflow and tightening docs, evals, evidence artifacts, and positioning.

**Architecture:** Close the product workflow through existing FastAPI routers, SQLAlchemy models, background jobs, Pydantic schemas, and Streamlit/API-client patterns. Add minimal persistence for uploaded policies and imported historical ticket batches, then cover policy upload -> extraction -> persisted SkillVersion -> ticket simulation -> HTML report with deterministic local tests.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.x, Alembic, Pydantic v2, pytest, Jinja2, Streamlit, Inspect evals, TypeScript SDK, pnpm/vitest.

## Global Constraints

- Do not read, print, summarize, or tune against `data/eval/test/`.
- Do not bypass `LLMClient` for real LLM behavior; deterministic tests may use `FakeLLMClient`.
- Keep skill versions immutable: create new `skill_versions` rows; never update a persisted `spec`.
- Use schema/codegen workflow if canonical JSON Schemas change.
- Use Alembic for database schema changes.
- Do not add Celery, Redis, Kafka, vector databases, or new infrastructure.
- Keep real-provider evals opt-in; default local/CI tests must not require network or API keys.
- Preserve backward compatibility for existing callers using inline `policy_text` and inline simulation `tickets`.

---

### Task 1: Policy Upload API And Extraction By Policy ID

**Files:**
- Create: `packages/api/src/skiljo_api/routers/policies.py`
- Create: `packages/api/tests/test_policies.py`
- Modify: `packages/api/src/skiljo_api/main.py`
- Modify: `packages/api/src/skiljo_api/routers/skills.py`
- Modify: `packages/api/tests/test_skills_extract.py`
- Modify: `docs/DESIGN_DOCUMENT.md`

**Interfaces:**
- Produces: `POST /policies` with JSON body `{"raw_text": str, "source_filename": str | None}` returning `{id, source_filename, raw_text, uploaded_at}`.
- Produces: `GET /policies/{policy_id}` returning the persisted policy.
- Extends: `ExtractRequest` to accept either `policy_text` or `policy_id`; existing inline `policy_text` callers keep working.
- Consumes: existing `Policy`, `Skill`, `SkillVersion`, `Job`, and `run_extraction_pipeline()`.

- [ ] **Step 1: Write failing policy API tests**

Add `packages/api/tests/test_policies.py`:

```python
import uuid

from fastapi.testclient import TestClient

from skiljo_api.main import app
from skiljo_core.db.models import Policy
from skiljo_core.db.session import SessionLocal


def _clean_policies() -> None:
    with SessionLocal() as session:
        session.query(Policy).delete()
        session.commit()


def test_upload_policy_persists_and_returns_policy() -> None:
    _clean_policies()
    client = TestClient(app)

    response = client.post(
        "/policies",
        json={
            "raw_text": "Refunds under $100 are approved.",
            "source_filename": "refund-policy.txt",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert uuid.UUID(data["id"])
    assert data["source_filename"] == "refund-policy.txt"
    assert data["raw_text"] == "Refunds under $100 are approved."
    assert data["uploaded_at"]

    with SessionLocal() as session:
        stored = session.get(Policy, uuid.UUID(data["id"]))
        assert stored is not None
        assert stored.raw_text == "Refunds under $100 are approved."


def test_get_policy_returns_404_for_missing_policy() -> None:
    client = TestClient(app)
    response = client.get(f"/policies/{uuid.uuid4()}")
    assert response.status_code == 404
    assert response.json()["error"]["message"] == "policy not found"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest packages/api/tests/test_policies.py -v
```

Expected: FAIL because `/policies` routes do not exist.

- [ ] **Step 3: Implement `policies.py` and route registration**

Create `packages/api/src/skiljo_api/routers/policies.py`:

```python
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
```

Modify `packages/api/src/skiljo_api/main.py`:

```python
from skiljo_api.routers import evals, jobs, policies, simulations, skills, tickets

app.include_router(policies.router)
```

- [ ] **Step 4: Run policy tests to verify they pass**

Run:

```bash
uv run pytest packages/api/tests/test_policies.py -v
```

Expected: PASS.

- [ ] **Step 5: Write failing extraction-by-policy-id test**

Append to `packages/api/tests/test_skills_extract.py`:

```python
def test_extract_endpoint_accepts_existing_policy_id() -> None:
    _clean_tables()
    policy_text = "Refunds under $100 within 30 days are approved."
    fake_client = FakeLLMClient(
        [
            SegmentationResult(segments=[Segment(segment_type="thresholds", text=policy_text)]),
            CandidateRuleList(
                rules=[
                    DeterministicRule(
                        condition=Condition(
                            all=[
                                ConditionOrPredicate(
                                    root=Predicate(field="refund_amount", op=Operator.lt, value=100)
                                )
                            ]
                        ),
                        action="approve_refund",
                        citation=Citation(span=Span(start=0, end=7), quoted_text="Refunds"),
                    )
                ]
            ),
            ZoneClassification(zone="deterministic"),
        ]
    )
    app.dependency_overrides[get_llm_client] = lambda: fake_client
    try:
        client = TestClient(app)
        upload = client.post("/policies", json={"raw_text": policy_text, "source_filename": "refunds.txt"})
        assert upload.status_code == 201
        policy_id = upload.json()["id"]

        response = client.post(
            "/skills/extract",
            json={
                "policy_id": policy_id,
                "skill_name": "process_refund_request",
                "trigger": "customer_requests_refund",
            },
        )

        assert response.status_code == 202
        job_id = uuid.UUID(response.json()["job_id"])
        with SessionLocal() as session:
            job = session.get(Job, job_id)
            assert job is not None
            assert job.status == "completed"
            version = session.get(SkillVersion, job.result_ref)
            assert version is not None
            assert str(version.source_policy_id) == policy_id
            assert version.spec["decision_zones"]["deterministic"][0]["citation"]["quoted_text"] == "Refunds"
    finally:
        app.dependency_overrides.clear()
```

- [ ] **Step 6: Run test to verify it fails**

Run:

```bash
uv run pytest packages/api/tests/test_skills_extract.py::test_extract_endpoint_accepts_existing_policy_id -v
```

Expected: FAIL because `ExtractRequest` requires `policy_text`.

- [ ] **Step 7: Extend extraction request without breaking inline extraction**

Modify `packages/api/src/skiljo_api/routers/skills.py`:

```python
class ExtractRequest(BaseModel):
    policy_text: str | None = None
    policy_id: uuid.UUID | None = None
    skill_name: str
    trigger: str
```

Inside `extract_skill()`:

```python
with SessionLocal() as session:
    if request.policy_id is not None:
        policy = session.get(Policy, request.policy_id)
        if policy is None:
            raise HTTPException(status_code=404, detail="policy not found")
    elif request.policy_text:
        policy = Policy(raw_text=request.policy_text)
        session.add(policy)
        session.flush()
    else:
        raise HTTPException(status_code=400, detail="policy_text or policy_id is required")
```

Keep `_run_extraction_job()` unchanged; it already reads `Policy.raw_text` by `policy_id`.

- [ ] **Step 8: Run extraction and policy tests**

Run:

```bash
uv run pytest packages/api/tests/test_policies.py packages/api/tests/test_skills_extract.py -v
```

Expected: PASS.

- [ ] **Step 9: Update API docs**

Update `docs/DESIGN_DOCUMENT.md` API sections so `/policies` reflects shipped implementation and `/skills/extract` documents both `policy_text` and `policy_id`.

- [ ] **Step 10: Commit**

```bash
git add packages/api/src/skiljo_api/routers/policies.py packages/api/src/skiljo_api/main.py packages/api/src/skiljo_api/routers/skills.py packages/api/tests/test_policies.py packages/api/tests/test_skills_extract.py docs/DESIGN_DOCUMENT.md
git commit -m "feat(api): add policy upload workflow [readiness]"
```

---

### Task 2: Persist Historical Ticket Batches And Simulate Imported Tickets

**Files:**
- Modify: `packages/core/src/skiljo_core/db/models.py`
- Create: `packages/core/alembic/versions/a7b2c9d4e5f6_ticket_batches.py`
- Modify: `packages/api/src/skiljo_api/routers/tickets.py`
- Modify: `packages/api/src/skiljo_api/routers/simulations.py`
- Modify: `packages/api/tests/test_tickets_import.py`
- Modify: `packages/api/tests/test_simulations.py`
- Modify: `docs/DESIGN_DOCUMENT.md`

**Interfaces:**
- Produces DB model `TicketBatch(id, source_filename, ticket_count, created_at)`.
- Produces DB model `TicketRecord(id, batch_id, ticket_id, ticket_data)`.
- Extends `POST /tickets/import` to persist valid tickets and keep returning `{batch_id, count, errors}`.
- Adds `GET /tickets/batches/{batch_id}` returning batch metadata and ticket JSON.
- Extends `SimulationRequest` to accept either inline `tickets` or persisted `ticket_batch_id`.

- [ ] **Step 1: Write failing persistence tests for ticket import**

Append to `packages/api/tests/test_tickets_import.py`:

```python
import uuid

from skiljo_core.db.models import TicketBatch, TicketRecord
from skiljo_core.db.session import SessionLocal


def _clean_ticket_tables() -> None:
    with SessionLocal() as session:
        session.query(TicketRecord).delete()
        session.query(TicketBatch).delete()
        session.commit()


def test_import_persists_ticket_batch_and_records() -> None:
    _clean_ticket_tables()
    csv_data = _make_csv_bytes([VALID_ROW])

    response = client.post(
        "/tickets/import",
        files={"file": ("tickets.csv", io.BytesIO(csv_data), "text/csv")},
    )

    assert response.status_code == 200
    batch_id = uuid.UUID(response.json()["batch_id"])
    with SessionLocal() as session:
        batch = session.get(TicketBatch, batch_id)
        assert batch is not None
        assert batch.source_filename == "tickets.csv"
        assert batch.ticket_count == 1
        records = session.query(TicketRecord).filter(TicketRecord.batch_id == batch_id).all()
        assert len(records) == 1
        assert records[0].ticket_data["ground_truth_decision"] == "approve_refund"


def test_get_ticket_batch_returns_imported_tickets() -> None:
    _clean_ticket_tables()
    csv_data = _make_csv_bytes([VALID_ROW])
    imported = client.post(
        "/tickets/import",
        files={"file": ("tickets.csv", io.BytesIO(csv_data), "text/csv")},
    )
    batch_id = imported.json()["batch_id"]

    response = client.get(f"/tickets/batches/{batch_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == batch_id
    assert data["ticket_count"] == 1
    assert data["tickets"][0]["ground_truth_decision"] == "approve_refund"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest packages/api/tests/test_tickets_import.py::test_import_persists_ticket_batch_and_records packages/api/tests/test_tickets_import.py::test_get_ticket_batch_returns_imported_tickets -v
```

Expected: FAIL because `TicketBatch`/`TicketRecord` do not exist.

- [ ] **Step 3: Add SQLAlchemy models**

Modify `packages/core/src/skiljo_core/db/models.py`:

```python
class TicketBatch(Base):
    __tablename__ = "ticket_batches"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_filename: Mapped[str | None] = mapped_column(Text)
    ticket_count: Mapped[int] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class TicketRecord(Base):
    __tablename__ = "ticket_records"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    batch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ticket_batches.id"), nullable=False)
    ticket_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    ticket_data: Mapped[dict] = mapped_column(JSONB, nullable=False)
```

- [ ] **Step 4: Add Alembic migration**

Create `packages/core/alembic/versions/a7b2c9d4e5f6_ticket_batches.py`:

```python
"""ticket batches

Revision ID: a7b2c9d4e5f6
Revises: df49c1c3cda5
Create Date: 2026-08-15
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "a7b2c9d4e5f6"
down_revision = "df49c1c3cda5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ticket_batches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source_filename", sa.Text(), nullable=True),
        sa.Column("ticket_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "ticket_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("batch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ticket_batches.id"), nullable=False),
        sa.Column("ticket_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ticket_data", postgresql.JSONB(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("ticket_records")
    op.drop_table("ticket_batches")
```

- [ ] **Step 5: Persist imported tickets and add batch retrieval**

Modify `packages/api/src/skiljo_api/routers/tickets.py`:

```python
from skiljo_core.db.models import TicketBatch, TicketRecord
from skiljo_core.db.session import SessionLocal
```

In `import_tickets()`, after validating at least one ticket:

```python
batch_id = uuid.uuid4()
with SessionLocal() as session:
    batch = TicketBatch(
        id=batch_id,
        source_filename=filename,
        ticket_count=len(tickets),
    )
    session.add(batch)
    for ticket in tickets:
        session.add(
            TicketRecord(
                batch_id=batch_id,
                ticket_id=ticket.ticket_id,
                ticket_data=ticket.model_dump(mode="json"),
            )
        )
    session.commit()
```

Add endpoint:

```python
@router.get("/batches/{batch_id}")
def get_ticket_batch(batch_id: uuid.UUID) -> dict:
    with SessionLocal() as session:
        batch = session.get(TicketBatch, batch_id)
        if batch is None:
            raise HTTPException(status_code=404, detail="ticket batch not found")
        records = session.query(TicketRecord).filter(TicketRecord.batch_id == batch_id).all()
        return {
            "id": str(batch.id),
            "source_filename": batch.source_filename,
            "ticket_count": batch.ticket_count,
            "tickets": [record.ticket_data for record in records],
        }
```

- [ ] **Step 6: Run ticket import tests**

Run:

```bash
uv run pytest packages/api/tests/test_tickets_import.py -v
```

Expected: PASS.

- [ ] **Step 7: Write failing simulation-by-batch test**

Append to `packages/api/tests/test_simulations.py`:

```python
def test_simulation_accepts_imported_ticket_batch_id() -> None:
    _clean()
    _, version_id = _seed_approved_skill()
    client = TestClient(app)
    csv_data = b"customer_id,refund_amount,purchase_days_ago,customer_segment,fraud_flags,refund_reason,ground_truth_decision\ncust_1,50,10,standard,[],defective,approve_refund\n"
    imported = client.post(
        "/tickets/import",
        files={"file": ("tickets.csv", io.BytesIO(csv_data), "text/csv")},
    )
    assert imported.status_code == 200
    batch_id = imported.json()["batch_id"]

    response = client.post(
        "/simulations",
        json={"skill_version_id": str(version_id), "ticket_batch_id": batch_id},
    )

    assert response.status_code == 202
    job_id = uuid.UUID(response.json()["job_id"])
    with SessionLocal() as session:
        job = session.get(Job, job_id)
        assert job is not None
        assert job.status == "completed"
        run = session.get(SimulationRun, job.result_ref)
        assert run is not None
        assert str(run.ticket_batch_id) == batch_id
        assert run.summary["total_tickets"] == 1
```

Import `io` if not already present.

- [ ] **Step 8: Run test to verify it fails**

Run:

```bash
uv run pytest packages/api/tests/test_simulations.py::test_simulation_accepts_imported_ticket_batch_id -v
```

Expected: FAIL because `SimulationRequest` requires inline `tickets`.

- [ ] **Step 9: Extend simulation request**

Modify `packages/api/src/skiljo_api/routers/simulations.py`:

```python
from skiljo_core.db.models import Job, SimulationResult, SimulationRun, SkillVersion, TicketRecord


class SimulationRequest(BaseModel):
    skill_version_id: uuid.UUID
    tickets: list[dict[str, Any]] | None = None
    ticket_batch_id: uuid.UUID | None = None
```

Inside `create_simulation()` before creating `SimulationRun`:

```python
if request.ticket_batch_id is not None and request.tickets is not None:
    raise HTTPException(status_code=400, detail="provide either tickets or ticket_batch_id, not both")
if request.ticket_batch_id is None and request.tickets is None:
    raise HTTPException(status_code=400, detail="tickets or ticket_batch_id is required")

if request.ticket_batch_id is not None:
    records = session.query(TicketRecord).filter(TicketRecord.batch_id == request.ticket_batch_id).all()
    if not records:
        raise HTTPException(status_code=404, detail="ticket batch not found")
    tickets_raw = [record.ticket_data for record in records]
    ticket_batch_id = request.ticket_batch_id
else:
    tickets_raw = request.tickets or []
    ticket_batch_id = uuid.uuid4()
```

Use `tickets_raw` and `ticket_batch_id` when creating the job/run/background task.

- [ ] **Step 10: Run simulation and ticket tests**

Run:

```bash
uv run pytest packages/api/tests/test_tickets_import.py packages/api/tests/test_simulations.py -v
```

Expected: PASS.

- [ ] **Step 11: Update docs**

Update `docs/DESIGN_DOCUMENT.md` so `POST /tickets/import` explicitly creates a persisted batch usable by `POST /simulations`.

- [ ] **Step 12: Commit**

```bash
git add packages/core/src/skiljo_core/db/models.py packages/core/alembic/versions/*_ticket_batches.py packages/api/src/skiljo_api/routers/tickets.py packages/api/src/skiljo_api/routers/simulations.py packages/api/tests/test_tickets_import.py packages/api/tests/test_simulations.py docs/DESIGN_DOCUMENT.md
git commit -m "feat(api): persist ticket batches for simulation [readiness]"
```

---

### Task 3: Deterministic Complete Diagnostic Workflow Test

**Files:**
- Create: `packages/api/tests/test_diagnostic_workflow.py`
- Modify: `packages/api/tests/conftest.py` if cleanup helpers should be centralized
- Modify: `docs/learning/README.md`
- Create: `docs/learning/week8-task1-diagnostic-workflow.md`
- Modify: `docs/learning/GLOSSARY.md`

**Interfaces:**
- Consumes: `POST /policies`, `POST /skills/extract` with `policy_id`, `POST /tickets/import`, `POST /simulations` with `ticket_batch_id`, `GET /simulations/{id}/report`, and `GET /simulations/{id}/report.html`.
- Produces: automated proof of policy upload -> extraction -> structured `Skill` -> persisted immutable version -> historical ticket simulation -> generated report.

- [ ] **Step 1: Write failing end-to-end local workflow test**

Create `packages/api/tests/test_diagnostic_workflow.py`:

```python
import io
import uuid

from fastapi.testclient import TestClient

from skiljo_api.dependencies import get_llm_client
from skiljo_api.main import app
from skiljo_core.db.models import Job, Policy, SimulationResult, SimulationRun, Skill, SkillVersion, TicketBatch, TicketRecord
from skiljo_core.db.session import SessionLocal
from skiljo_core.extraction.rules import CandidateRuleList
from skiljo_core.extraction.segmentation import Segment, SegmentationResult
from skiljo_core.extraction.zones import ZoneClassification
from skiljo_core.schemas.rule_schema import Citation, Condition, ConditionOrPredicate, DeterministicRule, Operator, Predicate, Span
from skiljo_core.testing import FakeLLMClient


POLICY_TEXT = "Refunds under $100 within 30 days are approved."


def _clean() -> None:
    with SessionLocal() as session:
        session.query(SimulationResult).delete()
        session.query(SimulationRun).delete()
        session.query(TicketRecord).delete()
        session.query(TicketBatch).delete()
        session.query(SkillVersion).delete()
        session.query(Skill).delete()
        session.query(Job).delete()
        session.query(Policy).delete()
        session.commit()


def test_complete_diagnostic_workflow_policy_to_html_report() -> None:
    _clean()
    fake_client = FakeLLMClient(
        [
            SegmentationResult(segments=[Segment(segment_type="thresholds", text=POLICY_TEXT)]),
            CandidateRuleList(
                rules=[
                    DeterministicRule(
                        condition=Condition(
                            all=[
                                ConditionOrPredicate(
                                    root=Predicate(field="refund_amount", op=Operator.lt, value=100)
                                ),
                                ConditionOrPredicate(
                                    root=Predicate(field="purchase_days_ago", op=Operator.lte, value=30)
                                ),
                            ]
                        ),
                        action="approve_refund",
                        citation=Citation(span=Span(start=0, end=7), quoted_text="Refunds"),
                    )
                ]
            ),
            ZoneClassification(zone="deterministic"),
        ]
    )
    app.dependency_overrides[get_llm_client] = lambda: fake_client
    client = TestClient(app)
    try:
        uploaded_policy = client.post(
            "/policies",
            json={"raw_text": POLICY_TEXT, "source_filename": "refund-policy.txt"},
        )
        assert uploaded_policy.status_code == 201
        policy_id = uploaded_policy.json()["id"]

        extracted = client.post(
            "/skills/extract",
            json={
                "policy_id": policy_id,
                "skill_name": "process_refund_request",
                "trigger": "customer_requests_refund",
            },
        )
        assert extracted.status_code == 202
        extraction_job_id = uuid.UUID(extracted.json()["job_id"])

        with SessionLocal() as session:
            extraction_job = session.get(Job, extraction_job_id)
            assert extraction_job is not None
            assert extraction_job.status == "completed"
            version = session.get(SkillVersion, extraction_job.result_ref)
            assert version is not None
            assert version.source_policy_id == uuid.UUID(policy_id)
            assert version.version_number == 1
            assert version.status == "draft"
            assert version.spec["skill_name"] == "process_refund_request"
            assert version.spec["decision_zones"]["deterministic"][0]["citation"]["quoted_text"] == "Refunds"
            skill = session.get(Skill, version.skill_id)
            assert skill is not None
            assert skill.current_version_id == version.id
            version_id = version.id

        csv_bytes = (
            "customer_id,refund_amount,purchase_days_ago,customer_segment,fraud_flags,refund_reason,ground_truth_decision\n"
            "cust_1,50,10,standard,[],defective,approve_refund\n"
            "cust_2,150,10,standard,[],changed_mind,human_review\n"
        ).encode()
        imported_tickets = client.post(
            "/tickets/import",
            files={"file": ("tickets.csv", io.BytesIO(csv_bytes), "text/csv")},
        )
        assert imported_tickets.status_code == 200
        ticket_batch_id = imported_tickets.json()["batch_id"]

        simulation = client.post(
            "/simulations",
            json={"skill_version_id": str(version_id), "ticket_batch_id": ticket_batch_id},
        )
        assert simulation.status_code == 202
        simulation_job_id = uuid.UUID(simulation.json()["job_id"])

        with SessionLocal() as session:
            simulation_job = session.get(Job, simulation_job_id)
            assert simulation_job is not None
            assert simulation_job.status == "completed"
            sim_run_id = simulation_job.result_ref

        report = client.get(f"/simulations/{sim_run_id}/report")
        assert report.status_code == 200
        report_json = report.json()
        assert report_json["skill_version_id"] == str(version_id)
        assert report_json["total_tickets"] == 2
        assert "match_rate" in report_json
        assert "results" in report_json

        html = client.get(f"/simulations/{sim_run_id}/report.html")
        assert html.status_code == 200
        assert "text/html" in html.headers["content-type"]
        assert "Executive Summary" in html.text
        assert "process_refund_request" in html.text
    finally:
        app.dependency_overrides.clear()
```

- [ ] **Step 2: Run test to verify it fails before Tasks 1-2 are complete**

Run:

```bash
uv run pytest packages/api/tests/test_diagnostic_workflow.py -v
```

Expected before Tasks 1-2: FAIL. Expected after Tasks 1-2 implementation: PASS.

- [ ] **Step 3: Run the test after Tasks 1-2**

Run:

```bash
uv run pytest packages/api/tests/test_diagnostic_workflow.py -v
```

Expected: PASS and no real LLM/API key usage.

- [ ] **Step 4: Write learning debrief**

Create `docs/learning/week8-task1-diagnostic-workflow.md`:

```markdown
# Week 8 Task 1: Complete Diagnostic Workflow

## What Changed

The API now has a deterministic local integration test for the full diagnostic path: policy upload, extraction from a persisted policy, immutable skill-version persistence, historical ticket import, simulation by ticket batch, and HTML report generation.

## Why It Matters

This proves Skiljo is no longer just a set of separate endpoints. The product workflow a buyer would evaluate is covered as one path, without requiring a real LLM call or external service in tests.

## Where To Look

- `packages/api/tests/test_diagnostic_workflow.py`
- `packages/api/src/skiljo_api/routers/policies.py`
- `packages/api/src/skiljo_api/routers/tickets.py`
- `packages/api/src/skiljo_api/routers/simulations.py`
```

Add to `docs/learning/README.md` under Week 8:

```markdown
## Week 8 - Project readiness hardening

1. [Task 1: Complete diagnostic workflow](week8-task1-diagnostic-workflow.md)
```

Add `Diagnostic workflow` to `docs/learning/GLOSSARY.md` alphabetically:

```markdown
## Diagnostic workflow

The complete Skiljo product path: upload a policy, extract a structured `Skill`, persist an immutable `SkillVersion`, import historical tickets, simulate those tickets against the version, and generate a diagnostic report. See [Week 8 Task 1](week8-task1-diagnostic-workflow.md).
```

- [ ] **Step 5: Commit**

```bash
git add packages/api/tests/test_diagnostic_workflow.py docs/learning/week8-task1-diagnostic-workflow.md docs/learning/README.md docs/learning/GLOSSARY.md
git commit -m "test(api): cover complete diagnostic workflow [readiness]"
```

---

### Task 4: Activate Extraction Eval Solver

**Files:**
- Modify: `packages/core/src/skiljo_core/eval/extraction.py`
- Modify: `packages/core/src/skiljo_core/eval/collect_metrics.py`
- Modify: `packages/core/tests/test_eval_extraction.py`
- Modify: `packages/core/tests/test_eval_collect_metrics.py`
- Modify: `docs/evals.md`
- Create: `docs/learning/week8-task2-extraction-eval-solver.md`
- Modify: `docs/learning/README.md`
- Modify: `docs/learning/GLOSSARY.md`

**Interfaces:**
- Produces: extraction eval solver that populates `state.metadata["actual_spec"]` by running `run_extraction_pipeline()`.
- Produces: deterministic test seam accepting an injected `LLMClient` for solver unit tests.
- Preserves: `split="test"` remains rejected by dataset loader.

- [ ] **Step 1: Write failing scorer/solver behavior test**

Add to `packages/core/tests/test_eval_extraction.py`:

```python
from inspect_ai.solver import TaskState
from inspect_ai.util import JSON

from skiljo_core.eval.extraction import extraction_solver
from skiljo_core.extraction.rules import CandidateRuleList
from skiljo_core.extraction.segmentation import Segment, SegmentationResult
from skiljo_core.extraction.zones import ZoneClassification
from skiljo_core.schemas.rule_schema import Citation, Condition, ConditionOrPredicate, DeterministicRule, Operator, Predicate, Span
from skiljo_core.testing import FakeLLMClient


async def test_extraction_solver_populates_actual_spec_metadata() -> None:
    policy_text = "Refunds under $100 are approved."
    fake_client = FakeLLMClient(
        [
            SegmentationResult(segments=[Segment(segment_type="thresholds", text=policy_text)]),
            CandidateRuleList(
                rules=[
                    DeterministicRule(
                        condition=Condition(
                            all=[
                                ConditionOrPredicate(
                                    root=Predicate(field="refund_amount", op=Operator.lt, value=100)
                                )
                            ]
                        ),
                        action="approve_refund",
                        citation=Citation(span=Span(start=0, end=7), quoted_text="Refunds"),
                    )
                ]
            ),
            ZoneClassification(zone="deterministic"),
        ]
    )
    solver = extraction_solver(llm_client=fake_client)
    state = TaskState(
        model="mockllm/model",
        sample_id="sample-1",
        epoch=1,
        input=policy_text,
        messages=[],
        metadata={"skill_name": "process_refund_request", "trigger": "customer_requests_refund"},
    )

    result = await solver(state, generate=None)

    actual = result.metadata["actual_spec"]
    assert actual["skill_name"] == "process_refund_request"
    assert actual["decision_zones"]["deterministic"][0]["citation"]["quoted_text"] == "Refunds"
```

Adjust `TaskState` construction only if the installed Inspect version requires different required fields; keep the assertion behavior unchanged.

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest packages/core/tests/test_eval_extraction.py::test_extraction_solver_populates_actual_spec_metadata -v
```

Expected: FAIL because `extraction_solver` does not exist.

- [ ] **Step 3: Implement extraction solver**

Modify `packages/core/src/skiljo_core/eval/extraction.py`:

```python
from inspect_ai.solver import Generate, Solver, TaskState, solver

from skiljo_core.extraction.pipeline import run_extraction_pipeline
from skiljo_core.llm.base import LLMClient
from skiljo_core.testing import FakeLLMClient


@solver
def extraction_solver(llm_client: LLMClient | None = None) -> Solver:
    async def solve(state: TaskState, generate: Generate) -> TaskState:
        client = llm_client
        if client is None:
            client = FakeLLMClient([])
        skill = run_extraction_pipeline(
            client,
            policy_text=str(state.input),
            skill_name=str(state.metadata.get("skill_name", "process_refund_request")),
            trigger=str(state.metadata.get("trigger", "customer_requests_refund")),
        )
        state.metadata["actual_spec"] = skill.model_dump(mode="json")
        return state

    return solve
```

If importing `FakeLLMClient` from production eval code creates an unacceptable test-only dependency, instead add a small `NoopLLMClient` in the eval module that raises a clear `RuntimeError("extraction_solver requires an LLM client for real extraction")` when no client is provided, then keep actual local metric collection explicit about model/client limitations.

Modify `ExtractionEval()`:

```python
return Task(
    dataset=list(load_extraction_dataset(split=split)),
    solver=extraction_solver(),
    scorer=[recall_scorer(), citation_scorer()],
    name="extract",
)
```

- [ ] **Step 4: Run focused eval tests**

Run:

```bash
uv run pytest packages/core/tests/test_eval_extraction.py packages/core/tests/test_eval_collect_metrics.py -v
```

Expected: PASS.

- [ ] **Step 5: Run metric collector and document actual behavior**

Run:

```bash
uv run python -m skiljo_core.eval.collect_metrics --output /tmp/skiljo-eval-readiness.json --split train
```

Expected: command exits 0. If default mock solver cannot produce meaningful extraction because no fake responses exist for all 30 samples, document that real extraction metrics require an opt-in real `LLMClient` and keep the command behavior explicit rather than masking it.

- [ ] **Step 6: Update eval docs**

Update `docs/evals.md` and `collect_metrics.py` docstrings so they say exactly:

- extraction dataset loading is active for train/dev.
- extraction solver behavior is active only when a usable LLM client/provider is configured.
- citation resolution is still a hard invariant.
- simulation/e2e metrics remain limited until ticket-level ground truth lands.
- `data/eval/test/` remains forbidden locally.

- [ ] **Step 7: Write learning debrief**

Create `docs/learning/week8-task2-extraction-eval-solver.md`:

```markdown
# Week 8 Task 2: Extraction Eval Solver

## What Changed

The extraction eval path now has an explicit solver seam for running the extraction pipeline per train/dev sample and writing the resulting `Skill` spec into `state.metadata["actual_spec"]`.

## Why It Matters

Extraction recall is only useful when it compares expected rules to actual pipeline output. This task closes the empty-actual gap or, when a real provider is not configured, makes that limitation explicit.

## Where To Look

- `packages/core/src/skiljo_core/eval/extraction.py`
- `packages/core/src/skiljo_core/eval/collect_metrics.py`
- `packages/core/tests/test_eval_extraction.py`
```

Update learning index and glossary with `Eval solver`.

- [ ] **Step 8: Commit**

```bash
git add packages/core/src/skiljo_core/eval/extraction.py packages/core/src/skiljo_core/eval/collect_metrics.py packages/core/tests/test_eval_extraction.py packages/core/tests/test_eval_collect_metrics.py docs/evals.md docs/learning/week8-task2-extraction-eval-solver.md docs/learning/README.md docs/learning/GLOSSARY.md
git commit -m "feat(eval): add extraction pipeline solver [readiness]"
```

---

### Task 5: Sample Diagnostic Report Artifact

**Files:**
- Create: `scripts/generate_sample_report.py`
- Create: `docs/demo-artifacts/sample-diagnostic-report.html`
- Modify: `packages/api/tests/test_report_html.py`
- Create: `docs/learning/week8-task3-sample-report-artifact.md`
- Modify: `docs/learning/README.md`

**Interfaces:**
- Produces: reproducible script that renders a standalone sample diagnostic report using the existing Jinja2 template and typed `SimulationReport`.
- Produces: committed HTML artifact at `docs/demo-artifacts/sample-diagnostic-report.html`.

- [ ] **Step 1: Write failing script test**

Add to `packages/api/tests/test_report_html.py`:

```python
def test_sample_report_artifact_script_generates_html(tmp_path: Path) -> None:
    from scripts.generate_sample_report import generate_sample_report

    output = tmp_path / "sample.html"
    generate_sample_report(output)

    html = output.read_text()
    assert "<html" in html.lower()
    assert "Executive Summary" in html
    assert "Estimated Financial Impact" in html
    assert "Evidence Appendix" in html
```

Import `Path` from `pathlib`.

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest packages/api/tests/test_report_html.py::test_sample_report_artifact_script_generates_html -v
```

Expected: FAIL because `scripts/generate_sample_report.py` does not exist.

- [ ] **Step 3: Implement generator script**

Create `scripts/generate_sample_report.py`:

```python
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from jinja2 import Environment, FileSystemLoader

from skiljo_core.schemas.simulation_report_schema import (
    Citation,
    Contradiction,
    EstimatedFinancialImpact,
    Result,
    RoiEstimates,
    SimulationReport,
    Zone,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_DIR = REPO_ROOT / "packages" / "api" / "src" / "skiljo_api" / "templates"
DEFAULT_OUTPUT = REPO_ROOT / "docs" / "demo-artifacts" / "sample-diagnostic-report.html"


def build_sample_report() -> SimulationReport:
    return SimulationReport(
        skill_version_id=UUID("00000000-0000-0000-0000-000000000105"),
        total_tickets=12,
        match_rate=0.75,
        escalation_accuracy=1.0,
        contradiction_count=1,
        automation_candidate_count=8,
        roi_estimates=RoiEstimates(
            automation_safe_volume=8,
            manual_review_hours_saved=2.0,
            contradicted_decision_value_usd=900.0,
        ),
        contradictions=[
            Contradiction(
                cluster_key={"amount_band": "100-500", "customer_segment": "vip"},
                written_decision="human_review",
                observed_decision="approve_refund",
                frequency=0.75,
                ticket_count=12,
                affected_ticket_ids=["ticket-001", "ticket-002", "ticket-003"],
                citation=Citation(rule_id="rule-vip-review", span_start=0, span_end=42, quoted_text="Refunds over $100 require human review."),
                estimated_financial_impact=EstimatedFinancialImpact(
                    divergent_ticket_count=9,
                    average_refund_amount=100.0,
                    estimated_impact_usd=900.0,
                ),
            )
        ],
        results=[
            Result(
                ticket_id=UUID("00000000-0000-0000-0000-000000000001"),
                decision="approve_refund",
                zone=Zone.deterministic,
                matched_human_decision=True,
                reasoning="Refund amount is within the auto-approval threshold.",
            )
        ],
    )


def generate_sample_report(output_path: Path = DEFAULT_OUTPUT) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)), autoescape=True)
    template = env.get_template("report.html")
    html = template.render(
        report=build_sample_report(),
        skill_name="process_refund_request",
        extracted_rule_count=3,
        generated_at=datetime(2026, 8, 15, tzinfo=UTC),
    )
    output_path.write_text(html)


if __name__ == "__main__":
    generate_sample_report()
```

Adjust field names to match the generated `simulation_report_schema.py`.

- [ ] **Step 4: Run script test**

Run:

```bash
uv run pytest packages/api/tests/test_report_html.py::test_sample_report_artifact_script_generates_html -v
```

Expected: PASS.

- [ ] **Step 5: Generate committed artifact**

Run:

```bash
uv run python scripts/generate_sample_report.py
```

Expected: creates `docs/demo-artifacts/sample-diagnostic-report.html`.

- [ ] **Step 6: Write learning debrief**

Create `docs/learning/week8-task3-sample-report-artifact.md` with what the artifact shows, why it is generated rather than hand-authored, and where to regenerate it.

- [ ] **Step 7: Commit**

```bash
git add scripts/generate_sample_report.py docs/demo-artifacts/sample-diagnostic-report.html packages/api/tests/test_report_html.py docs/learning/week8-task3-sample-report-artifact.md docs/learning/README.md
git commit -m "docs: add generated diagnostic report artifact [readiness]"
```

---

### Task 6: Status Docs And Portfolio Package

**Files:**
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `Makefile`
- Modify: `docs/evals.md`
- Create: `docs/INTERVIEW_READINESS.md`
- Create: `docs/learning/week8-task4-readiness-docs.md`
- Modify: `docs/learning/README.md`
- Modify: `docs/learning/GLOSSARY.md`

**Interfaces:**
- Produces: public-facing status docs that match code and verification.
- Produces: interview/resume package with supported claims only.

- [ ] **Step 1: Write docs status checklist**

Create a temporary checklist in the working notes while editing:

```text
README status mentions complete diagnostic workflow.
README links sample diagnostic report.
README says eval solver/metrics caveat accurately.
AGENTS current status no longer says week 2 complete.
Makefile eval comments match current eval behavior.
docs/evals.md does not claim dataset=None for current tasks.
INTERVIEW_READINESS avoids customer/revenue/production claims.
```

- [ ] **Step 2: Update README**

Replace the stale status paragraph with:

```markdown
**Status:** The core diagnostic workflow is implemented and locally test-covered: policy upload -> extraction -> structured `Skill` -> persisted immutable `SkillVersion` -> historical ticket simulation -> JSON/HTML diagnostic report. The v1.05 consistency-checker surface is also present through cross-document contradiction detection and Streamlit workflow pages. Current caveat: extraction eval execution is still being hardened for real-provider measurement; do not treat mock/default eval output as product-quality metrics.
```

Add a short "Demo Artifacts" section linking `docs/demo-artifacts/sample-diagnostic-report.html`.

- [ ] **Step 3: Update AGENTS current status**

Replace the stale current status with:

```markdown
**Phase: readiness hardening after citations/v1.05 merge.** Core diagnostic workflow is present: policy upload, extraction, immutable skill-version persistence, historical ticket import, simulation, and rendered report. Citations are schema-required for rules. v1.05 surfaces are present: HTML diagnostic reports, cross-document contradiction detection, and Streamlit workflow integration.

**Next:** harden eval measurement and demo evidence. Keep `data/eval/test/` off limits; use train/dev only.
```

- [ ] **Step 4: Update Makefile eval comments**

Replace comments claiming no dataset loader exists with comments matching the current eval state:

```make
# Eval suites default to Inspect's mockllm/model so they run without API keys.
# Train/dev dataset loading is active. Extraction quality becomes meaningful only
# when the solver has a usable extraction client/provider; simulation/e2e metrics
# remain limited until ticket-level ground truth is added.
```

- [ ] **Step 5: Update `docs/evals.md`**

Ensure it states:

```markdown
Train/dev dataset loading is active. Local eval commands never read `data/eval/test/`.
Extraction recall is only meaningful when actual pipeline output is populated by the extraction solver.
Simulation and e2e metrics remain limited because the eval corpus does not yet contain ticket-level historical outcomes for every example.
```

- [ ] **Step 6: Add interview readiness doc**

Create `docs/INTERVIEW_READINESS.md`:

```markdown
# Interview Readiness

## 60-Second Summary

Skiljo turns refund, credit, and billing policies into versioned executable `Skill` specs, then simulates those specs against historical tickets to find where written policy and real behavior diverge.

## What Is Demonstrable

- Policy upload through FastAPI.
- Four-pass LLM extraction into structured `Skill` specs.
- Immutable `SkillVersion` persistence.
- Historical ticket CSV import and simulation.
- JSON and standalone HTML diagnostic reports.
- Cross-document contradiction detection.
- Schema-first Python/TypeScript type generation.

## Technical Stories

- Auditability: every rule requires character-offset citations.
- Reliability: structured outputs, Pydantic validation, retries, and citation validation.
- Measurement: train/dev eval corpus, regression gate plumbing, and explicit caveats where metrics are not fully meaningful.
- Product judgment: report artifacts are designed for finance/support-ops review, not just developer logs.

## Honest Limitations

- No payment flow.
- No live customer deployment claim.
- Real-provider eval metrics require deliberate opt-in runs and should be reported with exact model/date/context.
- Background jobs use FastAPI `BackgroundTasks`, so jobs are not durable across process restarts.

## Resume Bullets

- Built Skiljo, a Python/TypeScript policy-fidelity system that extracts refund and billing rules into versioned executable specifications using FastAPI, Pydantic, SQLAlchemy, Streamlit, and a generated TypeScript SDK.
- Designed a four-pass LLM extraction pipeline with structured outputs, validation retries, audit logging, and mandatory character-offset citations linking each rule to source text.
- Implemented historical-ticket simulation and contradiction detection with clustering, statistical support, and estimated financial impact reporting.
- Shipped a complete diagnostic workflow: policy upload, Skill extraction, immutable version persistence, ticket import, simulation, and standalone HTML reports.
```

- [ ] **Step 7: Write learning debrief**

Create `docs/learning/week8-task4-readiness-docs.md` summarizing the status-doc cleanup and interview package.

- [ ] **Step 8: Commit**

```bash
git add README.md AGENTS.md Makefile docs/evals.md docs/INTERVIEW_READINESS.md docs/learning/week8-task4-readiness-docs.md docs/learning/README.md docs/learning/GLOSSARY.md
git commit -m "docs: refresh project readiness status [readiness]"
```

---

### Task 7: Final Verification And Readiness Review

**Files:**
- Modify: `docs/INTERVIEW_READINESS.md`
- Modify: `docs/learning/week8-task4-readiness-docs.md` if verification notes belong there

**Interfaces:**
- Produces: final verified readiness status with exact command results.

- [ ] **Step 1: Run full verification**

Run:

```bash
make lint typecheck test
```

Expected: ruff passes, mypy passes, TypeScript typecheck passes, pytest passes, vitest passes.

- [ ] **Step 2: Run focused workflow verification**

Run:

```bash
uv run pytest packages/api/tests/test_diagnostic_workflow.py -v
```

Expected: PASS.

- [ ] **Step 3: Run eval metric collection**

Run:

```bash
uv run python -m skiljo_core.eval.collect_metrics --output /tmp/skiljo-readiness-metrics.json --split train
```

Expected: exits 0. Record exact metric values and caveats.

- [ ] **Step 4: Inspect git status**

Run:

```bash
git status --short
```

Expected: only known unrelated local files remain, or no changes.

- [ ] **Step 5: Update interview readiness with verified status**

Add a "Verified Locally" section to `docs/INTERVIEW_READINESS.md`. Replace the result text below with the exact counts from Steps 1-3 before committing:

```markdown
## Verified Locally

Last verified: 2026-08-15

- `make lint typecheck test`: ruff result, mypy result, TypeScript typecheck result, pytest pass/skip count, and vitest pass count from Step 1.
- `uv run pytest packages/api/tests/test_diagnostic_workflow.py -v`: pytest pass count from Step 2.
- `uv run python -m skiljo_core.eval.collect_metrics --output /tmp/skiljo-readiness-metrics.json --split train`: metric names, numeric values, and caveats from Step 3.
```

Use exact command output from this task.

- [ ] **Step 6: Commit verification note**

```bash
git add docs/INTERVIEW_READINESS.md docs/learning/week8-task4-readiness-docs.md
git commit -m "docs: record readiness verification results [readiness]"
```

- [ ] **Step 7: Final response**

Report:

- current `HEAD`
- exact tests run and outcomes
- what changed
- remaining caveats
- updated readiness scores
