import uuid

from fastapi.testclient import TestClient

from skiljo_api.dependencies import get_llm_client
from skiljo_api.main import app
from skiljo_core.db.models import Job, Policy, Skill, SkillVersion, SimulationResult, SimulationRun
from skiljo_core.db.session import SessionLocal
from skiljo_core.schemas.rule_schema import (
    Condition,
    ConditionOrPredicate,
    DeterministicRule,
    HumanOnlyRule,
    Operator,
    Predicate,
)
from skiljo_core.schemas.skill_schema import DecisionZones, Input, Skill as SkillSchema, Type
from skiljo_core.simulation.cross_document import ConflictCheck, DecisionSurfaceClassification
from skiljo_core.testing import FakeLLMClient


def _clean() -> None:
    with SessionLocal() as session:
        session.query(SimulationResult).delete()
        session.query(SimulationRun).delete()
        session.query(Job).delete()
        session.query(SkillVersion).delete()
        session.query(Skill).delete()
        session.query(Policy).delete()
        session.commit()


def _condition() -> Condition:
    return Condition(
        all=[ConditionOrPredicate(root=Predicate(field="days_since_purchase", op=Operator.gt, value=0))]
    )


def _seed_skill_version(policy_id: uuid.UUID | None, action: str, zone: str) -> uuid.UUID:
    deterministic = [DeterministicRule(condition=_condition(), action=action)] if zone == "deterministic" else []
    human_only = [HumanOnlyRule(condition=_condition(), action=action)] if zone == "human_only" else []
    spec = SkillSchema(
        skill_name="process_refund_request",
        version=1,
        trigger="customer_requests_refund",
        inputs=[Input(name="days_since_purchase", type=Type.integer)],
        decision_zones=DecisionZones(deterministic=deterministic, llm_assisted=[], human_only=human_only),
    )
    with SessionLocal() as session:
        skill_row = Skill(name="process_refund_request")
        session.add(skill_row)
        session.flush()
        version_row = SkillVersion(
            skill_id=skill_row.id,
            version_number=1,
            spec=spec.model_dump(mode="json"),
            source_policy_id=policy_id,
            status="approved",
        )
        session.add(version_row)
        session.flush()
        skill_row.current_version_id = version_row.id
        session.commit()
        return version_row.id


def test_cross_document_endpoint_detects_shopify_style_conflict() -> None:
    _clean()
    with SessionLocal() as session:
        tos_policy = Policy(raw_text="Shopify plan fees are non-refundable.")
        help_policy = Policy(raw_text="Refund requests are reviewed case by case.")
        session.add_all([tos_policy, help_policy])
        session.commit()
        tos_policy_id, help_policy_id = tos_policy.id, help_policy.id

    tos_version_id = _seed_skill_version(tos_policy_id, "deny_refund_no_refunds_policy", "deterministic")
    help_version_id = _seed_skill_version(help_policy_id, "escalate_case_by_case_review", "human_only")

    fake_client = FakeLLMClient(
        [
            DecisionSurfaceClassification(decision_surface="refund_eligibility"),
            DecisionSurfaceClassification(decision_surface="refund_eligibility"),
            ConflictCheck(is_conflict=True, rationale="ToS forbids refunds; help center reviews case by case."),
        ]
    )
    app.dependency_overrides[get_llm_client] = lambda: fake_client
    try:
        client = TestClient(app)
        response = client.post(
            "/cross-document-contradictions",
            json={"skill_version_ids": [str(tos_version_id), str(help_version_id)]},
        )
        assert response.status_code == 200
        body = response.json()
        assert len(body) == 1
        contradiction = body[0]
        assert contradiction["decision_surface"] == "refund_eligibility"
        assert {contradiction["policy_1"], contradiction["policy_2"]} == {str(tos_policy_id), str(help_policy_id)}
        assert {contradiction["action_1"], contradiction["action_2"]} == {
            "deny_refund_no_refunds_policy",
            "escalate_case_by_case_review",
        }
    finally:
        app.dependency_overrides.clear()


def test_cross_document_endpoint_requires_at_least_two_versions() -> None:
    _clean()
    version_id = _seed_skill_version(None, "approve_refund", "deterministic")
    app.dependency_overrides[get_llm_client] = lambda: FakeLLMClient([])
    try:
        client = TestClient(app)
        response = client.post(
            "/cross-document-contradictions",
            json={"skill_version_ids": [str(version_id)]},
        )
        assert response.status_code == 400
    finally:
        app.dependency_overrides.clear()


def test_cross_document_endpoint_404s_on_missing_version() -> None:
    _clean()
    version_id = _seed_skill_version(None, "approve_refund", "deterministic")
    app.dependency_overrides[get_llm_client] = lambda: FakeLLMClient([])
    try:
        client = TestClient(app)
        response = client.post(
            "/cross-document-contradictions",
            json={"skill_version_ids": [str(version_id), str(uuid.uuid4())]},
        )
        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()
