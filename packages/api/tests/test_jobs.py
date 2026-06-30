import uuid

from fastapi.testclient import TestClient

from skiljo_api.main import app
from skiljo_core.db.models import Job
from skiljo_core.db.session import SessionLocal


def _clean_jobs() -> None:
    with SessionLocal() as session:
        session.query(Job).delete()
        session.commit()


def test_get_job_returns_status_and_result_ref() -> None:
    _clean_jobs()
    result_ref = uuid.uuid4()
    with SessionLocal() as session:
        job = Job(kind="extraction", status="completed", result_ref=result_ref)
        session.add(job)
        session.commit()
        job_id = job.id

    client = TestClient(app)
    response = client.get(f"/jobs/{job_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["job_id"] == str(job_id)
    assert body["status"] == "completed"
    assert body["result_ref"] == str(result_ref)
    assert body["error"] is None


def test_get_job_404_for_unknown_id() -> None:
    client = TestClient(app)
    response = client.get(f"/jobs/{uuid.uuid4()}")
    assert response.status_code == 404
