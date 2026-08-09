# Eval Harness

Operator and maintainer reference for the eval harness: what it measures today, how it's structured, how to run it, and how the design is meant to grow. For the target design see [DESIGN_DOCUMENT.md Section 5.10](DESIGN_DOCUMENT.md) ("Eval harness") and Section 9 ("Testing and evaluation strategy"); for the "why Inspect" decision, see Section 6 ("Inspect for evals").

**Read this section first if you're picking up eval work:** this doc describes the harness as it exists in the repo right now, which is still smaller than the target design in DESIGN_DOCUMENT.md in a few specific ways called out below. All three eval suites (extraction, simulation, end-to-end) and the eval-run persistence API are built. CI regression *gating* (a dedicated workflow that runs the suites on every PR and blocks merge on a drop) is not — `ci.yml` runs the suites' unit tests via plain `pytest`, but nothing yet runs `inspect eval` against real data or diffs metrics against `main`. The dataset's `train/` split is complete (30 examples); `dev/` and `test/` exist as directories but are still being populated. Where this doc says "planned," treat that as a TODO pointer, not a description of running code.

## Framework: Inspect

[Inspect](https://inspect.ai-safety-institute.org.uk/) (Anthropic's open-source eval framework) provides `Task`, `Scorer`, and `Score` primitives plus a CLI (`inspect eval`) for running eval suites against a dataset and model. It was chosen over Braintrust, Weights & Biases, or a hand-rolled harness because it's purpose-built for LLM evals and integrates cleanly with Anthropic's own tooling — see DESIGN_DOCUMENT.md Section 6 for the full comparison.

`packages/core/src/skiljo_core/eval/` is the harness package, with one module per suite:

- `extraction.py` — the `ExtractionEval` Inspect `Task` (name `"extract"`), wrapping `extraction_recall` and `citation_resolution`.
- `simulation.py` — the `SimulationEval` Inspect `Task` (name `"simulate"`), wrapping `simulation_match_rate`, `contradiction_detection_precision`, and `contradiction_detection_recall`.
- `e2e.py` — the `E2EEval` Inspect `Task` (name `"e2e"`), wrapping `e2e_accuracy`, which composes extraction and simulation into a single accuracy figure for a policy → skill → simulated-decisions example.

All three follow the identical structure described in the next section: standalone pure-function scorers, thin `@scorer`-decorated adapters, and a `Task` constructed with `dataset=None` (see "Dataset" section below for what that placeholder means and what it will take to remove it).

## Why the scorer logic is standalone, pure Python

Look at `extraction.py`'s structure: `extraction_recall(expected: dict, actual: dict) -> Score` and `citation_resolution(expected: dict, actual: dict) -> Score` are ordinary functions that take plain dicts and return a `Score` — they know nothing about Inspect's `TaskState`, `Target`, or the eval-run lifecycle. Separately, `recall_scorer()` and `citation_scorer()` are thin `@scorer`-decorated adapters that pull `actual` out of `state.metadata["actual_spec"]` and `expected` out of `target.text` (parsed as JSON), then delegate to the plain functions.

This split is deliberate, not incidental:

- **The scorer logic is unit-testable with zero Inspect machinery.** `packages/core/tests/test_eval_extraction.py` imports `extraction_recall` and `citation_resolution` directly and calls them with hand-built dicts — no `Task`, no dataset, no `inspect eval` CLI invocation, no event loop. This is the entire test suite for scoring correctness (recall math, vacuous-truth cases, citation completeness checks), and it runs in milliseconds as part of the normal `pytest` run.
- **The scoring rule is the thing you actually want to reason about and change.** When a threshold moves or a metric's definition changes, the diff should be in a pure function's logic, not tangled with Inspect's async scorer protocol.
- **It decouples "what does correct mean" from "how does Inspect wire this in."** If Inspect's API changes, or the harness later needs to compute the same recall number outside of an Inspect run (e.g. for the API-persisted `EvalRun` model, or for the report renderer), the pure function is reusable as-is; only the adapter would need to change.

If you're adding a new metric, follow this pattern: write the pure `(expected, actual) -> Score` function first, write plain-dict unit tests for it, then wrap it in a `@scorer(metrics=[mean()])`-decorated adapter that knows how to pull `expected`/`actual` out of Inspect's `TaskState`/`Target`, and add it to the relevant `Task`'s `scorer=[...]` list.

## What `ExtractionEval` actually measures

Two scorers, both operating on skill-spec dicts (the JSON/dict form of a `Skill`, not the Pydantic model — this matters because both scorers assume an `{"rules": [...]}` list-of-rules shape with `id` and `citations` keys per rule that **does not exist in the current `Skill`/`Rule` schema** — see the note below):

- **`extraction_recall(expected, actual)`** — `len(expected_rule_ids ∩ actual_rule_ids) / len(expected_rule_ids)`, comparing rule `id`s. Vacuously `1.0` if `expected` has no rules (nothing to recall). This is a recall-only metric today; precision (rules extracted that shouldn't have been) is not yet computed, despite being named in the plan and in DESIGN_DOCUMENT.md's description of the suite.
- **`citation_resolution(expected, actual)`** — walks every rule in `actual`; the first rule with no `citations` entries, or a citation missing `span_start`/`span_end`/`quoted_text`, returns `0.0` immediately (short-circuit, not an average). All rules with complete citations on every entry returns `1.0`. Vacuously `1.0` if `actual` has no rules.

**Important caveat:** as documented in [`docs/extraction.md`](extraction.md#citations--design-intent-vs-current-implementation), the extraction pipeline does not currently attach `id` or `citations` to rules at all — the schema doesn't have those fields. These scorers are written against the *target* schema shape described in DESIGN_DOCUMENT.md, ahead of the schema and pipeline actually producing that shape. Practically: the scorer unit tests (which hand-construct dicts with `id`/`citations` already present) pass and correctly validate the scoring *logic*; running `citation_resolution` against real output from `run_extraction_pipeline()` today would score `0.0` for every rule, because no rule in the current schema has a `citations` key to check. Don't read a `0.0` from a real pipeline run as a citation-resolution regression — it's an expected consequence of the schema gap, not a signal about extraction quality, until the schema/pipeline work described in `docs/extraction.md` lands.

## How contradiction detection is measured (`SimulationEval`)

`packages/core/src/skiljo_core/eval/simulation.py` scores two different things, both against dicts:

- **`simulation_match_rate(expected, actual)`** — zips `expected["results"]` against `actual["results"]` (both a list of per-ticket dicts with a `decision` key, in matching ticket order) and returns the fraction that agree. This mirrors `SimulationReport.match_rate` (see [`docs/simulation.md`](simulation.md#async-batch-processing-enginepy)) but is computed independently, against a labeled example's `results`, not by re-deriving it from a live `compute_report()` call.
- **`contradiction_detection_precision(expected, actual)` / `contradiction_detection_recall(expected, actual)`** — compare `actual["contradictions"]` (a list of dicts with a `rule_id`) against `expected["planted_divergence_ids"]`. This is the mechanically-measurable check that makes [planted contradiction](learning/GLOSSARY.md#planted-contradiction) detection a real eval metric rather than a vibe: a labeled example specifies exactly which `DivergenceSpec.rule_id`s were planted into its shadow policy (see [`docs/simulation.md`](simulation.md#shadow-policy-design-generatorpy)), and recall/precision are computed directly against that set. Precision is vacuously `1.0` when nothing was detected (no false positives to penalize); recall is vacuously `1.0` when nothing was planted. The acceptance target from CLAUDE.md is ≥0.8 recall on planted divergences with ≤1 false positive per run — the recall number this scorer produces is the direct measurement of that target, though the "≤1 false positive per run" half of the target is a count, not a rate, so it isn't fully captured by the precision score alone; check `len(detected - planted)` directly if you need the raw false-positive count.

Both suites' `actual`-side data — `state.metadata["actual_spec"]` for extraction, `state.metadata["actual_result"]` for simulation, `state.metadata["actual_e2e"]` for e2e — is populated by whatever runs the pipeline/engine against a sample and writes its output into task state before scoring. That "solver" step (the piece that actually calls `run_extraction_pipeline()` or `simulate_batch()` per sample and populates `state.metadata`) is what's still missing before `inspect eval` can run any of these suites against real data — see "Dataset" and "Running evals" below.

## Dataset: train / dev / test split

**Target design** (DESIGN_DOCUMENT.md Section 9): `data/eval/train/` (30 examples, used freely during development), `data/eval/dev/` (15 examples, used to validate changes before opening a PR), `data/eval/test/` (15 examples, CI-only, CODEOWNERS-gated, never manually inspected).

**Current state:** `data/eval/train/` has all 30 planned examples; `data/eval/dev/` is in progress (partially populated as of this writing); `data/eval/test/` exists only as an empty directory containing a `.CODEOWNERS` placeholder (`data/eval/test/.CODEOWNERS`, contents `* @no-one` — nobody owns it, so it can't be casually approved for a merge that reads it) with no labeled examples yet. This is plan #51 ("expand labeled set to 60 examples with train/dev/test split"), still landing. `data/eval/README.md` documents the split rationale and, notably, the corpus-allocation discipline: specific documents (Steam refund policy, Shopify subscription policy, Cloudflare Business SLA + Billing Policy, DigitalOcean Droplets SLA family) are reserved for `test/` specifically so a *new* rule cluster — not one already seen in `train/`/`dev/` — lands in the held-out set, rather than just holding out an arbitrary 15 examples that might duplicate patterns already used for iteration. Each example is a `NN_<slug>.policy.txt` / `NN_<slug>.skill.yaml` pair (e.g. `01_notion.policy.txt` / `01_notion.skill.yaml`), the latter a hand-labeled ground-truth `Skill` spec validated against `schemas/skill.schema.json`.

There is still no dataset loader module wiring these files into a real Inspect `Dataset`, and no "solver" step that runs the extraction pipeline or simulation engine against a sample and writes its output into `state.metadata` for scoring. All three `Task`s (`ExtractionEval`, `SimulationEval`, `E2EEval`) are constructed with `dataset=None`, which makes Inspect supply a single dummy sample so each task can be imported and instantiated without real data on disk — this is the actual gap between "the scorer logic is correct and tested" (true today) and "`inspect eval` produces a real recall/match-rate number against `data/eval/train/`" (not yet possible). Closing it means: a loader that turns each `NN_*.policy.txt`/`NN_*.skill.yaml` pair into an Inspect `Sample` (policy text as input, skill spec as `target`), and a solver that calls `run_extraction_pipeline()` (or `simulate_batch()`, or both for e2e) and stashes the result in `state.metadata` under the key each scorer expects (`"actual_spec"`, `"actual_result"`, `"actual_e2e"` respectively).

**Why the split matters, and why `test/` is off-limits** (this is a hygiene discipline the codebase enforces even before the `test/` directory itself exists): train is for iterating on prompts and pipeline logic; dev is a check before opening a PR that you haven't quietly overfit to train; test is the only number that means anything about generalization, and the moment a human reads its contents to "understand a failure," it stops being held-out data — every future prompt tweak is then implicitly informed by knowledge of the test set, even unintentionally. CLAUDE.md's invariant is explicit: never read, print, summarize, or tune against `data/eval/test/`; if asked to debug a test-set failure, work from aggregate metrics only. The plan calls for a CODEOWNERS rule (`data/eval/test/.CODEOWNERS` naming a nobody-owner) as a light mechanical speed bump — but as DESIGN_DOCUMENT.md itself notes, this is "mostly social hygiene rather than enforcement." The actual guarantee is the discipline of the people running the harness, not a technical control.

## Running evals

**Today:** every suite's scorer logic is exercised via ordinary `pytest`, with no real dataset or LLM calls involved:

```bash
uv run pytest packages/core/tests/test_eval_extraction.py -v
uv run pytest packages/core/tests/test_eval_simulation.py -v
uv run pytest packages/core/tests/test_eval_e2e.py -v
```

This is folded into the normal `uv run pytest` / `make test` run — there is no separate eval invocation path yet, and no `make eval-extraction` / `eval-simulation` / `eval-e2e` targets exist in the `Makefile` despite being named in CLAUDE.md's "Make targets" list. If you go looking for them, they don't exist yet; add them once the dataset loader/solver wiring below lands, so the target has something real to invoke.

**Planned:** once a dataset loader and solver exist (see previous section), `inspect eval packages/core/src/skiljo_core/eval/extraction.py --dataset data/eval/train/` (or `.../eval/simulation.py`, `.../eval/e2e.py`, against `train/` or `dev/`) would run the actual extraction pipeline / simulation engine against real labeled examples via Inspect's CLI, producing a scored log with real recall/match-rate/accuracy numbers. This is not runnable yet — the `dataset=None` placeholder on every `Task` is exactly the gap that blocks it.

## Persistent metric history

`POST /eval-runs` and `GET /eval-runs` (`packages/api/src/skiljo_api/routers/evals.py`) are implemented and tested (`packages/api/tests/test_eval_runs.py`): `POST` records an `EvalRun` row (`commit_sha`, `dataset_version`, `model`, `metrics` as a JSONB blob, `ran_at`); `GET` lists runs most-recent-first with optional `model`/`commit_sha` filters. This is the persistence layer for "metric trends over time" — but nothing calls `POST /eval-runs` automatically yet, because there's no CI step that runs a suite and reports its numbers (see below). Right now the endpoint exists and works; it's just not wired to anything that produces real metrics. One additional gap worth flagging for whoever picks this up: the `EvalRun` model is defined in `packages/core/src/skiljo_core/db/models.py`, but `packages/core/alembic/versions/` only has migrations for the initial schema and the LLM cache table — there is no committed Alembic migration creating `eval_runs` yet, so a fresh database migrated via `alembic upgrade head` would not actually have the table (tests presumably create it via `Base.metadata.create_all` against a test database rather than via migration — check `conftest.py` if you need to confirm this before relying on it in a real deployment).

## CI status

`.github/workflows/ci.yml` runs `uv run pytest` (all Python tests, including every eval suite's scorer unit tests) and `uv run mypy` / `ruff check` on every push and PR — this is the only CI gate that currently touches eval code, and it's testing scorer *logic* and the `eval-runs` API contract, not running any suite against a dataset or comparing metrics to a baseline.

**Planned, not present:** a dedicated `.github/workflows/eval.yml` that runs `inspect eval` against train/dev on every PR, computes the regression thresholds below, calls `POST /eval-runs` with the result, and blocks merge on violation; a regression-check script that diffs current-branch metrics against `origin/main`'s last recorded run. None of this exists in the repo yet — it's the natural next piece once the dataset loader/solver gap above is closed, since there's no meaningful regression number to gate on until a suite can actually run against real data.

## Regression thresholds (target — for when CI gating lands)

From DESIGN_DOCUMENT.md Section 9 / CLAUDE.md system invariant 4:

| Metric | Threshold |
|---|---|
| Extraction recall | must not drop more than 2 percentage points |
| Citation resolution rate | must stay at 100% (any unresolvable citation is a broken build) |
| Contradiction recall | must not drop more than 5 percentage points |
| Simulation match rate | must not drop more than 3 percentage points |
| End-to-end accuracy | must not drop more than 3 percentage points |

**Tuning discipline:** if a change breaks one of these thresholds, the default assumption is that the change is wrong, not the threshold. CLAUDE.md is explicit that a threshold should never be silently bumped to make a failing change pass — a deliberate, documented threshold change (updating this table and DESIGN_DOCUMENT.md Section 9 together, with a stated reason) is the only sanctioned path, and it should be rare.

## Adding a new eval metric

1. Write a pure function `metric_name(expected: dict, actual: dict) -> Score` with no Inspect imports beyond `Score` itself. Decide what "vacuous" input should return (usually `1.0` — nothing to get wrong) and document it in the function's docstring, matching the pattern in `extraction_recall`/`citation_resolution`.
2. Write plain-dict unit tests for the function directly — recall/precision math, the vacuous case, and at least one clearly-wrong case. This is the bulk of the confidence in the metric; get it right here before touching Inspect.
3. Wrap it in a `@scorer(metrics=[mean()])`-decorated adapter that extracts `expected`/`actual` from `state.metadata` / `target.text`, matching `recall_scorer()`/`citation_scorer()` in `extraction.py`.
4. Add the scorer to the relevant `Task`'s `scorer=[...]` list.
5. If the metric is one of the five in the regression-threshold table, update DESIGN_DOCUMENT.md Section 9 and this doc's table together if the threshold itself is changing — never move a threshold silently.
