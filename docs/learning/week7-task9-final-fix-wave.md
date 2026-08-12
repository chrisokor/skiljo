# Week 7 Task 9: Final Review Fix Wave

## What Was Built

This wave tightened the evidence boundary across extraction, simulation reports,
contradiction metrics, fixtures, and cross-document comparison.

The train/dev citation audit inspected all 145 current rule-to-quote pairings.
It corrected 45 obvious weak citations across 23 skill files and expanded the
helper's exact reviewed override set to 54 rules. The synthetic refund fixture
now has a source policy whose spans resolve instead of fabricated `"x"` quotes.

Simulation reports no longer infer a rule citation from decision text. Cluster
metrics now describe only the selected representative decision pair. Extraction
drops invalid citation candidates when a valid rule remains and fails when none
remain. Cross-document conflicts now require overlapping predicate fields and
reject provably disjoint equality or numeric constraints before conflict review.

## Non-Obvious Concepts

See [Execution provenance](GLOSSARY.md#execution-provenance) for why a unique
action string still cannot identify an executed rule. See [Predicate overlap
guard](GLOSSARY.md#predicate-overlap-guard) for the deliberately incomplete but
useful mechanical conflict check.

Mechanical citation resolution and semantic support are separate guarantees.
`source[start:end] == quoted_text` proves location, not relevance. Exact reviewed
overrides protect selected semantic decisions, while unreviewed helper output is
described only as a mechanically valid candidate.

## Why This Way

The report fix is conservative because adding rule identity to the generated
simulation schema would enlarge this final wave and require codegen in both
languages. Persisting `null` is truthful under the current contract.

The cross-document guard handles only cases it can prove cheaply. Pure
conjunctions permit straightforward equality and interval checks; OR trees are
left for later rather than approximated unsafely. The extraction change similarly
keeps the documented repair boundary small: malformed candidates are dropped,
and all LLM activity remains behind `LLMClient`.

## Where To Look

- `scripts/add_eval_citations.py` owns candidate selection and exact overrides.
- `packages/core/src/skiljo_core/extraction/pipeline.py` filters invalid citations.
- `packages/core/src/skiljo_core/simulation/contradictions.py` computes pair metrics.
- `packages/core/src/skiljo_core/simulation/cross_document.py` applies overlap guards.
- `packages/api/src/skiljo_api/routers/simulations.py` persists report evidence.
- Focused regressions live beside each component and in `test_eval_citations.py`.
