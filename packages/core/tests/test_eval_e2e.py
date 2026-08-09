"""Tests for the end-to-end eval suite (plan #50).

Verifies:
- E2EEval task exists with correct name and scorer wired
- e2e_accuracy scorer measures closeness of observed vs. expected pipeline
  accuracy correctly
"""

import pytest

from skiljo_core.eval.e2e import E2EEval, e2e_accuracy


def test_e2e_eval_task_exists() -> None:
    eval_task = E2EEval()
    assert eval_task.name == "e2e"
    assert eval_task.scorer is not None


def test_e2e_accuracy_perfect_match() -> None:
    expected = {"expected_e2e_accuracy": 0.9}
    actual = {"e2e_accuracy": 0.9}

    score = e2e_accuracy(expected, actual)
    assert score.value == 1.0


def test_e2e_accuracy_partial_error() -> None:
    expected = {"expected_e2e_accuracy": 0.9}
    actual = {"e2e_accuracy": 0.7}

    score = e2e_accuracy(expected, actual)
    assert score.value == pytest.approx(0.8)


def test_e2e_accuracy_worst_case_floors_at_zero() -> None:
    expected = {"expected_e2e_accuracy": 1.0}
    actual = {"e2e_accuracy": 0.0}

    score = e2e_accuracy(expected, actual)
    assert score.value == 0.0


def test_e2e_accuracy_defaults_when_missing_keys() -> None:
    # Both default to 0.0 when keys are absent -> zero error -> perfect score
    score = e2e_accuracy({}, {})
    assert score.value == 1.0


def test_e2e_accuracy_error_direction_does_not_matter() -> None:
    # Overshoot and undershoot by the same margin score identically
    over = e2e_accuracy({"expected_e2e_accuracy": 0.5}, {"e2e_accuracy": 0.7})
    under = e2e_accuracy({"expected_e2e_accuracy": 0.5}, {"e2e_accuracy": 0.3})
    assert over.value == under.value
