# Week 7 Task 4: Eval Ground-Truth Citations

## What Was Built

Every rule in the 30 train and 15 dev hand-labeled eval skills now includes a
character-offset citation. Each citation stores a half-open span and the exact
policy text at that span, giving the ground truth the same provenance contract
as extracted skills.

The task also adds `scripts/add_eval_citations.py`. It derives a candidate
policy paragraph from literal action and predicate terms, applies exact
reviewed overrides for selected rules, and validates every persisted citation
with the production citation validator. The script is idempotent: after
citations exist, it validates them and, under `--write`, replaces stale reviewed
mappings without duplicating citation blocks.

## Key Concepts

See [Character-offset citation](GLOSSARY.md#character-offset-citation) for the
source-coordinate contract. The important property is that provenance is
checked mechanically: `quoted_text` must exactly equal
`policy_text[start:end]`, rather than merely looking plausible to an LLM or a
reviewer.

## Why This Way

The eval data is a ground-truth artifact, so its citations must be reviewable
and reproducible. The helper uses deterministic literal matching to propose
whole source paragraphs. That heuristic is only a candidate selector; it does
not prove that the paragraph supports the rule. Exact reviewed overrides cover
54 high-risk rules and preserve the existing YAML layout, avoiding a broad
serialization-only diff.

This gives the eval loader a durable invariant: any train or dev rule it
returns has a non-empty, source-resolving citation. The loader already retains
complete rule dictionaries, so no loader implementation change was needed.

## Where To Look

- `scripts/add_eval_citations.py` derives, writes, and validates citations.
- `packages/core/tests/test_eval_dataset_loader.py` enforces the citation
  invariant for the permitted train and dev splits.
- `data/eval/train/*.skill.yaml` and `data/eval/dev/*.skill.yaml` contain the
  resulting 145 source citations.
- `packages/core/src/skiljo_core/extraction/citation_validator.py` provides
  the shared span-and-quote mechanical check.

## Review Fixes

Offset validation alone cannot establish that a citation supports a rule. The
final audit inspected the action-to-quote pairing for all 145 current train/dev
rules, corrected 45 obvious title-only, adjacent-paragraph, and incomplete
evidence cases across 23 skill files, and expanded the exact override set to 54
rules total. The remaining 91 citations still have mechanical span guarantees
and were screened for obvious mismatches, but are not claimed to have an
automated semantic guarantee. In validation mode, the helper compares reviewed
citations with their exact unique approved excerpts, catching replacement with
a merely in-bounds but irrelevant span.
