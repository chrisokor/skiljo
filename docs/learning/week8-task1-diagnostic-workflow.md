# Week 8 Task 1: Complete Diagnostic Workflow

## What Changed

The API now has a deterministic local integration test for the full diagnostic path: policy upload, extraction from a persisted policy, immutable skill-version persistence, historical ticket import, simulation by ticket batch, and HTML report generation.

## Why It Matters

This proves Skiljo is no longer just a set of separate endpoints. The product workflow a buyer would evaluate is covered as one path, without requiring a real LLM call or external service in tests.

## Where To Look

- `packages/api/tests/test_diagnostic_workflow.py`
- `packages/api/src/skiljo_api/routers/policies.py`
- `packages/api/src/skiljo_api/routers/tickets.py`
- `packages/api/src/skiljo_api/routers/simulations.py`
