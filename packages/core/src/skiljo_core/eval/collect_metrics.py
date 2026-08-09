"""Collects eval metrics for the CI regression gate (plan #52).

Bridges the Inspect eval harness (this package) and ``scripts/check_regression.py``:
runs all three eval Tasks (extraction, simulation, e2e) and flattens their scorer
means into the metric names used by DESIGN_DOCUMENT.md Section 9
(``extraction_recall``, ``citation_resolution``, ``simulation_match_rate``,
``contradiction_recall``, ``e2e_accuracy``), writing them to a flat JSON file.

Defaults to Inspect's ``mockllm/model`` provider so this runs in CI without an API key,
network access, or cost. **Every score is vacuous (always 1.0) today**, not because
quality is perfect but because none of the three Tasks has a real dataset or solver
wired up yet: each is constructed with ``dataset=None`` (a single dummy sample) and
nothing populates ``state.metadata["actual_spec"]`` / ``"actual_result"`` /
``"actual_e2e"`` from a real ``run_extraction_pipeline()`` / ``simulate_batch()`` call
against ``data/eval/train/``. See ``docs/evals.md`` ("Dataset" section) for the exact
gap. This module -- and the CI wiring around it -- is deliberately built so that once
a dataset loader + solver land, the numbers this produces become real without any
change to ``.github/workflows/eval.yml`` or ``scripts/check_regression.py``: only
``--model`` needs to point at a real provider.
"""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from inspect_ai import Task, eval as inspect_eval
from inspect_ai.log import EvalLog

from skiljo_core.eval.e2e import E2EEval
from skiljo_core.eval.extraction import ExtractionEval
from skiljo_core.eval.simulation import SimulationEval

# Inspect scorer name -> Section 9 / DESIGN_DOCUMENT.md metric name, per suite.
_EXTRACTION_METRIC_NAMES = {
    "recall_scorer": "extraction_recall",
    "citation_scorer": "citation_resolution",
}
_SIMULATION_METRIC_NAMES = {
    "match_rate_scorer": "simulation_match_rate",
    "contradiction_precision_scorer": "contradiction_precision",
    "contradiction_recall_scorer": "contradiction_recall",
}
_E2E_METRIC_NAMES = {
    "e2e_accuracy_scorer": "e2e_accuracy",
}


def _flatten_scores(log: EvalLog, metric_names: dict[str, str]) -> dict[str, float]:
    """Extract each scorer's ``mean`` metric from an EvalLog's results."""
    metrics: dict[str, float] = {}
    if log.results is None:
        return metrics
    for score in log.results.scores:
        name = metric_names.get(score.name, score.name)
        mean_metric = score.metrics.get("mean")
        if mean_metric is not None:
            metrics[name] = mean_metric.value
    return metrics


def _run_task_metrics(task: Task, model: str, metric_names: dict[str, str]) -> dict[str, float]:
    with tempfile.TemporaryDirectory() as log_dir:
        logs = inspect_eval(task, model=model, log_dir=log_dir)
    return _flatten_scores(logs[0], metric_names)


def collect_extraction_metrics(model: str = "mockllm/model") -> dict[str, float]:
    """Run the extraction eval suite and return its Section-9-named metrics."""
    return _run_task_metrics(ExtractionEval(), model, _EXTRACTION_METRIC_NAMES)


def collect_simulation_metrics(model: str = "mockllm/model") -> dict[str, float]:
    """Run the simulation eval suite and return its Section-9-named metrics."""
    return _run_task_metrics(SimulationEval(), model, _SIMULATION_METRIC_NAMES)


def collect_e2e_metrics(model: str = "mockllm/model") -> dict[str, float]:
    """Run the end-to-end eval suite and return its Section-9-named metrics."""
    return _run_task_metrics(E2EEval(), model, _E2E_METRIC_NAMES)


def collect_all_metrics(model: str = "mockllm/model") -> dict[str, float]:
    """Run every eval suite and merge their metrics into one flat dict."""
    metrics: dict[str, float] = {}
    metrics.update(collect_extraction_metrics(model=model))
    metrics.update(collect_simulation_metrics(model=model))
    metrics.update(collect_e2e_metrics(model=model))
    return metrics


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path, help="Path to write metrics JSON")
    parser.add_argument(
        "--model",
        default="mockllm/model",
        help=(
            "Inspect model provider to run the eval suites against "
            "(default: mockllm/model -- no network or API key required)"
        ),
    )
    args = parser.parse_args(argv)

    metrics = collect_all_metrics(model=args.model)
    args.output.write_text(json.dumps(metrics, indent=2, sort_keys=True) + "\n")

    print(f"Wrote {len(metrics)} metric(s) to {args.output}")
    for name, value in sorted(metrics.items()):
        print(f"  {name}: {value:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
