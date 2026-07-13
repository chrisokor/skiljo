"""End-to-end integration test: upload policy → extract skill → run simulation → fetch reports.

Marked to skip unless INTEGRATION=1 env var is set, because it makes real Anthropic API calls.
Run against a local API server:

    API_KEY=<key> uvicorn skiljo_api.main:app --port 8000 &
    INTEGRATION=1 API_KEY=<key> API_BASE_URL=http://localhost:8000 pytest packages/api/tests/test_e2e_integration.py -v
"""
import os
import time
import uuid

import pytest
import requests

INTEGRATION = os.environ.get("INTEGRATION", "0") == "1"
API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000")
API_KEY = os.environ.get("API_KEY", "")

POLICY_TEXT = """
Refund Policy

1. Refunds are approved automatically when the refund amount is $100 or less and the purchase
   was made within 30 days.
2. Refunds over $100 require human review regardless of purchase date.
3. Any refund request flagged for fraud is denied immediately.
""".strip()

SKILL_NAME = "process_refund_request"
TRIGGER = "customer_requests_refund"

POLL_MAX_ITERATIONS = 120  # 120 seconds timeout
POLL_SLEEP_SECONDS = 1


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {API_KEY}"}


def _poll_job(job_id: str) -> dict:
    """Poll GET /jobs/{id} until status is completed or failed (or timeout)."""
    for _ in range(POLL_MAX_ITERATIONS):
        resp = requests.get(f"{API_BASE_URL}/jobs/{job_id}", headers=_headers())
        assert resp.status_code == 200, f"Job poll failed: {resp.status_code} {resp.text}"
        data = resp.json()
        status = data["status"]
        if status == "completed":
            return data
        if status == "failed":
            pytest.fail(f"Job {job_id} failed: {data.get('error')}")
        time.sleep(POLL_SLEEP_SECONDS)
    pytest.fail(f"Job {job_id} did not complete within {POLL_MAX_ITERATIONS} seconds")


