# Week 7 Task 6: Cross-document contradiction UI

## What was built

The Streamlit demo now has a Cross-Document page that compares two distinct,
approved skill versions. It shows every extracted rule side by side with its
condition and mechanically validated character-offset citation, then calls the
existing cross-document endpoint and expands each returned conflict with its
decision surface, actions, rule references, and rationale.

The page deliberately starts from approved, extracted policies rather than
uploading fresh documents. That matches the API contract and keeps comparison
results tied to immutable versions that were already reviewed in the demo.

## Non-obvious concepts

### Streamlit multipage discovery

Streamlit discovers Python files under `src/pages/` automatically and uses the
filename prefix to order them in navigation. `4_Cross_Document.py` therefore
adds the next demo screen without editing a router, app registry, or navigation
link. See [Streamlit multipage navigation](GLOSSARY.md#streamlit-multipage-navigation).

### Cross-document evidence

The detector returns a rule reference for each side of a contradiction as a
decision-zone name and index. The page preserves those references rather than
trying to infer a matching rule from actions, which could be duplicated within
a policy. The side-by-side rule tables supply the corresponding source quote
and character span. See [Decision surface](GLOSSARY.md#decision-surface-cross-document-contradiction-detection)
and [Character-offset citation](GLOSSARY.md#character-offset-citation).

## Why this approach

The original brief proposed uploads followed by extraction, but the real API
accepts `skill_version_ids` only. Selecting approved versions uses the existing
Review workflow, avoids duplicate extraction and LLM calls, and ensures every
displayed rule already carries validated provenance.

The API helper stays a thin `requests.post` wrapper, consistent with the other
demo helpers. Its focused test asserts the exact endpoint payload, preventing a
regression back to raw document upload semantics.

## Where to look

- `packages/demo/src/pages/4_Cross_Document.py`: approved-version selection,
  side-by-side rule display, and conflict evidence.
- `packages/demo/src/api_client.py`: cross-document detector HTTP helper.
- `packages/demo/tests/test_api_client.py`: request contract test.

## Verification

`make lint typecheck test` passed: Ruff and mypy were clean, 234 Python tests
passed with 2 skipped, and all 27 SDK tests passed. The page was also served
locally with Streamlit and returned its application shell at `/Cross_Document`.
