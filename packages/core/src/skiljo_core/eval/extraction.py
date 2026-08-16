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
from inspect_ai.solver import Generate, Solver, TaskState, solver

from .dataset_loader import load_extraction_dataset
from skiljo_core.extraction.pipeline import run_extraction_pipeline
from skiljo_core.llm.base import LLMClient


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
    ``_iter_rules``) must carry a valid source citation. Pipeline output uses
    the schema's singular ``citation`` shape (``span.start``, ``span.end``,
    and ``quoted_text``); the legacy plural ``citations`` shape remains
    accepted for existing scorer fixtures. Returns 0.0 on the first rule
    that fails this invariant.

    Args:
        expected: Not used for this scorer (ground-truth is structural).
        actual:   Extracted skill spec dict to evaluate.

    Returns:
        Score with value 1.0 (all citations valid) or 0.0 (violation found).
    """
    rules = _iter_rules(actual)

    for rule in rules:
        citation = rule.get("citation")
        if isinstance(citation, dict):
            span = citation.get("span")
            if isinstance(span, dict) and {"start", "end"}.issubset(span) and "quoted_text" in citation:
                continue
            return Score(
                value=0.0,
                explanation=f"Rule with action {rule.get('action', '?')!r} has an invalid citation",
            )

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


@solver
def extraction_solver(llm_client: LLMClient | None = None) -> Solver:
    """Run the extraction pipeline and attach its serialized Skill to state.

    A usable client is deliberately injected rather than constructed here so
    provider calls retain the application's logging/configuration boundary and
    deterministic tests can use ``FakeLLMClient`` without production code
    depending on test helpers.
    """

    async def solve(state: TaskState, generate: Generate) -> TaskState:
        if llm_client is None:
            raise RuntimeError("extraction_solver requires an LLM client for real extraction")

        skill = run_extraction_pipeline(
            llm_client,
            policy_text=str(state.input),
            skill_name=str(state.metadata.get("skill_name", "process_refund_request")),
            trigger=str(state.metadata.get("trigger", "customer_requests_refund")),
        )
        state.metadata["actual_spec"] = skill.model_dump(mode="json")
        return state

    return solve


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
def ExtractionEval(split: str = "train", llm_client: LLMClient | None = None) -> Task:
    """Extraction pipeline eval: rule recall and citation resolution.

    Uses labeled examples from ``data/eval/{split}/`` (policy text + expected
    skill spec YAML) and an explicit extraction-pipeline solver. ``llm_client``
    is required when the task executes: keeping it injected prevents default
    local/CI runs from making provider calls or constructing an unlogged client.
    """
    return Task(
        dataset=list(load_extraction_dataset(split=split)),
        solver=extraction_solver(llm_client=llm_client),
        scorer=[recall_scorer(), citation_scorer()],
        name="extract",
    )
