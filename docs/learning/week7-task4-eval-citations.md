# Week 7 Task 4: Eval Ground-Truth Citations

## What Was Built

Every rule in the 30 train and 15 dev hand-labeled eval skills now includes a
character-offset citation. Each citation stores a half-open span and the exact
policy text at that span, giving the ground truth the same provenance contract
as extracted skills.

The task also adds `scripts/add_eval_citations.py`. It derives a candidate
policy paragraph from literal action and predicate terms, applies a small set
of reviewed overrides for paraphrased rules, and validates every persisted
citation with the production citation validator. The script is idempotent:
after citations exist, it validates them instead of inserting another mapping.

## Key Concepts

See [Character-offset citation](GLOSSARY.md#character-offset-citation) for the
source-coordinate contract. The important property is that provenance is
checked mechanically: `quoted_text` must exactly equal
`policy_text[start:end]`, rather than merely looking plausible to an LLM or a
reviewer.

## Why This Way

The eval data is a ground-truth artifact, so its citations must be reviewable
and reproducible. The helper uses deterministic literal matching to propose
whole source paragraphs, which is conservative when a rule combines several
facts from one paragraph. Three reviewed overrides cover rule wording whose
literal tokens do not occur in the source text. Direct insertion preserves the
existing YAML layout, avoiding a broad serialization-only diff.

This gives the eval loader a durable invariant: any train or dev rule it
returns has a non-empty, source-resolving citation. The loader already retains
complete rule dictionaries, so no loader implementation change was needed.

## Where To Look

- `scripts/add_eval_citations.py` derives, writes, and validates citations.
- `packages/core/tests/test_eval_dataset_loader.py` enforces the citation
  invariant for the permitted train and dev splits.
- `data/eval/train/*.skill.yaml` and `data/eval/dev/*.skill.yaml` contain the
  resulting 146 source citations.
- `packages/core/src/skiljo_core/extraction/citation_validator.py` provides
  the shared span-and-quote mechanical check.

## Review Fixes

Offset validation alone cannot establish that a citation supports a rule. A
small reviewed-evidence override list now covers the known paraphrased and
configuration-sensitive rules. In validation mode, the helper compares those
persisted citations with their exact approved excerpts, catching a future
replacement with a merely in-bounds but irrelevant span. This deliberately
targets known high-risk cases rather than adding broad or subjective NLP
relevance scoring.
