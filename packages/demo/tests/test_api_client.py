"""Tests for the demo REST client helpers."""

from __future__ import annotations

from unittest.mock import Mock

import api_client


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
