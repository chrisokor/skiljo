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
