"""Tests for the eval regression gate (plan #52).

Verifies the pure comparison logic in ``skiljo_core.eval.regression`` that
``scripts/check_regression.py`` wraps for CI.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from skiljo_core.eval.regression import (
    RegressionCheck,
    baseline_metrics_from_git,
    check_metric,
    load_metrics,
    main,
    parse_check_arg,
    run_checks,
)


def test_load_metrics(tmp_path: Path) -> None:
    path = tmp_path / "metrics.json"
    path.write_text(json.dumps({"extraction_recall": 0.9}))

    assert load_metrics(path) == {"extraction_recall": 0.9}


def test_check_metric_passes_within_threshold() -> None:
    check = RegressionCheck(metric="extraction_recall", max_drop=-0.02)
    current = {"extraction_recall": 0.90}
    baseline = {"extraction_recall": 0.91}

    passed, message = check_metric(current, baseline, check)

    assert passed
    assert "PASS" in message


def test_check_metric_fails_beyond_threshold() -> None:
    check = RegressionCheck(metric="extraction_recall", max_drop=-0.02)
    current = {"extraction_recall": 0.80}
    baseline = {"extraction_recall": 0.91}

    passed, message = check_metric(current, baseline, check)

    assert not passed
    assert "FAIL" in message
    assert "regressed" in message


def test_check_metric_passes_when_no_baseline() -> None:
    check = RegressionCheck(metric="extraction_recall", max_drop=-0.02)

    passed, message = check_metric({"extraction_recall": 0.5}, None, check)

    assert passed
    assert "no baseline" in message


def test_check_metric_missing_from_baseline_passes() -> None:
    # A brand-new metric with nothing to compare against should pass, not error.
    check = RegressionCheck(metric="new_metric", max_drop=-0.02)

    passed, _ = check_metric({"new_metric": 0.5}, {"other_metric": 1.0}, check)

    assert passed


def test_check_metric_require_min_fails_even_without_drop() -> None:
    # citation_resolution must be exactly 1.0 regardless of baseline/delta.
    check = RegressionCheck(metric="citation_resolution", max_drop=0.0, require_min=1.0)
    current = {"citation_resolution": 0.95}
    baseline = {"citation_resolution": 0.95}  # no drop at all

    passed, message = check_metric(current, baseline, check)

    assert not passed
    assert "required minimum" in message


def test_check_metric_require_min_passes_at_floor() -> None:
    check = RegressionCheck(metric="citation_resolution", max_drop=0.0, require_min=1.0)

    passed, _ = check_metric({"citation_resolution": 1.0}, {"citation_resolution": 1.0}, check)

    assert passed


def test_check_metric_missing_current_metric_fails() -> None:
    check = RegressionCheck(metric="extraction_recall", max_drop=-0.02)

    passed, message = check_metric({}, {"extraction_recall": 0.9}, check)

    assert not passed
    assert "not present" in message


def test_run_checks_aggregates_all_passed() -> None:
    checks = [
        RegressionCheck(metric="a", max_drop=-0.02),
        RegressionCheck(metric="b", max_drop=-0.02),
    ]
    current = {"a": 0.9, "b": 0.9}
    baseline = {"a": 0.9, "b": 0.9}

    passed, messages = run_checks(current, baseline, checks)

    assert passed
    assert len(messages) == 2


def test_run_checks_fails_if_any_check_fails() -> None:
    checks = [
        RegressionCheck(metric="a", max_drop=-0.02),
        RegressionCheck(metric="b", max_drop=-0.02),
    ]
    current = {"a": 0.9, "b": 0.5}
    baseline = {"a": 0.9, "b": 0.9}

    passed, messages = run_checks(current, baseline, checks)

    assert not passed
    assert len(messages) == 2


def test_parse_check_arg_simple() -> None:
    check = parse_check_arg("extraction_recall=-0.02")

    assert check.metric == "extraction_recall"
    assert check.max_drop == -0.02
    assert check.require_min is None


def test_parse_check_arg_with_min() -> None:
    check = parse_check_arg("citation_resolution=0:min=1.0")

    assert check.metric == "citation_resolution"
    assert check.max_drop == 0.0
    assert check.require_min == 1.0


def test_parse_check_arg_invalid_raises() -> None:
    with pytest.raises(ValueError):
        parse_check_arg("no-equals-sign")


def test_baseline_metrics_from_git_missing_ref_returns_none() -> None:
    result = baseline_metrics_from_git("definitely-not-a-real-ref", "nope.json")

    assert result is None


def test_main_passes_and_returns_zero(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    current_path = tmp_path / "current.json"
    baseline_path = tmp_path / "baseline.json"
    current_path.write_text(json.dumps({"extraction_recall": 0.9, "citation_resolution": 1.0}))
    baseline_path.write_text(json.dumps({"extraction_recall": 0.9, "citation_resolution": 1.0}))

    exit_code = main(
        [
            "--current",
            str(current_path),
            "--baseline-file",
            str(baseline_path),
            "--check",
            "extraction_recall=-0.02",
            "--check",
            "citation_resolution=0:min=1.0",
        ]
    )

    assert exit_code == 0
    out = capsys.readouterr().out
    assert "PASS extraction_recall" in out
    assert "PASS citation_resolution" in out


def test_main_fails_and_returns_one(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    current_path = tmp_path / "current.json"
    baseline_path = tmp_path / "baseline.json"
    current_path.write_text(json.dumps({"extraction_recall": 0.5, "citation_resolution": 1.0}))
    baseline_path.write_text(json.dumps({"extraction_recall": 0.9, "citation_resolution": 1.0}))

    exit_code = main(
        [
            "--current",
            str(current_path),
            "--baseline-file",
            str(baseline_path),
            "--check",
            "extraction_recall=-0.02",
        ]
    )

    assert exit_code == 1
    out = capsys.readouterr().out
    assert "FAIL extraction_recall" in out


def test_main_no_checks_passes(tmp_path: Path) -> None:
    current_path = tmp_path / "current.json"
    current_path.write_text(json.dumps({"extraction_recall": 0.9}))

    exit_code = main(["--current", str(current_path)])

    assert exit_code == 0
