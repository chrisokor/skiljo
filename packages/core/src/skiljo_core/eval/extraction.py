"""Extraction pipeline evaluation using the Inspect AI framework.

Provides scorers for:
- Rule recall: percentage of expected rules found in extracted skill spec
- Citation resolution: 100% of extracted rules must have valid span citations

The ExtractionEval task wraps these scorers in an Inspect Task for use with
the ``inspect eval`` CLI and programmatic evaluation harness.
"""

from __future__ import annotations

import json

from inspect_ai import Task, task
from inspect_ai.scorer import Score, Scorer, Target, mean, scorer
from inspect_ai.scorer._scorer import TaskState


# ---------------------------------------------------------------------------
# Standalone scorer logic (pure Python, testable without Inspect machinery)
# ---------------------------------------------------------------------------


def extraction_recall(expected: dict, actual: dict) -> Score:
    """Measure percentage of expected rules found in extracted skill spec.

    Compares rule IDs in the expected spec against rule IDs present in the
    actual extraction output.  Vacuously returns 1.0 when the expected spec
    has no rules (nothing to recall).

    Args:
        expected: Ground-truth skill spec dict (``rules`` list with ``id`` keys).
        actual:   Extracted skill spec dict to evaluate.

    Returns:
        Score with value in [0.0, 1.0].
    """
    expected_rule_ids = set(r["id"] for r in expected.get("rules", []))
    actual_rule_ids = set(r["id"] for r in actual.get("rules", []))

    if not expected_rule_ids:
        return Score(value=1.0, explanation="No expected rules — vacuous recall")

    recall = len(expected_rule_ids & actual_rule_ids) / len(expected_rule_ids)
    matched = expected_rule_ids & actual_rule_ids
    missed = expected_rule_ids - actual_rule_ids
    return Score(
        value=recall,
        explanation=f"Matched: {sorted(matched)}, Missed: {sorted(missed)}",
    )


def citation_resolution(expected: dict, actual: dict) -> Score:
    """Verify 100% of extracted rules have valid citation spans.

    Each rule in ``actual`` must have at least one citation entry containing
    ``span_start``, ``span_end``, and ``quoted_text`` fields.  Returns 0.0
    on the first rule that fails this invariant.

    Args:
        expected: Not used for this scorer (ground-truth is structural).
        actual:   Extracted skill spec dict to evaluate.

    Returns:
        Score with value 1.0 (all citations valid) or 0.0 (violation found).
    """
    rules = actual.get("rules", [])

    for rule in rules:
        citations = rule.get("citations", [])
        if not citations:
            return Score(
                value=0.0,
                explanation=f"Rule {rule.get('id', '?')} has no citations",
            )

        for citation in citations:
            required = {"span_start", "span_end", "quoted_text"}
            if not required.issubset(citation):
                missing = sorted(required - citation.keys())
                return Score(
                    value=0.0,
                    explanation=(
                        f"Citation for rule {rule.get('id', '?')} "
                        f"missing fields: {missing}"
                    ),
                )

    return Score(value=1.0, explanation="All citations valid")


# ---------------------------------------------------------------------------
# Inspect AI scorer factories (wired into the Task)
# ---------------------------------------------------------------------------


@scorer(metrics=[mean()])
def recall_scorer() -> Scorer:
    """Inspect scorer that delegates to extraction_recall.

    Reads ground-truth spec from target JSON and actual spec from
    ``state.metadata["actual_spec"]``.
    """

    async def score(state: TaskState, target: Target) -> Score:
        actual: dict = state.metadata.get("actual_spec", {})
        target_text = target.text if isinstance(target.text, str) else "{}"
        try:
            expected: dict = json.loads(target_text)
        except json.JSONDecodeError:
            expected = {}
        return extraction_recall(expected, actual)

    return score  # type: ignore[return-value]


@scorer(metrics=[mean()])
def citation_scorer() -> Scorer:
    """Inspect scorer that delegates to citation_resolution.

    Reads actual spec from ``state.metadata["actual_spec"]``.
    """

    async def score(state: TaskState, target: Target) -> Score:
        actual: dict = state.metadata.get("actual_spec", {})
        return citation_resolution({}, actual)

    return score  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Inspect Task
# ---------------------------------------------------------------------------


@task(name="extract")
def ExtractionEval() -> Task:
    """Extraction pipeline eval: rule recall and citation resolution.

    Uses labeled examples from ``data/eval/train/`` (policy text + expected
    skill spec YAML).  In the full harness the solver runs the extraction
    pipeline and populates ``state.metadata["actual_spec"]`` so the scorers
    can evaluate it.

    ``dataset=None`` makes Inspect supply a single dummy sample so the task
    can be imported and instantiated without real eval data on disk.
    """
    return Task(
        dataset=None,  # populated by the eval runner with real samples
        scorer=[recall_scorer(), citation_scorer()],
        name="extract",
    )
