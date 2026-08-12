"""Tests for the demo REST client helpers."""

from __future__ import annotations

import builtins
import io
from pathlib import Path
from unittest.mock import Mock

import api_client
from streamlit.testing.v1 import AppTest


def test_detect_cross_document_contradictions_posts_selected_version_ids(
    monkeypatch,
) -> None:
    response = Mock()
    response.json.return_value = [{"decision_surface": "refund eligibility"}]
    post = Mock(return_value=response)
    monkeypatch.setattr(api_client.requests, "post", post)

    result = api_client.detect_cross_document_contradictions(["version-1", "version-2"])

    assert result == [{"decision_surface": "refund eligibility"}]
    post.assert_called_once_with(
        f"{api_client.API_BASE}/cross-document-contradictions",
        json={"skill_version_ids": ["version-1", "version-2"]},
        headers=api_client.get_headers(),
        timeout=60,
    )
    response.raise_for_status.assert_called_once_with()


def test_get_simulation_report_html_fetches_report_endpoint(monkeypatch) -> None:
    response = Mock()
    response.text = "<!doctype html><title>Skiljo report</title>"
    get = Mock(return_value=response)
    monkeypatch.setattr(api_client.requests, "get", get)

    result = api_client.get_simulation_report_html("simulation-1")

    assert result == "<!doctype html><title>Skiljo report</title>"
    get.assert_called_once_with(
        f"{api_client.API_BASE}/simulations/simulation-1/report.html",
        headers=api_client.get_headers(),
        timeout=30,
    )
    response.raise_for_status.assert_called_once_with()


def test_cross_document_page_limits_second_selection_to_a_different_skill(monkeypatch) -> None:
    skills = [
        {"id": "skill-1", "name": "Terms of Service"},
        {"id": "skill-2", "name": "Help Center"},
    ]
    versions = {
        "skill-1": [
            {"id": "version-1", "version_number": 1, "status": "approved", "spec": {}},
            {"id": "version-2", "version_number": 2, "status": "approved", "spec": {}},
        ],
        "skill-2": [{"id": "version-2", "version_number": 1, "status": "approved", "spec": {}}],
    }
    monkeypatch.setattr(api_client, "list_skills", lambda: skills)
    monkeypatch.setattr(api_client, "get_skill_versions", lambda skill_id: versions[skill_id])

    page = AppTest.from_file("packages/demo/src/pages/4_Cross_Document.py").run(timeout=10)

    assert not page.exception
    assert [selectbox.label for selectbox in page.selectbox] == ["Policy 1", "Policy 2"]
    assert page.selectbox[1].options == ["Help Center (v1)"]


def test_simulate_page_links_to_cross_document_detection(monkeypatch) -> None:
    monkeypatch.setattr(api_client, "list_skills", lambda: [{"id": "skill-1", "name": "Refunds"}])
    monkeypatch.setattr(
        api_client,
        "get_skill_versions",
        lambda _skill_id: [{"id": "version-1", "version_number": 1, "status": "approved", "spec": {}}],
    )
    original_open = builtins.open

    def open_ticket_fixture(file, *args, **kwargs):
        if str(file).endswith("tickets.json"):
            return io.StringIO("[]")
        return original_open(file, *args, **kwargs)

    monkeypatch.setattr(Path, "exists", lambda _path: True)
    monkeypatch.setattr(builtins, "open", open_ticket_fixture)

    page = AppTest.from_file("packages/demo/src/pages/3_Simulate.py").run(timeout=10)

    assert not page.exception
    assert any("Cross-Document Detection" in markdown.value for markdown in page.markdown)
