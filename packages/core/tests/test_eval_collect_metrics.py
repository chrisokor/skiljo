"""Tests for the eval metrics collector (plan #52).

Runs the real Inspect eval Tasks (extraction, simulation, e2e) against the offline
``mockllm/model`` provider (no network access or API key needed) and checks the
metrics get flattened and written out under the Section 9 metric names.
"""

from __future__ import annotations

import json
from pathlib import Path

from skiljo_core.eval.collect_metrics import (
    collect_all_metrics,
    collect_e2e_metrics,
    collect_extraction_metrics,
    collect_simulation_metrics,
    main,
)


def test_collect_extraction_metrics_returns_section9_names() -> None:
    metrics = collect_extraction_metrics()

    assert "extraction_recall" in metrics
    assert "citation_resolution" in metrics
    assert all(isinstance(v, float) for v in metrics.values())


def test_collect_simulation_metrics_returns_section9_names() -> None:
    metrics = collect_simulation_metrics()

    assert "simulation_match_rate" in metrics
    assert "contradiction_recall" in metrics
    assert "contradiction_precision" in metrics


def test_collect_e2e_metrics_returns_section9_names() -> None:
    metrics = collect_e2e_metrics()

    assert "e2e_accuracy" in metrics


def test_collect_all_metrics_merges_every_suite() -> None:
    metrics = collect_all_metrics()

    assert metrics.keys() >= {
        "extraction_recall",
        "citation_resolution",
        "simulation_match_rate",
        "contradiction_recall",
        "e2e_accuracy",
    }


def test_main_writes_metrics_json(tmp_path: Path) -> None:
    output_path = tmp_path / "eval-results.json"

    exit_code = main(["--output", str(output_path)])

    assert exit_code == 0
    written = json.loads(output_path.read_text())
    assert written.keys() >= {
        "extraction_recall",
        "citation_resolution",
        "simulation_match_rate",
        "contradiction_recall",
        "e2e_accuracy",
    }
