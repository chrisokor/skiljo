"""Simulation pipeline evaluation using the Inspect AI framework.

Provides scorers for:
- Match rate: percentage of tickets where the simulated decision matches
  ground truth (the shadow-policy-generated expected decision).
- Contradiction detection precision: of the contradictions the simulation
  flagged, how many correspond to real planted divergences?
- Contradiction detection recall: of the planted divergences, how many did
  the simulation's contradiction detector actually flag?

The SimulationEval task wraps these scorers in an Inspect Task for use with
the ``inspect eval`` CLI and programmatic evaluation harness.
"""

from __future__ import annotations

import json
from typing import Any

from inspect_ai import Task, task
from inspect_ai.scorer import Score, Scorer, Target, mean, scorer
from inspect_ai.scorer._scorer import TaskState


# ---------------------------------------------------------------------------
# Standalone scorer logic (pure Python, testable without Inspect machinery)
# ---------------------------------------------------------------------------


def _contradiction_key(contradiction: dict[str, Any]) -> str:
    """Structural identity for a detected contradiction.

    Real ``Contradiction`` output (see
    ``skiljo_core.simulation.contradictions.Contradiction``) has no top-level
    ``rule_id`` field. It carries an optional ``citation`` with a nested
    ``rule_id``, but ``detect_contradictions`` never populates ``citation``
    (it's always ``None``/absent), so that can't be relied on either.

    Prefer ``citation.rule_id`` when present (future-proofing for once the
    detector attaches citations), otherwise fall back to a structural key
    built from ``cluster_key`` + the written/observed decision pair — the
    same fields the detector uses to construct each ``Contradiction`` in the
    first place.
    """
    citation = contradiction.get("citation") or {}
    rule_id = citation.get("rule_id") if isinstance(citation, dict) else None
    if rule_id:
        return str(rule_id)

    cluster_key = contradiction.get("cluster_key") or {}
    return json.dumps(
        {
            "cluster_key": cluster_key,
            "written_decision": contradiction.get("written_decision"),
            "observed_decision": contradiction.get("observed_decision"),
        },
        sort_keys=True,
    )


def simulation_match_rate(expected: dict[str, Any], actual: dict[str, Any]) -> Score:
    """Measure percentage of tickets where the simulated decision matches
    ground truth.

    Ground truth decisions come from the shadow-policy ticket generator
    (see CLAUDE.md: tickets are labeled against the shadow policy, not the
    written policy, so this is a genuine fidelity measurement rather than a
    circular one). Vacuously returns 1.0 when there are no expected results.

    Args:
        expected: Ground-truth simulation result dict (``results`` list with
            per-ticket ``decision`` keys, in ticket order).
        actual:   Simulation output dict to evaluate, same shape.

    Returns:
        Score with value in [0.0, 1.0].
    """
    expected_results = expected.get("results", [])
    actual_results = actual.get("results", [])

    if not expected_results:
        return Score(value=1.0, explanation="No expected results — vacuous match rate")

    matches = sum(
        1
        for exp, act in zip(expected_results, actual_results)
        if exp.get("decision") == act.get("decision")
    )
    match_rate = matches / len(expected_results)
    return Score(
        value=match_rate,
        explanation=f"Matched {matches} of {len(expected_results)} ticket decisions",
    )


def contradiction_detection_precision(expected: dict[str, Any], actual: dict[str, Any]) -> Score:
    """Of the contradictions flagged, how many were real (planted)?

    Compares detected contradiction rule IDs against the set of planted
    divergence IDs from the shadow-policy spec. Vacuously returns 1.0 when
    nothing was detected (no false positives to penalize).

    Args:
        expected: Ground-truth dict with ``planted_divergence_ids`` list.
        actual:   Simulation output dict with ``contradictions`` list of
            dicts (real ``Contradiction`` shape — see ``_contradiction_key``
            for how each one is keyed, since there's no top-level ``rule_id``).

    Returns:
        Score with value in [0.0, 1.0].
    """
    planted = set(expected.get("planted_divergence_ids", []))
    detected = {_contradiction_key(c) for c in actual.get("contradictions", [])}

    if not detected:
        return Score(value=1.0, explanation="No contradictions detected — vacuous precision")

    true_positives = planted & detected
    precision = len(true_positives) / len(detected)
    return Score(
        value=precision,
        explanation=f"True positives: {sorted(true_positives)}, Detected: {sorted(detected)}",
    )


