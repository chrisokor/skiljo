"""Extraction pipeline evaluation using the Inspect AI framework.

Provides scorers for:
- Rule recall: percentage of expected rules found in extracted skill spec
- Citation resolution: 100% of extracted rules must have valid span citations

The ExtractionEval task wraps these scorers in an Inspect Task for use with
the ``inspect eval`` CLI and programmatic evaluation harness.
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


def _iter_rules(spec: dict[str, Any]) -> list[dict[str, Any]]:
    """Flatten a Skill dict's three decision zones into one list of rule dicts.

    Real Skill specs (both hand-labeled ground truth in ``data/eval/*/*.skill.yaml``
    and pipeline output from ``assemble_skill``) have no top-level ``rules`` key —
    rules live under ``decision_zones.{deterministic,llm_assisted,human_only}``
    per ``schemas/skill.schema.json``. Rules also have no ``id`` field in the
    schema, so callers must key on structure (see ``_rule_key``), not identity.
    """
    zones = spec.get("decision_zones") or {}
    rules: list[dict[str, Any]] = []
    for zone_name in ("deterministic", "llm_assisted", "human_only"):
        rules.extend(zones.get(zone_name) or [])
    return rules


def _rule_key(rule: dict[str, Any]) -> str:
    """Structural identity for a rule: its condition + action as canonical JSON.

    Rules carry no stable ``id`` in ``rule.schema.json``, so two rules are
    considered "the same rule" for recall purposes when their condition and
    action match exactly.
    """
    return json.dumps(
        {"condition": rule.get("condition"), "action": rule.get("action")},
        sort_keys=True,
    )


def extraction_recall(expected: dict[str, Any], actual: dict[str, Any]) -> Score:
    """Measure percentage of expected rules found in extracted skill spec.

    Compares rules (by condition+action structure — see ``_rule_key``) found
    across all three decision zones of the expected spec against those in the
    actual extraction output. Vacuously returns 1.0 when the expected spec
    has no rules (nothing to recall).

    Args:
        expected: Ground-truth Skill spec dict (``decision_zones.*`` rule lists).
        actual:   Extracted Skill spec dict to evaluate.

    Returns:
        Score with value in [0.0, 1.0].
    """
    expected_keys = {_rule_key(r) for r in _iter_rules(expected)}
    actual_keys = {_rule_key(r) for r in _iter_rules(actual)}

    if not expected_keys:
        return Score(value=1.0, explanation="No expected rules — vacuous recall")

    matched = expected_keys & actual_keys
    missed = expected_keys - actual_keys
    recall = len(matched) / len(expected_keys)
    return Score(
        value=recall,
        explanation=f"Matched {len(matched)} of {len(expected_keys)} expected rules "
        f"({len(missed)} missed)",
    )


def citation_resolution(expected: dict[str, Any], actual: dict[str, Any]) -> Score:
    """Verify 100% of extracted rules have valid citation spans.

    Each rule in ``actual`` (across all three decision zones — see
    ``_iter_rules``) must have at least one citation entry containing
    ``span_start``, ``span_end``, and ``quoted_text`` fields. Returns 0.0
    on the first rule that fails this invariant.

    Note: ``rule.schema.json`` does not currently define a ``citations``
    field at all, so this will score 0.0 against any real extraction output
    until that schema gap is closed — that is expected and intentional; it
    surfaces the CLAUDE.md invariant #3 violation rather than masking it.

    Args:
        expected: Not used for this scorer (ground-truth is structural).
        actual:   Extracted skill spec dict to evaluate.

    Returns:
        Score with value 1.0 (all citations valid) or 0.0 (violation found).
    """
    rules = _iter_rules(actual)

    for rule in rules:
        citations = rule.get("citations", [])
        if not citations:
            return Score(
                value=0.0,
                explanation=f"Rule with action {rule.get('action', '?')!r} has no citations",
            )

        for citation in citations:
            required = {"span_start", "span_end", "quoted_text"}
            if not required.issubset(citation):
                missing = sorted(required - citation.keys())
                return Score(
                    value=0.0,
                    explanation=(
                        f"Citation for rule with action {rule.get('action', '?')!r} "
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
        actual: dict[str, Any] = state.metadata.get("actual_spec", {})
        target_text = target.text if isinstance(target.text, str) else "{}"
        try:
            expected: dict[str, Any] = json.loads(target_text)
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
        actual: dict[str, Any] = state.metadata.get("actual_spec", {})
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
