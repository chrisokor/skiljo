"""Tests for GET /simulations/{id}/report.html endpoint (plan #A2)."""
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
from skiljo_core.schemas.simulation_report_schema import (
    Citation,
    Contradiction,
    EstimatedFinancialImpact,
    Result,
    RoiEstimates,
    SimulationReport,
    Zone,
)
from skiljo_core.testing import FakeLLMClient, TEST_CITATION


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
                    citation=TEST_CITATION,
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


def _tickets_payload(count: int = 5, ground_truth_decision: str = "approve_refund") -> list[dict]:
    tickets = []
    for i in range(count):
        tickets.append({
            "ticket_id": str(uuid.uuid4()),
            "refund_amount": 50.0,
            "purchase_days_ago": 10,
            "ground_truth_decision": ground_truth_decision,
        })
    return tickets


def test_get_report_html_not_found() -> None:
    """Returns 404 for a non-existent simulation ID."""
    client = TestClient(app)
    nonexistent = str(uuid.uuid4())
    response = client.get(f"/simulations/{nonexistent}/report.html")
    assert response.status_code == 404


def test_get_report_html_not_completed() -> None:
    """Returns 409 when simulation exists but is still pending."""
    _clean()
    _, version_id = _seed_approved_skill()

    # Insert a pending SimulationRun directly (no background task)
    with SessionLocal() as session:
        sim_run = SimulationRun(
            skill_version_id=version_id,
            ticket_batch_id=uuid.uuid4(),
            status="pending",
            summary=None,
        )
        session.add(sim_run)
        session.commit()
        sim_id = sim_run.id

    client = TestClient(app)
    response = client.get(f"/simulations/{sim_id}/report.html")
    assert response.status_code == 409


def test_get_report_html_returns_html_content_type() -> None:
    """Returns 200 with text/html content type for a completed simulation."""
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

        with SessionLocal() as session:
            job = session.get(Job, job_id)
            assert job is not None
            assert job.status == "completed", f"Job failed: {job.error}"
            sim_id = job.result_ref

        html_resp = client.get(f"/simulations/{sim_id}/report.html")
        assert html_resp.status_code == 200
        assert "text/html" in html_resp.headers["content-type"]
    finally:
        app.dependency_overrides.clear()


def test_get_report_html_contains_key_sections() -> None:
    """The rendered HTML includes summary metrics, contradictions section, and ticket table."""
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

        with SessionLocal() as session:
            job = session.get(Job, job_id)
            assert job is not None
            assert job.status == "completed", f"Job failed: {job.error}"
            sim_id = job.result_ref

        html_resp = client.get(f"/simulations/{sim_id}/report.html")
        assert html_resp.status_code == 200
        body = html_resp.text

        # Executive summary section
        assert "Executive Summary" in body
        assert "Match Rate" in body
        assert "Escalation Accuracy" in body

        # Contradictions section heading
        assert "Contradictions Detected" in body

        # Per-ticket table
        assert "Per-Ticket Results" in body
        assert "<table" in body
        assert "Ticket ID" in body
    finally:
        app.dependency_overrides.clear()


def test_get_report_html_match_rate_rendered() -> None:
    """Match rate is rendered as a percentage value in the HTML."""
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

        with SessionLocal() as session:
            job = session.get(Job, job_id)
            assert job is not None
            assert job.status == "completed", f"Job failed: {job.error}"
            sim_id = job.result_ref

        html_resp = client.get(f"/simulations/{sim_id}/report.html")
        assert html_resp.status_code == 200
        body = html_resp.text

        # All 5 tickets should match (refund_amount=50 <= 100, decision=approve_refund)
        assert "100.0%" in body
    finally:
        app.dependency_overrides.clear()


def test_get_report_html_renders_diagnostic_evidence_and_roi() -> None:
    """Renders contradiction citations, financial impact, ROI, and ticket evidence."""
    _clean()
    _, version_id = _seed_approved_skill()
    ticket_id = uuid.uuid4()
    summary = SimulationReport(
        skill_version_id=version_id,
        match_rate=0.8,
        escalation_accuracy=0.5,
        automation_candidate_count=4,
        results=[
            Result(
                ticket_id=ticket_id,
                decision="approve_refund",
                zone=Zone.deterministic,
                matched_human_decision=False,
                reasoning="VIP exception applied",
            )
        ],
        contradictions=[
            Contradiction(
                cluster_key={"amount_band": "101-200", "customer_segment": "vip"},
                written_decision="deny_refund",
                observed_decision="approve_refund",
                frequency=0.75,
                ticket_count=12,
                affected_ticket_ids=[str(ticket_id)],
                citation=Citation(
                    policy_id="refund-policy",
                    rule_id="rule-7",
                    span_start=10,
                    span_end=42,
                    quoted_text="Refunds are unavailable after 30 days.",
                ),
                estimated_financial_impact=EstimatedFinancialImpact(
                    divergent_ticket_count=9,
                    average_refund_amount=125.0,
                    estimated_impact_usd=1125.0,
                ),
            )
        ],
        roi_estimates=RoiEstimates(
            automation_safe_volume=4,
            manual_review_hours_per_month=3.5,
            estimated_value_usd=420.0,
        ),
    )
    with SessionLocal() as session:
        sim_run = SimulationRun(
            skill_version_id=version_id,
            ticket_batch_id=uuid.uuid4(),
            status="completed",
            summary=summary.model_dump(mode="json"),
        )
        session.add(sim_run)
        session.commit()
        sim_id = sim_run.id

    response = TestClient(app).get(f"/simulations/{sim_id}/report.html")

    assert response.status_code == 200
    body = response.text
    assert "Contradictions Detected" in body
    assert "Refunds are unavailable after 30 days." in body
    assert "Affected segment" in body
    assert "vip" in body
    assert "$1,125.00" in body
    assert "Automation Candidates" in body
    assert "Manual review hours saved per month" in body
    assert "Missed Escalations and Over-Approvals" in body
    assert "Per-Ticket Results" in body
    assert str(ticket_id) in body
    assert "VIP exception applied" in body


def test_completed_simulation_report_preserves_contradiction_citation() -> None:
    """Detector output is persisted with the cited source rule for the HTML report."""
    _clean()
    _, version_id = _seed_approved_skill()
    app.dependency_overrides[get_llm_client] = lambda: FakeLLMClient([])
    client = TestClient(app)
    try:
        response = client.post(
            "/simulations",
            json={
                "skill_version_id": str(version_id),
                "tickets": _tickets_payload(5, ground_truth_decision="deny_refund"),
            },
        )
        job_id = uuid.UUID(response.json()["job_id"])
        with SessionLocal() as session:
            job = session.get(Job, job_id)
            assert job is not None
            assert job.status == "completed", f"Job failed: {job.error}"
            sim_id = job.result_ref

        report = client.get(f"/simulations/{sim_id}/report").json()

        assert report["contradiction_count"] == 1
        assert report["contradictions"][0]["citation"]["quoted_text"] == "x"
    finally:
        app.dependency_overrides.clear()
