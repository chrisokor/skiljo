"""Tests for the simulation eval suite (plan #49).

Verifies:
- SimulationEval task exists with correct name and scorers wired
- simulation_match_rate scorer calculates ticket decision match rate correctly
- contradiction_detection_precision scorer validates detected-vs-planted precision
- contradiction_detection_recall scorer validates detected-vs-planted recall
"""

from skiljo_core.eval.simulation import (
    SimulationEval,
    contradiction_detection_precision,
    contradiction_detection_recall,
    simulation_match_rate,
)


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
    actual = {"contradictions": [{"rule_id": "div1"}, {"rule_id": "div3"}]}

    score = contradiction_detection_precision(expected, actual)
    assert score.value == 0.5  # 1 of 2 detected were real


def test_contradiction_detection_precision_vacuous_when_none_detected() -> None:
    expected = {"planted_divergence_ids": ["div1"]}
    actual = {"contradictions": []}

    score = contradiction_detection_precision(expected, actual)
    assert score.value == 1.0


def test_contradiction_detection_recall() -> None:
    expected = {"planted_divergence_ids": ["div1", "div2"]}
    actual = {"contradictions": [{"rule_id": "div1"}]}

    score = contradiction_detection_recall(expected, actual)
    assert score.value == 0.5  # 1 of 2 planted found


def test_contradiction_detection_recall_vacuous_when_none_planted() -> None:
    expected = {"planted_divergence_ids": []}
    actual = {"contradictions": [{"rule_id": "div1"}]}

    score = contradiction_detection_recall(expected, actual)
    assert score.value == 1.0


def test_contradiction_detection_recall_zero() -> None:
    expected = {"planted_divergence_ids": ["div1", "div2"]}
    actual = {"contradictions": [{"rule_id": "div3"}]}

    score = contradiction_detection_recall(expected, actual)
    assert score.value == 0.0
