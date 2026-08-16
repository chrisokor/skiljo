"""Tests for the eval baseline refresh mechanism (plan #58).

Verifies ``skiljo_core.eval.baseline.update_baseline`` writes the flat
``{metric_name: float}`` shape ``skiljo_core.eval.regression`` (the PR-time
regression gate) expects, and that ``main()`` wires the CLI the same way
``scripts/update_baseline.py`` invokes it from CI.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from skiljo_core.eval.baseline import DEFAULT_BASELINE_PATH, main, update_baseline
from skiljo_core.eval.collect_metrics import collect_all_metrics
from skiljo_core.eval.regression import load_metrics


def test_update_baseline_writes_flat_metrics(tmp_path: Path) -> None:
    output_path = tmp_path / "baseline_metrics.json"

    metrics = update_baseline(output_path=output_path)

    written = json.loads(output_path.read_text())
    assert written == metrics
    assert all(isinstance(v, float) for v in written.values())
    assert written.keys() >= {
        "extraction_recall",
        "citation_resolution",
        "simulation_match_rate",
        "contradiction_recall",
        "e2e_accuracy",
    }


def test_committed_baseline_matches_explicit_offline_metrics() -> None:
    with pytest.warns(RuntimeWarning, match="requires an injected LLMClient"):
        current_metrics = collect_all_metrics()

    assert load_metrics(DEFAULT_BASELINE_PATH) == current_metrics


def test_update_baseline_is_flat_no_metadata_wrapper(tmp_path: Path) -> None:
    # regression.load_metrics / baseline_metrics_from_git load this file directly
    # as dict[str, float] -- a "metrics" wrapper key or timestamp/commit_sha field
    # mixed in would silently break every regression check (metric no longer found
    # in baseline -> treated as "no baseline to compare", not a regression).
    output_path = tmp_path / "baseline_metrics.json"

    update_baseline(output_path=output_path)

    written = json.loads(output_path.read_text())
    assert "metrics" not in written
    assert "timestamp" not in written
    assert "commit_sha" not in written


def test_update_baseline_overwrites_stale_metrics(tmp_path: Path) -> None:
    output_path = tmp_path / "baseline_metrics.json"
    output_path.write_text(json.dumps({"stale_metric": 0.1}))

    update_baseline(output_path=output_path)

    written = json.loads(output_path.read_text())
    assert "stale_metric" not in written


def test_main_writes_metrics_to_output_path(tmp_path: Path) -> None:
    output_path = tmp_path / "baseline_metrics.json"

    exit_code = main(["--output", str(output_path)])

    assert exit_code == 0
    written = json.loads(output_path.read_text())
    assert "extraction_recall" in written
