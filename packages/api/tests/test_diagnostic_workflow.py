import io
import uuid

from fastapi.testclient import TestClient

from skiljo_api.dependencies import get_llm_client
from skiljo_api.main import app
from skiljo_core.db.models import (
    Job,
    Policy,
    SimulationResult,
    SimulationRun,
    Skill,
    SkillVersion,
    TicketBatch,
    TicketRecord,
)
from skiljo_core.db.session import SessionLocal
from skiljo_core.extraction.rules import CandidateRuleList
from skiljo_core.extraction.segmentation import Segment, SegmentationResult
from skiljo_core.extraction.zones import ZoneClassification
from skiljo_core.schemas.rule_schema import (
    Citation,
    Condition,
    ConditionOrPredicate,
    DeterministicRule,
    Operator,
    Predicate,
    Span,
)
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
            SegmentationResult(
                segments=[Segment(segment_type="thresholds", text=POLICY_TEXT)]
            ),
            CandidateRuleList(
                rules=[
                    DeterministicRule(
                        condition=Condition(
                            all=[
                                ConditionOrPredicate(
                                    root=Predicate(
                                        field="refund_amount",
                                        op=Operator.lt,
                                        value=100,
                                    )
                                ),
                                ConditionOrPredicate(
                                    root=Predicate(
                                        field="purchase_days_ago",
                                        op=Operator.lte,
                                        value=30,
                                    )
                                ),
                            ]
                        ),
                        action="approve_refund",
                        citation=Citation(
                            span=Span(start=0, end=7), quoted_text="Refunds"
                        ),
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
            json={
                "raw_text": POLICY_TEXT,
                "source_filename": "refund-policy.txt",
            },
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
            assert (
                version.spec["decision_zones"]["deterministic"][0]["citation"][
                    "quoted_text"
                ]
                == "Refunds"
            )
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
            json={
                "skill_version_id": str(version_id),
                "ticket_batch_id": ticket_batch_id,
            },
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
        _clean()
