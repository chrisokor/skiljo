"""Tests for the demo REST client helpers."""

from __future__ import annotations

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


def test_cross_document_page_loads_with_approved_versions(monkeypatch) -> None:
    skills = [
        {"id": "skill-1", "name": "Terms of Service"},
        {"id": "skill-2", "name": "Help Center"},
    ]
    versions = {
        "skill-1": [{"id": "version-1", "version_number": 1, "status": "approved", "spec": {}}],
        "skill-2": [{"id": "version-2", "version_number": 1, "status": "approved", "spec": {}}],
    }
    monkeypatch.setattr(api_client, "list_skills", lambda: skills)
    monkeypatch.setattr(api_client, "get_skill_versions", lambda skill_id: versions[skill_id])

    page = AppTest.from_file("packages/demo/src/pages/4_Cross_Document.py").run(timeout=10)

    assert not page.exception
    assert [selectbox.label for selectbox in page.selectbox] == ["Policy 1", "Policy 2"]
