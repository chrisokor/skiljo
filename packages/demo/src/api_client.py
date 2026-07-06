"""Shared HTTP client helpers for Skiljo demo pages."""

import os

import requests

API_BASE = os.environ.get("SKILJO_API_URL", "http://localhost:8000")
API_KEY = os.environ.get("SKILJO_API_KEY", "test-key")


def get_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {API_KEY}"}


def extract_skill(policy_text: str, skill_name: str, trigger: str) -> str:
    """Submit extraction job, return job_id as str."""
    resp = requests.post(
        f"{API_BASE}/skills/extract",
        json={"policy_text": policy_text, "skill_name": skill_name, "trigger": trigger},
        headers=get_headers(),
        timeout=30,
    )
    resp.raise_for_status()
    return str(resp.json()["job_id"])


def get_job(job_id: str) -> dict:
    """Poll job status. Returns dict with keys: job_id, status, result_ref, error."""
    resp = requests.get(
        f"{API_BASE}/jobs/{job_id}",
        headers=get_headers(),
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def get_skill(skill_id: str) -> dict:
    """Fetch skill summary by skill_version id."""
    resp = requests.get(
        f"{API_BASE}/skills/{skill_id}",
        headers=get_headers(),
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def get_skill_version(skill_id: str, version_id: str) -> dict:
    """Fetch full skill version spec."""
    resp = requests.get(
        f"{API_BASE}/skills/{skill_id}/versions",
        headers=get_headers(),
        timeout=10,
    )
    resp.raise_for_status()
    versions = resp.json()
    for v in versions:
        if str(v["id"]) == str(version_id):
            return v
    return versions[0] if versions else {}


def list_skills() -> list[dict]:
    """List all skills."""
    resp = requests.get(
        f"{API_BASE}/skills",
        headers=get_headers(),
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()
