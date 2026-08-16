"""Collects eval metrics for the CI regression gate (plan #52).

Bridges the Inspect eval harness (this package) and ``scripts/check_regression.py``:
runs all three eval Tasks (extraction, simulation, e2e) and flattens their scorer
means into the metric names used by DESIGN_DOCUMENT.md Section 9
(``extraction_recall``, ``citation_resolution``, ``simulation_match_rate``,
``contradiction_recall``, ``e2e_accuracy``), writing them to a flat JSON file.

Extraction dataset loading is active for the train and dev splits. The extraction
solver runs only when a usable, injected ``LLMClient`` is configured; the default
offline collector emits explicit placeholder extraction metrics instead of silently
constructing a provider client. Citation resolution remains a hard invariant when
real extraction runs. Simulation and end-to-end metrics remain limited until
ticket-level ground truth lands. ``data/eval/test/`` remains forbidden locally.

Defaults to Inspect's ``mockllm/model`` provider and ``split="train"`` so local/CI
runs need no network access or API key. Pass an injected, application-configured
``LLMClient`` to ``collect_extraction_metrics`` for real extraction metrics. This
preserves the LLM logging boundary rather than creating an unlogged provider client
inside the eval package.
"""

from __future__ import annotations

import argparse
import json
import tempfile
import warnings
from pathlib import Path

from inspect_ai import Task, eval as inspect_eval
from inspect_ai.log import EvalLog

from skiljo_core.eval.e2e import E2EEval
from skiljo_core.eval.extraction import ExtractionEval
from skiljo_core.eval.simulation import SimulationEval
from skiljo_core.llm.base import LLMClient

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


def collect_extraction_metrics(
    model: str = "mockllm/model",
    split: str = "train",
    llm_client: LLMClient | None = None,
) -> dict[str, float]:
    """Run extraction metrics when a client is injected, otherwise report the limit.

    The offline path preserves a successful no-network CI command while making the
    absence of real pipeline output visible: recall is zero and citation resolution
    is vacuously one because no extracted rules were evaluated.
    """
    if llm_client is None:
        warnings.warn(
            "Extraction eval requires an injected LLMClient for real extraction; "
            "returning explicit offline placeholder metrics.",
            RuntimeWarning,
            stacklevel=2,
        )
        return {"extraction_recall": 0.0, "citation_resolution": 1.0}
    return _run_task_metrics(
        ExtractionEval(split=split, llm_client=llm_client), model, _EXTRACTION_METRIC_NAMES
    )


def collect_simulation_metrics(model: str = "mockllm/model", split: str = "train") -> dict[str, float]:
    """Run the simulation eval suite and return its Section-9-named metrics."""
    return _run_task_metrics(SimulationEval(split=split), model, _SIMULATION_METRIC_NAMES)


def collect_e2e_metrics(model: str = "mockllm/model", split: str = "train") -> dict[str, float]:
    """Run the end-to-end eval suite and return its Section-9-named metrics."""
    return _run_task_metrics(E2EEval(split=split), model, _E2E_METRIC_NAMES)


def collect_all_metrics(
    model: str = "mockllm/model",
    split: str = "train",
    extraction_llm_client: LLMClient | None = None,
) -> dict[str, float]:
    """Run every eval suite (against ``data/eval/{split}/``, plan #57's real
    dataset loader) and merge their metrics into one flat dict."""
    metrics: dict[str, float] = {}
    metrics.update(
        collect_extraction_metrics(
            model=model,
            split=split,
            llm_client=extraction_llm_client,
        )
    )
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
