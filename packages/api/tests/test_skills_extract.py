import uuid

from fastapi.testclient import TestClient

from skiljo_core.testing import FakeLLMClient

from skiljo_api.dependencies import get_llm_client
from skiljo_api.main import app
from skiljo_core.db.models import Job, Policy, Skill, SkillVersion, SimulationResult, SimulationRun
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


def _clean_tables() -> None:
    with SessionLocal() as session:
        session.query(SimulationResult).delete()
        session.query(SimulationRun).delete()
        session.query(SkillVersion).delete()
        session.query(Skill).delete()
        session.query(Job).delete()
        session.query(Policy).delete()
        session.commit()


def test_extract_endpoint_creates_draft_skill_version() -> None:
    _clean_tables()
    fake_client = FakeLLMClient(
        [
            SegmentationResult(
                segments=[
                    Segment(segment_type="thresholds", text="Refunds under $100 within 30 days are approved.")
                ]
            ),
            CandidateRuleList(
                rules=[
                    DeterministicRule(
                        condition=Condition(all=[ConditionOrPredicate(root=Predicate(field="refund_amount", op=Operator.lt, value=100))]),
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
    try:
        client = TestClient(app)
        response = client.post(
            "/skills/extract",
            json={
                "policy_text": "Refunds under $100 within 30 days are approved.",
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
            assert version.status == "draft"
            assert version.spec["skill_name"] == "process_refund_request"
            assert len(version.spec["decision_zones"]["deterministic"]) == 1
            skill_obj = session.get(Skill, version.skill_id)
            assert skill_obj is not None
            assert skill_obj.current_version_id == version.id
    finally:
        app.dependency_overrides.clear()


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


def test_extract_endpoint_rejects_both_policy_sources() -> None:
    client = TestClient(app)

    response = client.post(
        "/skills/extract",
        json={
            "policy_id": str(uuid.uuid4()),
            "policy_text": "Refunds are approved.",
            "skill_name": "process_refund_request",
            "trigger": "customer_requests_refund",
        },
    )

    assert response.status_code == 422
    errors = response.json()["error"]["details"]["errors"]
    assert any("exactly one" in error["msg"].lower() for error in errors)


def test_extract_endpoint_rejects_missing_policy_source() -> None:
    client = TestClient(app)

    response = client.post(
        "/skills/extract",
        json={
            "skill_name": "process_refund_request",
            "trigger": "customer_requests_refund",
        },
    )

    assert response.status_code == 422
    errors = response.json()["error"]["details"]["errors"]
    assert any("exactly one" in error["msg"].lower() for error in errors)