@pytest.mark.skipif(not INTEGRATION, reason="Set INTEGRATION=1 to run real API integration tests")
def test_full_workflow_upload_extract_simulate_report() -> None:
    """
    Full end-to-end workflow:
      1. Extract a skill from a policy text
      2. Poll until extraction job completes
      3. Approve the extracted skill version
      4. Run a simulation against the approved skill
      5. Poll until simulation job completes
      6. Fetch the JSON report and verify structure
      7. Fetch the HTML report and verify output
    """
    # ── Step 1: Extract skill from policy text ──────────────────────────────
    extract_resp = requests.post(
        f"{API_BASE_URL}/skills/extract",
        headers=_headers(),
        json={
            "policy_text": POLICY_TEXT,
            "skill_name": SKILL_NAME,
            "trigger": TRIGGER,
        },
    )
    assert extract_resp.status_code == 202, (
        f"Expected 202 from /skills/extract, got {extract_resp.status_code}: {extract_resp.text}"
    )
    extract_data = extract_resp.json()
    assert "job_id" in extract_data
    assert extract_data["status"] == "pending"
    extraction_job_id = extract_data["job_id"]

    # ── Step 2: Poll extraction job until completed ─────────────────────────
    extraction_job = _poll_job(extraction_job_id)
    assert extraction_job["status"] == "completed"
    version_id = extraction_job["result_ref"]
    assert version_id is not None, "Extraction job completed but result_ref is None"

    # ── Step 3: Fetch the extracted skill and verify structure ──────────────
    # Find the skill via the version's skill_id by listing skills
    skills_resp = requests.get(f"{API_BASE_URL}/skills", headers=_headers())
    assert skills_resp.status_code == 200
    skills = skills_resp.json()
    assert len(skills) >= 1, "Expected at least one skill after extraction"

    skill_entry = next((s for s in skills if s["current_version_id"] == version_id), None)
    assert skill_entry is not None, f"Could not find skill with current_version_id={version_id}"
    skill_id = skill_entry["id"]
    assert skill_entry["name"] == SKILL_NAME

    # Verify GET /skills/{id} returns the skill
    skill_resp = requests.get(f"{API_BASE_URL}/skills/{skill_id}", headers=_headers())
    assert skill_resp.status_code == 200
    skill_data = skill_resp.json()
    assert skill_data["name"] == SKILL_NAME
    assert skill_data["current_version_id"] == version_id

    # Verify versions list contains the extracted version
    versions_resp = requests.get(f"{API_BASE_URL}/skills/{skill_id}/versions", headers=_headers())
    assert versions_resp.status_code == 200
    versions = versions_resp.json()
    assert len(versions) >= 1
    extracted_version = next((v for v in versions if v["id"] == version_id), None)
    assert extracted_version is not None
    assert extracted_version["status"] == "draft"
    spec = extracted_version["spec"]
    assert "decision_zones" in spec
    assert "skill_name" in spec

    # ── Step 4: Approve the skill version ───────────────────────────────────
    approve_resp = requests.patch(
        f"{API_BASE_URL}/skills/{skill_id}/versions/{version_id}/approve",
        headers=_headers(),
    )
    assert approve_resp.status_code == 200, (
        f"Expected 200 from approve, got {approve_resp.status_code}: {approve_resp.text}"
    )
    approved = approve_resp.json()
    assert approved["status"] == "approved"

    # ── Step 5: Run simulation on a small synthetic ticket batch ────────────
    tickets = [
        {
            "ticket_id": str(uuid.uuid4()),
            "refund_amount": 50.0,
            "purchase_days_ago": 10,
            "customer_segment": "standard",
            "fraud_flags": [],
            "refund_reason": "defective",
            "ground_truth_decision": "approve_refund",
        },
        {
            "ticket_id": str(uuid.uuid4()),
            "refund_amount": 200.0,
            "purchase_days_ago": 5,
            "customer_segment": "standard",
            "fraud_flags": [],
            "refund_reason": "changed_mind",
            "ground_truth_decision": "human_review",
        },
        {
            "ticket_id": str(uuid.uuid4()),
            "refund_amount": 75.0,
            "purchase_days_ago": 45,
            "customer_segment": "standard",
            "fraud_flags": ["suspected_fraud"],
            "refund_reason": "defective",
            "ground_truth_decision": "deny_refund",
        },
    ]

    sim_resp = requests.post(
        f"{API_BASE_URL}/simulations",
        headers=_headers(),
        json={"skill_version_id": version_id, "tickets": tickets},
    )
    assert sim_resp.status_code == 202, (
        f"Expected 202 from /simulations, got {sim_resp.status_code}: {sim_resp.text}"
    )
    sim_data = sim_resp.json()
    assert "job_id" in sim_data
    assert sim_data["status"] == "pending"
    simulation_job_id = sim_data["job_id"]

    # ── Step 6: Poll simulation job until completed ─────────────────────────
    simulation_job = _poll_job(simulation_job_id)
    assert simulation_job["status"] == "completed"
    sim_run_id = simulation_job["result_ref"]
    assert sim_run_id is not None, "Simulation job completed but result_ref is None"

    # ── Step 7: Fetch the JSON report and verify structure ──────────────────
    report_resp = requests.get(f"{API_BASE_URL}/simulations/{sim_run_id}/report", headers=_headers())
    assert report_resp.status_code == 200, (
        f"Expected 200 from /simulations/{sim_run_id}/report, got {report_resp.status_code}: {report_resp.text}"
    )
    report = report_resp.json()
    assert "match_rate" in report, "Report missing 'match_rate' field"
    assert "escalation_accuracy" in report, "Report missing 'escalation_accuracy' field"
    assert "results" in report, "Report missing 'results' field"
    assert isinstance(report["match_rate"], float), "match_rate should be a float"
    assert 0.0 <= report["match_rate"] <= 1.0, "match_rate must be in [0, 1]"
    assert isinstance(report["results"], list), "results should be a list"
    assert len(report["results"]) == len(tickets), (
        f"Expected {len(tickets)} results, got {len(report['results'])}"
    )

    # ── Step 8: Fetch the HTML report and verify output ─────────────────────
    html_resp = requests.get(f"{API_BASE_URL}/simulations/{sim_run_id}/report.html", headers=_headers())
    assert html_resp.status_code == 200, (
        f"Expected 200 from /simulations/{sim_run_id}/report.html, got {html_resp.status_code}: {html_resp.text}"
    )
    assert "text/html" in html_resp.headers.get("content-type", ""), (
        f"Expected text/html content-type, got {html_resp.headers.get('content-type')}"
    )
    html_body = html_resp.text
    assert "<html" in html_body.lower(), "HTML report should contain an <html> element"
    assert "Executive Summary" in html_body, "HTML report missing 'Executive Summary' section"
    assert "Match Rate" in html_body, "HTML report missing 'Match Rate'"
    assert "Contradictions Detected" in html_body, "HTML report missing 'Contradictions Detected' section"
    assert "Per-Ticket Results" in html_body, "HTML report missing 'Per-Ticket Results' section"
