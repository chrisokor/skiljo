import uuid

from fastapi.testclient import TestClient

from skiljo_api.main import app
from skiljo_core.db.models import Skill, SkillVersion, SimulationResult, SimulationRun
from skiljo_core.db.session import SessionLocal


def _clean_tables() -> None:
    with SessionLocal() as session:
        session.query(SimulationResult).delete()
        session.query(SimulationRun).delete()
        session.query(SkillVersion).delete()
        session.query(Skill).delete()
        session.commit()


def _seed_draft_version() -> tuple[uuid.UUID, uuid.UUID]:
    with SessionLocal() as session:
        skill = Skill(name="process_refund_request")
        session.add(skill)
        session.flush()
        version = SkillVersion(
            skill_id=skill.id,
            version_number=1,
            spec={"skill_name": "process_refund_request"},
            status="draft",
        )
        session.add(version)
        session.commit()
        return skill.id, version.id


def test_approve_version_changes_status_to_approved() -> None:
    _clean_tables()
    skill_id, version_id = _seed_draft_version()

    client = TestClient(app)
    response = client.patch(f"/skills/{skill_id}/versions/{version_id}/approve")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(version_id)
    assert data["status"] == "approved"


def test_approve_version_persists_to_db() -> None:
    _clean_tables()
    skill_id, version_id = _seed_draft_version()

    client = TestClient(app)
    client.patch(f"/skills/{skill_id}/versions/{version_id}/approve")

    with SessionLocal() as session:
        version = session.get(SkillVersion, version_id)
        assert version is not None
        assert version.status == "approved"


def test_approve_version_404_for_unknown_version() -> None:
    _clean_tables()
    skill_id, _ = _seed_draft_version()

    client = TestClient(app)
    response = client.patch(f"/skills/{skill_id}/versions/{uuid.uuid4()}/approve")

    assert response.status_code == 404


def test_approve_version_404_for_unknown_skill() -> None:
    client = TestClient(app)
    response = client.patch(f"/skills/{uuid.uuid4()}/versions/{uuid.uuid4()}/approve")

    assert response.status_code == 404
