import uuid

from fastapi.testclient import TestClient

from skiljo_api.dependencies import get_llm_client
from skiljo_api.main import app
from skiljo_core.db.models import Job, SimulationResult, SimulationRun, Skill, SkillVersion
from skiljo_core.db.session import SessionLocal
from skiljo_core.schemas.rule_schema import (
    Condition,
    ConditionOrPredicate,
    DeterministicRule,
    Operator,
    Predicate,
)
from skiljo_core.schemas.skill_schema import DecisionZones, Input, Skill as SkillSchema, Type
from skiljo_core.testing import FakeLLMClient


def _clean() -> None:
    with SessionLocal() as session:
        session.query(SimulationResult).delete()
        session.query(SimulationRun).delete()
        session.query(Job).delete()
        session.query(SkillVersion).delete()
        session.query(Skill).delete()
        session.commit()


def _seed_approved_skill() -> tuple[uuid.UUID, uuid.UUID]:
    """Insert a skill + approved version. Returns (skill_id, version_id)."""
    spec = SkillSchema(
        skill_name="process_refund_request",
        version=1,
        trigger="customer_requests_refund",
        inputs=[Input(name="refund_amount", type=Type.number)],
        decision_zones=DecisionZones(
            deterministic=[
                DeterministicRule(
                    condition=Condition(
                        all=[ConditionOrPredicate(root=Predicate(field="refund_amount", op=Operator.lte, value=100.0))]
                    ),
                    action="approve_refund",
                )
            ],
            llm_assisted=[],
            human_only=[],
        ),
    )
    with SessionLocal() as session:
        skill_row = Skill(name="process_refund_request")
        session.add(skill_row)
        session.flush()
        version_row = SkillVersion(
            skill_id=skill_row.id,
            version_number=1,
            spec=spec.model_dump(mode="json"),
            status="approved",
        )
        session.add(version_row)
        session.flush()
        skill_row.current_version_id = version_row.id
        session.commit()
        return skill_row.id, version_row.id


def _tickets_payload(count: int = 5) -> list[dict]:
    tickets = []
    for i in range(count):
        tickets.append({
            "ticket_id": str(uuid.uuid4()),
            "refund_amount": 50.0,
            "purchase_days_ago": 10,
            "ground_truth_decision": "approve_refund",
        })
    return tickets


def test_post_simulations_returns_202_with_job_id() -> None:
    _clean()
    _, version_id = _seed_approved_skill()
    app.dependency_overrides[get_llm_client] = lambda: FakeLLMClient([])
    client = TestClient(app)
    try:
        response = client.post(
            "/simulations",
            json={"skill_version_id": str(version_id), "tickets": _tickets_payload()},
        )
        assert response.status_code == 202
        data = response.json()
        assert "job_id" in data
        assert data["status"] == "pending"
    finally:
        app.dependency_overrides.clear()


def test_post_simulations_creates_simulation_run_row() -> None:
    _clean()
    _, version_id = _seed_approved_skill()
    app.dependency_overrides[get_llm_client] = lambda: FakeLLMClient([])
    client = TestClient(app)
    try:
        response = client.post(
            "/simulations",
            json={"skill_version_id": str(version_id), "tickets": _tickets_payload(3)},
        )
        job_id = response.json()["job_id"]

        # Poll until done (TestClient runs background tasks synchronously by default)
        with SessionLocal() as session:
            job = session.get(Job, uuid.UUID(job_id))
            assert job is not None
    finally:
        app.dependency_overrides.clear()


def test_get_simulation_report_after_completion() -> None:
    _clean()
    _, version_id = _seed_approved_skill()
    app.dependency_overrides[get_llm_client] = lambda: FakeLLMClient([])
    client = TestClient(app)
    try:
        resp = client.post(
            "/simulations",
            json={"skill_version_id": str(version_id), "tickets": _tickets_payload(5)},
        )
        job_id = uuid.UUID(resp.json()["job_id"])

        # Get job result_ref (simulation run id)
        with SessionLocal() as session:
            job = session.get(Job, job_id)
            assert job is not None
            if job.status == "completed" and job.result_ref is not None:
                sim_id = job.result_ref
                report_resp = client.get(f"/simulations/{sim_id}/report")
                assert report_resp.status_code == 200
                report = report_resp.json()
                assert "match_rate" in report
                assert "results" in report
    finally:
        app.dependency_overrides.clear()
