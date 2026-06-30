import uuid

from fastapi.testclient import TestClient

from skiljo_api.main import app
from skiljo_core.db.models import Skill, SkillVersion
from skiljo_core.db.session import SessionLocal


def _clean_tables() -> None:
    with SessionLocal() as session:
        session.query(SkillVersion).delete()
        session.query(Skill).delete()
        session.commit()


def _seed_skill_with_version() -> tuple[uuid.UUID, uuid.UUID]:
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


def test_list_skills_includes_seeded_skill() -> None:
    _clean_tables()
    skill_id, _ = _seed_skill_with_version()

    client = TestClient(app)
    response = client.get("/skills")

    assert response.status_code == 200
    ids = [row["id"] for row in response.json()]
    assert str(skill_id) in ids


def test_get_skill_returns_detail() -> None:
    _clean_tables()
    skill_id, _ = _seed_skill_with_version()

    client = TestClient(app)
    response = client.get(f"/skills/{skill_id}")

    assert response.status_code == 200
    assert response.json()["name"] == "process_refund_request"


def test_get_skill_404_for_unknown_id() -> None:
    client = TestClient(app)
    response = client.get(f"/skills/{uuid.uuid4()}")
    assert response.status_code == 404


def test_list_skill_versions_includes_seeded_version() -> None:
    _clean_tables()
    skill_id, version_id = _seed_skill_with_version()

    client = TestClient(app)
    response = client.get(f"/skills/{skill_id}/versions")

    assert response.status_code == 200
    versions = response.json()
    assert len(versions) == 1
    assert versions[0]["id"] == str(version_id)
    assert versions[0]["status"] == "draft"
