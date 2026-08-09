"""Regression-gating logic for eval metrics (plan #52).

Compares a current metrics JSON (produced by ``skiljo_core.eval.collect_metrics``)
against a baseline metrics JSON and fails if any tracked metric has dropped beyond
its allowed threshold, per the regression budget in DESIGN_DOCUMENT.md Section 9:

    extraction recall      -2pts max
    citation resolution    100% required, no drop tolerated
    contradiction recall   -5pts max
    simulation match rate  -3pts max
    e2e accuracy           -3pts max

This module holds the pure, testable comparison logic. ``scripts/check_regression.py``
is the thin CLI entry point CI actually invokes.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

Metrics = dict[str, float]


@dataclass(frozen=True)
class RegressionCheck:
    """One metric's regression budget.

    ``max_drop`` is the most negative allowed delta (current - baseline); e.g. -0.02
    permits up to a 2-point drop. ``require_min`` is an absolute floor that must hold
    regardless of baseline (used for citation_resolution, which must always be 1.0 —
    Section 9 tolerates no regression on it at all).
    """

    metric: str
    max_drop: float = 0.0
    require_min: float | None = None


def load_metrics(path: Path) -> Metrics:
    """Load a metrics JSON file (metric name -> float)."""
    return dict(json.loads(Path(path).read_text()))


def baseline_metrics_from_git(ref: str, path: str) -> Metrics | None:
    """Read a metrics JSON file as it existed at ``ref`` (e.g. ``origin/main``).

    Returns ``None`` if the ref/path doesn't resolve -- e.g. this is the first PR to
    introduce the baseline file, or the metric didn't exist yet on that ref. A missing
    baseline means "nothing to regress against," not a build failure.
    """
    try:
        result = subprocess.run(
            ["git", "show", f"{ref}:{path}"],
            capture_output=True,
            check=True,
            text=True,
        )
    except (subprocess.CalledProcessError, OSError):
        return None
    try:
        return dict(json.loads(result.stdout))
    except json.JSONDecodeError:
        return None


def check_metric(
    current: Metrics, baseline: Metrics | None, check: RegressionCheck
) -> tuple[bool, str]:
    """Evaluate one metric's regression check. Returns ``(passed, message)``."""
    if check.metric not in current:
        return False, f"FAIL {check.metric}: not present in current metrics"

    current_value = current[check.metric]

    if check.require_min is not None and current_value < check.require_min:
        return False, (
            f"FAIL {check.metric}: {current_value:.3f} is below the required "
            f"minimum {check.require_min:.3f}"
        )

    if baseline is None or check.metric not in baseline:
        return True, f"PASS {check.metric}: {current_value:.3f} (no baseline to compare)"

    baseline_value = baseline[check.metric]
    delta = current_value - baseline_value
    if delta < check.max_drop:
        return False, (
            f"FAIL {check.metric}: regressed by {delta:.3f} "
            f"(baseline {baseline_value:.3f} -> current {current_value:.3f}, "
            f"max allowed drop {check.max_drop:.3f})"
        )
    return True, f"PASS {check.metric}: {current_value:.3f} (delta {delta:+.3f})"


def run_checks(
    current: Metrics, baseline: Metrics | None, checks: list[RegressionCheck]
) -> tuple[bool, list[str]]:
    """Evaluate every check. Returns ``(all_passed, messages)``."""
    messages: list[str] = []
    all_passed = True
    for check in checks:
        passed, message = check_metric(current, baseline, check)
        messages.append(message)
        all_passed = all_passed and passed
    return all_passed, messages


def parse_check_arg(raw: str) -> RegressionCheck:
    """Parse a ``--check`` CLI value.

    Format: ``metric=max_drop[:min=require_min]``, e.g.:
        extraction_recall=-0.02
        citation_resolution=0:min=1.0
    """
    metric_part, sep, drop_part = raw.partition("=")
    if not sep:
        raise ValueError(f"invalid --check value {raw!r}; expected metric=max_drop")

    require_min: float | None = None
    if ":min=" in drop_part:
        drop_part, _, min_part = drop_part.partition(":min=")
        require_min = float(min_part)

    return RegressionCheck(metric=metric_part, max_drop=float(drop_part), require_min=require_min)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--current", required=True, type=Path, help="Path to current metrics JSON")
    parser.add_argument("--baseline-file", type=Path, help="Path to a baseline metrics JSON file")
    parser.add_argument(
        "--baseline-ref", help="Git ref to read the baseline metrics file from, e.g. origin/main"
    )
    parser.add_argument(
        "--baseline-path",
        help="Path (relative to repo root) to the baseline metrics file within --baseline-ref",
    )
    parser.add_argument(
        "--check",
        action="append",
        default=[],
        metavar="METRIC=MAX_DROP[:min=REQUIRE_MIN]",
        help=(
            "Repeatable regression threshold, e.g. --check extraction_recall=-0.02 "
            "--check citation_resolution=0:min=1.0"
        ),
    )
    args = parser.parse_args(argv)

    current = load_metrics(args.current)

    baseline: Metrics | None = None
    if args.baseline_file is not None:
        baseline = load_metrics(args.baseline_file)
    elif args.baseline_ref and args.baseline_path:
        baseline = baseline_metrics_from_git(args.baseline_ref, args.baseline_path)

    checks = [parse_check_arg(raw) for raw in args.check]
    if not checks:
        print("No --check thresholds given; nothing to gate.")
        return 0

    passed, messages = run_checks(current, baseline, checks)
    for message in messages:
        print(message)

    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
