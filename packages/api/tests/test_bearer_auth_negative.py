"""Negative tests for bearer auth: every conftest fixture bypasses auth for
convenience, so these tests deliberately undo that bypass to exercise the
real `verify_api_key` dependency end to end.
"""

from fastapi.testclient import TestClient

from skiljo_api import dependencies
from skiljo_api.dependencies import verify_api_key
from skiljo_api.main import app


def test_unauthenticated_request_rejected() -> None:
    """POST to a protected endpoint without an Authorization header returns 401."""
    app.dependency_overrides.pop(verify_api_key, None)
    try:
        client = TestClient(app)
        response = client.post(
            "/skills/extract",
            json={"policy_text": "test", "skill_name": "s", "trigger": "t"},
        )
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "unauthorized"
    finally:
        app.dependency_overrides[verify_api_key] = lambda: None


def test_invalid_api_key_rejected(monkeypatch) -> None:
    """POST with a wrong bearer token returns 401 (real key configured, wrong one sent)."""
    monkeypatch.setattr(dependencies.config, "API_KEY", "the-real-key")
    app.dependency_overrides.pop(verify_api_key, None)
    try:
        client = TestClient(app)
        response = client.post(
            "/skills/extract",
            json={"policy_text": "test", "skill_name": "s", "trigger": "t"},
            headers={"Authorization": "Bearer wrongkey123"},
        )
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "unauthorized"
    finally:
        app.dependency_overrides[verify_api_key] = lambda: None
