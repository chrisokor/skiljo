"""Tests for the extraction eval suite (plan #48).

Verifies:
- ExtractionEval task exists with correct name and scorers wired
- extraction_recall scorer calculates recall correctly
- citation_resolution scorer validates citation completeness

Ground-truth and pipeline-output Skill specs (see ``schemas/skill.schema.json``
and ``schemas/rule.schema.json``) have no top-level ``rules`` list and no
``id`` field on individual rules — rules live under
``decision_zones.{deterministic,llm_assisted,human_only}`` and are identified
structurally by their ``condition`` + ``action``. Fixtures below use that real
shape (plan #54: the original fixtures used an ``{"rules": [{"id": ...}]}``
shape that never occurs in real data, which made both scorers vacuously
score 1.0 against every real extraction).
"""

from skiljo_core.eval.extraction import (
    ExtractionEval,
    citation_resolution,
    extraction_recall,
)


def _skill(*, deterministic: list[dict] | None = None) -> dict:
    return {
        "decision_zones": {
            "deterministic": deterministic or [],
            "llm_assisted": [],
            "human_only": [],
        }
    }


def _rule(action: str, field: str = "refund_amount", value: float = 100.0, citations: list[dict] | None = None) -> dict:
    rule: dict = {
        "condition": {"all": [{"field": field, "op": "lte", "value": value}]},
        "action": action,
    }
    if citations is not None:
        rule["citations"] = citations
    return rule


def test_extraction_eval_task_exists() -> None:
    eval_task = ExtractionEval()
    assert eval_task.name == "extract"
    assert eval_task.scorer is not None


def test_extraction_scorer_calculates_recall() -> None:
    expected = _skill(deterministic=[_rule("approve_refund"), _rule("deny_refund", value=500.0)])
    actual = _skill(deterministic=[_rule("approve_refund"), _rule("escalate", value=999.0)])

    score = extraction_recall(expected, actual)
    assert score.value == 0.5  # 1 of 2 rules found


def test_extraction_scorer_recall_perfect() -> None:
    expected = _skill(deterministic=[_rule("approve_refund"), _rule("deny_refund", value=500.0)])
    actual = _skill(deterministic=[_rule("approve_refund"), _rule("deny_refund", value=500.0)])

    score = extraction_recall(expected, actual)
    assert score.value == 1.0


def test_extraction_scorer_recall_zero() -> None:
    expected = _skill(deterministic=[_rule("approve_refund"), _rule("deny_refund", value=500.0)])
    actual = _skill(deterministic=[_rule("escalate", value=999.0)])

    score = extraction_recall(expected, actual)
    assert score.value == 0.0


def test_extraction_scorer_recall_vacuous_when_no_expected_rules() -> None:
    # When expected has no rules, recall is vacuously 1.0
    score = extraction_recall({}, _skill(deterministic=[_rule("approve_refund")]))
    assert score.value == 1.0


def test_extraction_scorer_recall_matches_across_decision_zones() -> None:
    # A rule expected in the deterministic zone but extracted into llm_assisted
    # still counts as a structural match — recall is about the rule, not the zone.
    expected = _skill(deterministic=[_rule("approve_refund")])
    actual = {
        "decision_zones": {
            "deterministic": [],
            "llm_assisted": [{**_rule("approve_refund"), "requires_human_approval": True}],
            "human_only": [],
        }
    }
    score = extraction_recall(expected, actual)
    assert score.value == 1.0


def test_extraction_scorer_validates_citations() -> None:
    # Valid: all rules have complete citations
    valid = _skill(
        deterministic=[
            _rule("approve_refund", citations=[{"span_start": 0, "span_end": 10, "quoted_text": "text"}])
        ]
    )
    score = citation_resolution({}, valid)
    assert score.value == 1.0

    # Invalid: rule has empty citations list
    invalid = _skill(deterministic=[_rule("approve_refund", citations=[])])
    score = citation_resolution({}, invalid)
    assert score.value == 0.0


def test_citation_resolution_missing_field() -> None:
    # Citation present but missing span_end
    broken = _skill(
        deterministic=[_rule("approve_refund", citations=[{"span_start": 0, "quoted_text": "text"}])]
    )
    score = citation_resolution({}, broken)
    assert score.value == 0.0


def test_citation_resolution_no_rules() -> None:
    # No rules means vacuous 1.0
    score = citation_resolution({}, _skill())
    assert score.value == 1.0


def test_citation_resolution_multiple_rules_all_valid() -> None:
    spec = _skill(
        deterministic=[
            _rule("approve_refund", citations=[{"span_start": 0, "span_end": 5, "quoted_text": "abc"}]),
            _rule("deny_refund", value=500.0, citations=[{"span_start": 10, "span_end": 20, "quoted_text": "def"}]),
        ]
    )
    score = citation_resolution({}, spec)
    assert score.value == 1.0


def test_citation_resolution_reflects_missing_schema_field_on_real_shaped_data() -> None:
    """Rules with no ``citations`` key at all (the real current schema shape,
    since ``rule.schema.json`` has no citations field yet) score 0.0 rather
    than being silently skipped. This is the intended, honest behavior."""
    spec = _skill(deterministic=[_rule("approve_refund")])  # no citations key
    score = citation_resolution({}, spec)
    assert score.value == 0.0
