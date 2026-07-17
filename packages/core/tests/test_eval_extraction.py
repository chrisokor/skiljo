"""Tests for the extraction eval suite (plan #48).

Verifies:
- ExtractionEval task exists with correct name and scorers wired
- extraction_recall scorer calculates recall correctly
- citation_resolution scorer validates citation completeness
"""

from skiljo_core.eval.extraction import (
    ExtractionEval,
    citation_resolution,
    extraction_recall,
)


def test_extraction_eval_task_exists() -> None:
    eval_task = ExtractionEval()
    assert eval_task.name == "extract"
    assert eval_task.scorer is not None


def test_extraction_scorer_calculates_recall() -> None:
    expected = {"rules": [{"id": "r1"}, {"id": "r2"}]}
    actual = {"rules": [{"id": "r1"}, {"id": "r3"}]}

    score = extraction_recall(expected, actual)
    assert score.value == 0.5  # 1 of 2 rules found


def test_extraction_scorer_recall_perfect() -> None:
    expected = {"rules": [{"id": "r1"}, {"id": "r2"}]}
    actual = {"rules": [{"id": "r1"}, {"id": "r2"}]}

    score = extraction_recall(expected, actual)
    assert score.value == 1.0


def test_extraction_scorer_recall_zero() -> None:
    expected = {"rules": [{"id": "r1"}, {"id": "r2"}]}
    actual = {"rules": [{"id": "r3"}]}

    score = extraction_recall(expected, actual)
    assert score.value == 0.0


def test_extraction_scorer_recall_vacuous_when_no_expected_rules() -> None:
    # When expected has no rules, recall is vacuously 1.0
    score = extraction_recall({}, {"rules": [{"id": "r1"}]})
    assert score.value == 1.0


def test_extraction_scorer_validates_citations() -> None:
    # Valid: all rules have complete citations
    valid: dict = {
        "rules": [
            {
                "id": "r1",
                "citations": [
                    {"span_start": 0, "span_end": 10, "quoted_text": "text"}
                ],
            }
        ]
    }
    score = citation_resolution({}, valid)
    assert score.value == 1.0

    # Invalid: rule has empty citations list
    invalid: dict = {"rules": [{"id": "r1", "citations": []}]}
    score = citation_resolution({}, invalid)
    assert score.value == 0.0


def test_citation_resolution_missing_field() -> None:
    # Citation present but missing span_end
    broken: dict = {
        "rules": [
            {
                "id": "r1",
                "citations": [{"span_start": 0, "quoted_text": "text"}],
            }
        ]
    }
    score = citation_resolution({}, broken)
    assert score.value == 0.0


def test_citation_resolution_no_rules() -> None:
    # No rules means vacuous 1.0
    score = citation_resolution({}, {"rules": []})
    assert score.value == 1.0


def test_citation_resolution_multiple_rules_all_valid() -> None:
    spec: dict = {
        "rules": [
            {
                "id": "r1",
                "citations": [
                    {"span_start": 0, "span_end": 5, "quoted_text": "abc"}
                ],
            },
            {
                "id": "r2",
                "citations": [
                    {"span_start": 10, "span_end": 20, "quoted_text": "def"}
                ],
            },
        ]
    }
    score = citation_resolution({}, spec)
    assert score.value == 1.0
