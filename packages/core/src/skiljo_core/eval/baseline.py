"""Refreshes the committed eval baseline on merge to main (plan #58).

CI wiring: ``.github/workflows/eval.yml``'s ``update-baseline`` job runs this after
every push to ``main``, so ``data/eval/baseline_metrics.json`` -- the file
``scripts/check_regression.py`` diffs every PR's metrics against -- tracks whatever
is actually on ``main`` instead of going stale relative to a baseline committed weeks
or commits ago. It reuses ``collect_all_metrics`` from
``skiljo_core.eval.collect_metrics`` -- the same function the PR-time gate uses to
produce "current" metrics -- so the baseline and the numbers compared against it are
always produced by the same code path and metric set.

Deliberately writes the same flat ``{metric_name: float}`` shape the file already
has (see ``skiljo_core.eval.regression.load_metrics`` /
``baseline_metrics_from_git``, both of which load this file directly as
``dict[str, float]``): no wrapper object, no ``timestamp``/``commit_sha`` metadata
fields mixed into the metrics dict. Provenance (which commit produced a given
baseline) belongs in the git history of this file, not inside it -- CI commits the
refreshed file with a normal commit, so ``git log data/eval/baseline_metrics.json``
already answers "when did this change and from what merge."

``scripts/update_baseline.py`` is the thin CLI entry point CI actually invokes.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from skiljo_core.eval.collect_metrics import collect_all_metrics

DEFAULT_BASELINE_PATH = Path("data/eval/baseline_metrics.json")


def update_baseline(
    model: str = "mockllm/model",
    output_path: Path = DEFAULT_BASELINE_PATH,
) -> dict[str, float]:
    """Recompute eval metrics and overwrite the baseline file with them.

    Returns the metrics dict written, so callers/tests that need it don't have to
    re-read the file. Uses the exact same JSON formatting
    (``collect_metrics.main``'s ``indent=2, sort_keys=True``) already committed at
    ``data/eval/baseline_metrics.json`` so this is a content-only diff, not a
    reformat, when nothing regressed.
    """
    metrics = collect_all_metrics(model=model)
    output_path.write_text(json.dumps(metrics, indent=2, sort_keys=True) + "\n")
    return metrics


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--model",
        default="mockllm/model",
        help=(
            "Inspect model provider to run the eval suites against "
            "(default: mockllm/model -- no network or API key required)"
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_BASELINE_PATH,
        help="Path to write the baseline metrics JSON (default: data/eval/baseline_metrics.json)",
    )
    args = parser.parse_args(argv)

    metrics = update_baseline(model=args.model, output_path=args.output)

    print(f"Refreshed {args.output} with {len(metrics)} metric(s)")
    for name, value in sorted(metrics.items()):
        print(f"  {name}: {value:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
