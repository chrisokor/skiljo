from fastapi.testclient import TestClient

from skiljo_api.main import app
from skiljo_core.db.models import EvalRun
from skiljo_core.db.session import SessionLocal

client = TestClient(app)


def _clean_eval_runs() -> None:
    with SessionLocal() as session:
        session.query(EvalRun).delete()
        session.commit()


def _create(commit_sha: str, dataset_version: str, model: str, metrics: dict) -> dict:
    response = client.post(
        "/eval-runs",
        json={
            "commit_sha": commit_sha,
            "dataset_version": dataset_version,
            "model": model,
            "metrics": metrics,
        },
    )
    assert response.status_code == 201
    return response.json()


def test_record_eval_run_returns_id_and_fields() -> None:
    _clean_eval_runs()
    body = _create("abc123", "v1", "claude-sonnet-4-6", {"recall": 0.9, "citation_resolution": 1.0})

    assert "id" in body
    assert body["commit_sha"] == "abc123"
    assert body["dataset_version"] == "v1"
    assert body["model"] == "claude-sonnet-4-6"
    assert body["metrics"] == {"recall": 0.9, "citation_resolution": 1.0}
    assert body["ran_at"] is not None


def test_record_eval_run_persists_to_db() -> None:
    _clean_eval_runs()
    body = _create("def456", "v1", "claude-sonnet-4-6", {"recall": 0.8})

    with SessionLocal() as session:
        run = session.get(EvalRun, body["id"])
        assert run is not None
        assert run.commit_sha == "def456"
        assert run.metrics == {"recall": 0.8}


def test_record_eval_run_missing_field_returns_422() -> None:
    _clean_eval_runs()
    response = client.post(
        "/eval-runs",
        json={"commit_sha": "abc123", "dataset_version": "v1", "metrics": {}},
    )
    assert response.status_code == 422


def test_list_eval_runs_orders_by_ran_at_desc() -> None:
    _clean_eval_runs()
    first = _create("commit-1", "v1", "claude-sonnet-4-6", {"recall": 0.5})
    second = _create("commit-2", "v1", "claude-sonnet-4-6", {"recall": 0.6})

    response = client.get("/eval-runs")
    assert response.status_code == 200
    body = response.json()

    assert len(body) == 2
    ids_in_order = [row["id"] for row in body]
    assert ids_in_order == [second["id"], first["id"]]


def test_list_eval_runs_filters_by_model() -> None:
    _clean_eval_runs()
    _create("commit-1", "v1", "claude-sonnet-4-6", {"recall": 0.5})
    _create("commit-2", "v1", "claude-haiku-4-6", {"recall": 0.6})

    response = client.get("/eval-runs", params={"model": "claude-haiku-4-6"})
    assert response.status_code == 200
    body = response.json()

    assert len(body) == 1
    assert body[0]["model"] == "claude-haiku-4-6"


def test_list_eval_runs_filters_by_commit_sha() -> None:
    _clean_eval_runs()
    _create("commit-1", "v1", "claude-sonnet-4-6", {"recall": 0.5})
    _create("commit-2", "v1", "claude-sonnet-4-6", {"recall": 0.6})

    response = client.get("/eval-runs", params={"commit_sha": "commit-1"})
    assert response.status_code == 200
    body = response.json()

    assert len(body) == 1
    assert body[0]["commit_sha"] == "commit-1"


def test_list_eval_runs_respects_limit() -> None:
    _clean_eval_runs()
    for i in range(3):
        _create(f"commit-{i}", "v1", "claude-sonnet-4-6", {"recall": 0.5})

    response = client.get("/eval-runs", params={"limit": 2})
    assert response.status_code == 200
    assert len(response.json()) == 2


def test_list_eval_runs_empty() -> None:
    _clean_eval_runs()
    response = client.get("/eval-runs")
    assert response.status_code == 200
    assert response.json() == []
