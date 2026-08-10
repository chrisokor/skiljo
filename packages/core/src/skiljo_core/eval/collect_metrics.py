"""Collects eval metrics for the CI regression gate (plan #52).

Bridges the Inspect eval harness (this package) and ``scripts/check_regression.py``:
runs all three eval Tasks (extraction, simulation, e2e) and flattens their scorer
means into the metric names used by DESIGN_DOCUMENT.md Section 9
(``extraction_recall``, ``citation_resolution``, ``simulation_match_rate``,
``contradiction_recall``, ``e2e_accuracy``), writing them to a flat JSON file.

Defaults to Inspect's ``mockllm/model`` provider so this runs in CI without an API key,
network access, or cost, and to ``split="train"`` (30 examples; pass ``split="dev"``
for 15, never ``split="test"`` -- see CLAUDE.md system invariant 5).

As of plan #57, all three Tasks load the real ``data/eval/{split}/`` dataset via
``skiljo_core.eval.dataset_loader`` instead of the single vacuous dummy sample
``dataset=None`` used to supply -- so ``extraction_recall`` is now a genuine
measurement rather than a constant 1.0. It still won't be a *meaningful* one until a
"solver" step exists that runs ``run_extraction_pipeline()`` per sample and populates
``state.metadata["actual_spec"]``: without it, ``actual`` stays empty and
``extraction_recall`` scores genuinely low (typically 0.0) against the real expected
rules, which is an honest reflection of the remaining gap, not a regression to chase
down. ``citation_resolution`` is unaffected (still vacuously 1.0, since it only reads
``actual``). ``simulation_match_rate`` and the contradiction precision/recall scorers
also stay vacuously 1.0 today: `data/eval/` has no ticket-level simulation ground
truth yet, so ``SimulationEval``'s samples carry no ``results``/
``planted_divergence_ids``. See ``dataset_loader.py``'s module docstring and
``docs/evals.md`` ("Dataset" section) for the full picture, and
``state.metadata["actual_result"]`` / ``"actual_e2e"`` for the remaining solver gap.
This module -- and the CI wiring around it -- is deliberately built so that once a
solver lands, the numbers this produces become real without any change to
``.github/workflows/eval.yml`` or ``scripts/check_regression.py``: only ``--model``
needs to point at a real provider.
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


def collect_extraction_metrics(model: str = "mockllm/model", split: str = "train") -> dict[str, float]:
    """Run the extraction eval suite and return its Section-9-named metrics."""
    return _run_task_metrics(ExtractionEval(split=split), model, _EXTRACTION_METRIC_NAMES)


def collect_simulation_metrics(model: str = "mockllm/model", split: str = "train") -> dict[str, float]:
    """Run the simulation eval suite and return its Section-9-named metrics."""
    return _run_task_metrics(SimulationEval(split=split), model, _SIMULATION_METRIC_NAMES)


def collect_e2e_metrics(model: str = "mockllm/model", split: str = "train") -> dict[str, float]:
    """Run the end-to-end eval suite and return its Section-9-named metrics."""
    return _run_task_metrics(E2EEval(split=split), model, _E2E_METRIC_NAMES)


def collect_all_metrics(model: str = "mockllm/model", split: str = "train") -> dict[str, float]:
    """Run every eval suite (against ``data/eval/{split}/``, plan #57's real
    dataset loader) and merge their metrics into one flat dict."""
    metrics: dict[str, float] = {}
    metrics.update(collect_extraction_metrics(model=model, split=split))
    metrics.update(collect_simulation_metrics(model=model, split=split))
    metrics.update(collect_e2e_metrics(model=model, split=split))
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
    parser.add_argument(
        "--split",
        default="train",
        choices=["train", "dev"],
        help=(
            "data/eval/ split to run against (default: train, 30 examples; "
            "dev has 15). 'test' is intentionally not an option -- "
            "CLAUDE.md system invariant 5."
        ),
    )
    args = parser.parse_args(argv)

    metrics = collect_all_metrics(model=args.model, split=args.split)
    args.output.write_text(json.dumps(metrics, indent=2, sort_keys=True) + "\n")

    print(f"Wrote {len(metrics)} metric(s) to {args.output}")
    for name, value in sorted(metrics.items()):
        print(f"  {name}: {value:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
