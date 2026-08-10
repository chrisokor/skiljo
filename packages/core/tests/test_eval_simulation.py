"""Tests for the simulation eval suite (plan #49, fixed up under plan #56-fixup).

Verifies:
- SimulationEval task exists with correct name and scorers wired
- simulation_match_rate scorer calculates ticket decision match rate correctly
- contradiction_detection_precision scorer validates detected-vs-planted precision
- contradiction_detection_recall scorer validates detected-vs-planted recall

Ground-truth and pipeline-output contradictions (see
``skiljo_core.simulation.contradictions.Contradiction``) have no top-level
``rule_id`` field. They carry an optional ``citation`` with a nested
``rule_id``, but the detector (``detect_contradictions``) never populates
``citation`` in practice — it's always ``None``. Fixtures below use that real
shape (plan #56-fixup: the original fixtures used a ``{"rule_id": ...}``
shape that never occurs in real detector output, which raised ``KeyError``
against real data).
"""

from skiljo_core.eval.simulation import (
    SimulationEval,
    contradiction_detection_precision,
    contradiction_detection_recall,
    simulation_match_rate,
)


def _contradiction(
    *,
    rule_id: str | None = None,
    amount_band: str = "0-50",
    customer_segment: str = "enterprise",
    written_decision: str = "deny",
    observed_decision: str = "approve",
) -> dict:
    """Build a real-shaped contradiction dict.

    Mirrors what ``dataclasses.asdict(Contradiction(...))`` (or JSON
    round-tripping the pydantic ``ContradictionRecord``) actually produces:
    a ``cluster_key`` dict, decision fields, and an optional ``citation``
    (``None`` unless explicitly given a ``rule_id`` here — matching the fact
    that the detector never populates it today).
    """
    contradiction: dict = {
        "cluster_key": {"amount_band": amount_band, "customer_segment": customer_segment},
        "written_decision": written_decision,
        "observed_decision": observed_decision,
        "frequency": 0.2,
        "ticket_count": 10,
        "affected_ticket_ids": [],
        "citation": (
            {
                "policy_id": "p1",
                "rule_id": rule_id,
                "span_start": 0,
                "span_end": 1,
                "quoted_text": "x",
            }
            if rule_id
            else None
        ),
        "estimated_financial_impact": None,
    }
    return contradiction


def test_simulation_eval_task_exists() -> None:
    eval_task = SimulationEval()
    assert eval_task.name == "simulate"
    assert eval_task.scorer is not None


def test_match_rate_scorer() -> None:
    expected = {"results": [{"decision": "approve"}, {"decision": "deny"}]}
    actual = {"results": [{"decision": "approve"}, {"decision": "approve"}]}

    score = simulation_match_rate(expected, actual)
    assert score.value == 0.5  # 1 of 2 match


def test_match_rate_scorer_perfect() -> None:
    expected = {"results": [{"decision": "approve"}, {"decision": "deny"}]}
    actual = {"results": [{"decision": "approve"}, {"decision": "deny"}]}

    score = simulation_match_rate(expected, actual)
    assert score.value == 1.0


def test_match_rate_scorer_zero() -> None:
    expected = {"results": [{"decision": "approve"}, {"decision": "deny"}]}
    actual = {"results": [{"decision": "deny"}, {"decision": "approve"}]}

    score = simulation_match_rate(expected, actual)
    assert score.value == 0.0


def test_match_rate_scorer_vacuous_when_no_expected_results() -> None:
    score = simulation_match_rate({}, {"results": [{"decision": "approve"}]})
    assert score.value == 1.0


def test_contradiction_detection_precision_scorer() -> None:
    expected = {"planted_divergence_ids": ["div1", "div2"]}
    actual = {
        "contradictions": [
            _contradiction(rule_id="div1"),
            _contradiction(rule_id="div3", amount_band="51-100"),
        ]
    }

    score = contradiction_detection_precision(expected, actual)
    assert score.value == 0.5  # 1 of 2 detected were real


def test_contradiction_detection_precision_vacuous_when_none_detected() -> None:
    expected = {"planted_divergence_ids": ["div1"]}
    actual = {"contradictions": []}

    score = contradiction_detection_precision(expected, actual)
    assert score.value == 1.0


def test_contradiction_detection_recall() -> None:
    expected = {"planted_divergence_ids": ["div1", "div2"]}
    actual = {"contradictions": [_contradiction(rule_id="div1")]}

    score = contradiction_detection_recall(expected, actual)
    assert score.value == 0.5  # 1 of 2 planted found


def test_contradiction_detection_recall_vacuous_when_none_planted() -> None:
    expected = {"planted_divergence_ids": []}
    actual = {"contradictions": [_contradiction(rule_id="div1")]}

    score = contradiction_detection_recall(expected, actual)
    assert score.value == 1.0


def test_contradiction_detection_recall_zero() -> None:
    expected = {"planted_divergence_ids": ["div1", "div2"]}
    actual = {"contradictions": [_contradiction(rule_id="div3")]}

    score = contradiction_detection_recall(expected, actual)
    assert score.value == 0.0


def test_contradiction_scorers_handle_real_shaped_contradiction_without_crashing() -> None:
    """Real detector output (``detect_contradictions``) never populates
    ``citation`` — it's always ``None`` and there's no top-level ``rule_id``.
    Both scorers must fall back to a structural key instead of raising
    ``KeyError`` on ``c["rule_id"]``, and still return a valid Score."""
    expected = {"planted_divergence_ids": ["div1"]}
    actual = {"contradictions": [_contradiction(rule_id=None)]}

    precision_score = contradiction_detection_precision(expected, actual)
    recall_score = contradiction_detection_recall(expected, actual)

    # No rule_id to match the planted id against, so the structural fallback
    # key can't line up with "div1" — the point is that this returns 0.0
    # gracefully rather than raising.
    assert precision_score.value == 0.0
    assert recall_score.value == 0.0
