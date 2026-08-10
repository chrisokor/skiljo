"""Tests for the eval dataset loader (plan #57).

Verifies `load_extraction_dataset` turns the real `data/eval/{train,dev}/`
labeled pairs into `ExtractionExample`s, and that `ExtractionDataset`
satisfies the minimal protocol Inspect's `Task(dataset=...)` needs
(`__iter__` + `__len__`; see `dataset_loader.py`'s docstring on why the full
`Sequence` protocol isn't required).

`data/eval/test/` is intentionally never exercised here (CLAUDE.md system
invariant 5) -- `test_load_extraction_dataset_rejects_test_split` checks the
loader itself refuses it, not that this test file reads its contents.
"""

from __future__ import annotations

import pytest

from skiljo_core.eval.dataset_loader import (
    ExtractionDataset,
    ExtractionExample,
    load_extraction_dataset,
)


def test_load_extraction_dataset_from_disk() -> None:
    dataset = load_extraction_dataset(split="train")
    assert len(dataset.examples) == 30
    for ex in dataset.examples:
        assert isinstance(ex.input["policy_text"], str)
        assert ex.input["policy_text"]  # non-empty
        assert isinstance(ex.target["expected_rules"], list)
        assert isinstance(ex.target["expected_e2e_accuracy"], float)


def test_load_extraction_dataset_dev_split() -> None:
    dataset = load_extraction_dataset(split="dev")
    assert len(dataset.examples) == 15


def test_load_extraction_dataset_rejects_test_split() -> None:
    with pytest.raises(ValueError, match="off-limits"):
        load_extraction_dataset(split="test")


def test_load_extraction_dataset_every_example_has_rules() -> None:
    # Every hand-labeled example in the corpus has at least one rule across
    # its three decision zones -- a zero-rule example would be a labeling bug.
    dataset = load_extraction_dataset(split="train")
    for ex in dataset.examples:
        assert len(ex.expected_rules) > 0


def test_extraction_dataset_implements_inspect_protocol() -> None:
    dataset = ExtractionDataset(examples=[])
    assert hasattr(dataset, "__iter__")
    assert hasattr(dataset, "__len__")
    assert len(dataset) == 0


def test_extraction_dataset_iterates_to_samples() -> None:
    example = ExtractionExample(
        policy_text="Refunds are issued within 30 days.",
        expected_rules=[{"condition": {"all": []}, "action": "approve_refund"}],
        expected_e2e_accuracy=0.0,
    )
    dataset = ExtractionDataset(examples=[example])

    samples = list(dataset)
    assert len(samples) == 1
    sample = samples[0]
    assert sample.input == example.policy_text
    assert "approve_refund" in sample.target
