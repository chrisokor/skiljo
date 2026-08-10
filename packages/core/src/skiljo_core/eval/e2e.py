"""End-to-end pipeline evaluation using the Inspect AI framework.

Composes the extraction and simulation stages into a single accuracy
measure: given raw policy text, extract a skill, simulate it against
synthetic tickets with planted divergences, and score how well the
predicted decisions match ground truth across the full pipeline.

Provides:
- e2e_accuracy: how close the observed end-to-end accuracy is to the
  expected (ground-truth) end-to-end accuracy for a labeled example.

The E2EEval task wraps this scorer in an Inspect Task for use with the
``inspect eval`` CLI and programmatic evaluation harness.
"""

from __future__ import annotations

import json
from typing import Any

from inspect_ai import Task, task
from inspect_ai.scorer import Score, Scorer, Target, mean, scorer
from inspect_ai.solver import TaskState


# ---------------------------------------------------------------------------
# Standalone scorer logic (pure Python, testable without Inspect machinery)
# ---------------------------------------------------------------------------


def e2e_accuracy(expected: dict[str, Any], actual: dict[str, Any]) -> Score:
    """Measure how close observed end-to-end accuracy is to the expected value.

    ``expected_e2e_accuracy`` is the labeled ground-truth accuracy for the
    example (the fraction of tickets across the full pipeline — extraction
    followed by simulation — that should resolve to the correct decision).
    ``actual_e2e_accuracy`` is what the pipeline actually achieved. The score
    is ``1.0`` minus the absolute error, floored at ``0.0``, so a perfect
    match scores 1.0 and increasing divergence scores lower.

    Args:
        expected: Ground-truth example dict with ``expected_e2e_accuracy``.
        actual:   Pipeline output dict with ``e2e_accuracy``.

    Returns:
        Score with value in [0.0, 1.0].
    """
    expected_accuracy = expected.get("expected_e2e_accuracy", 0.0)
    actual_accuracy = actual.get("e2e_accuracy", 0.0)

    error = abs(expected_accuracy - actual_accuracy)
    value = max(0.0, 1.0 - error)
    return Score(
        value=value,
        explanation=(
            f"expected={expected_accuracy:.3f}, actual={actual_accuracy:.3f}, "
            f"error={error:.3f}"
        ),
    )


# ---------------------------------------------------------------------------
# Inspect AI scorer factory (wired into the Task)
# ---------------------------------------------------------------------------


@scorer(metrics=[mean()])
def e2e_accuracy_scorer() -> Scorer:
    """Inspect scorer that delegates to e2e_accuracy.

    Reads ground-truth ``expected_e2e_accuracy`` from target JSON and the
    pipeline's actual result from ``state.metadata["actual_e2e"]``.
    """

    async def score(state: TaskState, target: Target) -> Score:
        actual: dict[str, Any] = state.metadata.get("actual_e2e", {})
        target_text = target.text if isinstance(target.text, str) else "{}"
        try:
            expected: dict[str, Any] = json.loads(target_text)
        except json.JSONDecodeError:
            expected = {}
        return e2e_accuracy(expected, actual)

    return score  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Inspect Task
# ---------------------------------------------------------------------------


@task(name="e2e")
def E2EEval() -> Task:
    """End-to-end pipeline eval: full extraction + simulation accuracy.

    Uses labeled examples pairing raw policy text with a ground-truth
    end-to-end accuracy figure computed by running the extracted skill's
    predicted decisions against the shadow-policy ground truth. In the full
    harness the solver runs extraction then simulation and populates
    ``state.metadata["actual_e2e"]`` so the scorer can evaluate it.

    ``dataset=None`` makes Inspect supply a single dummy sample so the task
    can be imported and instantiated without real eval data on disk.
    """
    return Task(
        dataset=None,  # populated by the eval runner with real samples
        scorer=[e2e_accuracy_scorer()],
        name="e2e",
    )
