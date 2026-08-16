# Week 8 Task 2: Extraction Eval Solver

## What Changed

The extraction eval path now has an explicit solver seam for running the extraction pipeline per train/dev sample and writing the resulting `Skill` spec into `state.metadata["actual_spec"]`.

## Why It Matters

Extraction recall is only useful when it compares expected rules to actual pipeline output. This task closes the empty-actual gap or, when a real provider is not configured, makes that limitation explicit.

## Where To Look

- `packages/core/src/skiljo_core/eval/extraction.py`
- `packages/core/src/skiljo_core/eval/collect_metrics.py`
- `packages/core/tests/test_eval_extraction.py`