def contradiction_detection_recall(expected: dict[str, Any], actual: dict[str, Any]) -> Score:
    """Of the planted divergences, how many did the detector flag?

    Acceptance target per CLAUDE.md is >=0.8 recall on planted divergences.
    Vacuously returns 1.0 when there are no planted divergences to find.

    Args:
        expected: Ground-truth dict with ``planted_divergence_ids`` list.
        actual:   Simulation output dict with ``contradictions`` list of
            dicts (real ``Contradiction`` shape — see ``_contradiction_key``
            for how each one is keyed, since there's no top-level ``rule_id``).

    Returns:
        Score with value in [0.0, 1.0].
    """
    planted = set(expected.get("planted_divergence_ids", []))
    detected = {_contradiction_key(c) for c in actual.get("contradictions", [])}

    if not planted:
        return Score(value=1.0, explanation="No planted divergences — vacuous recall")

    true_positives = planted & detected
    recall = len(true_positives) / len(planted)
    return Score(
        value=recall,
        explanation=f"Found: {sorted(true_positives)}, Missed: {sorted(planted - detected)}",
    )


# ---------------------------------------------------------------------------
# Inspect AI scorer factories (wired into the Task)
# ---------------------------------------------------------------------------


@scorer(metrics=[mean()])
def match_rate_scorer() -> Scorer:
    """Inspect scorer that delegates to simulation_match_rate.

    Reads ground-truth results from target JSON and actual results from
    ``state.metadata["actual_result"]``.
    """

    async def score(state: TaskState, target: Target) -> Score:
        actual: dict[str, Any] = state.metadata.get("actual_result", {})
        target_text = target.text if isinstance(target.text, str) else "{}"
        try:
            expected: dict[str, Any] = json.loads(target_text)
        except json.JSONDecodeError:
            expected = {}
        return simulation_match_rate(expected, actual)

    return score  # type: ignore[return-value]


@scorer(metrics=[mean()])
def contradiction_precision_scorer() -> Scorer:
    """Inspect scorer that delegates to contradiction_detection_precision.

    Reads ground-truth planted divergences from target JSON and actual
    contradictions from ``state.metadata["actual_result"]``.
    """

    async def score(state: TaskState, target: Target) -> Score:
        actual: dict[str, Any] = state.metadata.get("actual_result", {})
        target_text = target.text if isinstance(target.text, str) else "{}"
        try:
            expected: dict[str, Any] = json.loads(target_text)
        except json.JSONDecodeError:
            expected = {}
        return contradiction_detection_precision(expected, actual)

    return score  # type: ignore[return-value]


@scorer(metrics=[mean()])
def contradiction_recall_scorer() -> Scorer:
    """Inspect scorer that delegates to contradiction_detection_recall.

    Reads ground-truth planted divergences from target JSON and actual
    contradictions from ``state.metadata["actual_result"]``.
    """

    async def score(state: TaskState, target: Target) -> Score:
        actual: dict[str, Any] = state.metadata.get("actual_result", {})
        target_text = target.text if isinstance(target.text, str) else "{}"
        try:
            expected: dict[str, Any] = json.loads(target_text)
        except json.JSONDecodeError:
            expected = {}
        return contradiction_detection_recall(expected, actual)

    return score  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Inspect Task
# ---------------------------------------------------------------------------


@task(name="simulate")
def SimulationEval() -> Task:
    """Simulation eval: match rate and contradiction detection precision/recall.

    Uses labeled examples from ``data/eval/train/`` (skill spec + tickets +
    shadow-policy ground truth decisions and planted divergence IDs). In the
    full harness the solver runs the simulation engine and populates
    ``state.metadata["actual_result"]`` so the scorers can evaluate it.

    ``dataset=None`` makes Inspect supply a single dummy sample so the task
    can be imported and instantiated without real eval data on disk.
    """
    return Task(
        dataset=None,  # populated by the eval runner with real samples
        scorer=[
            match_rate_scorer(),
            contradiction_precision_scorer(),
            contradiction_recall_scorer(),
        ],
        name="simulate",
    )
