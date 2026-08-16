# Eval Harness

Operator and maintainer reference for the eval harness: what it measures today, how it's structured, how to run it, and how the design is meant to grow. For the target design see [DESIGN_DOCUMENT.md Section 5.10](DESIGN_DOCUMENT.md) ("Eval harness") and Section 9 ("Testing and evaluation strategy"); for the "why Inspect" decision, see Section 6 ("Inspect for evals").

**Read this section first if you're picking up eval work:** extraction dataset loading is active for `train` and `dev`, and `ExtractionEval` has a solver seam that runs the extraction pipeline when a usable `LLMClient` is injected. Default local and CI collection remains offline: it reports explicit placeholder extraction metrics rather than constructing an unlogged provider client. Real-provider extraction evals are opt-in. Simulation and end-to-end metrics remain limited until ticket-level ground truth lands. `data/eval/test/` remains forbidden locally.

## Framework: Inspect

[Inspect](https://inspect.ai-safety-institute.org.uk/) (Anthropic's open-source eval framework) provides `Task`, `Scorer`, and `Score` primitives plus a CLI (`inspect eval`) for running eval suites against a dataset and model. It was chosen over Braintrust, Weights & Biases, or a hand-rolled harness because it's purpose-built for LLM evals and integrates cleanly with Anthropic's own tooling — see DESIGN_DOCUMENT.md Section 6 for the full comparison.

`packages/core/src/skiljo_core/eval/` is the harness package, with one module per suite:

- `extraction.py` — the `ExtractionEval` Inspect `Task` (name `"extract"`), wrapping `extraction_recall` and `citation_resolution`.
- `simulation.py` — the `SimulationEval` Inspect `Task` (name `"simulate"`), wrapping `simulation_match_rate`, `contradiction_detection_precision`, and `contradiction_detection_recall`.
- `e2e.py` — the `E2EEval` Inspect `Task` (name `"e2e"`), wrapping `e2e_accuracy`, which composes extraction and simulation into a single accuracy figure for a policy → skill → simulated-decisions example.

All three follow the same scorer structure: standalone pure-function scorers and thin `@scorer`-decorated adapters. Extraction also has an injected-client solver; simulation and end-to-end still await ticket-level ground truth and execution solvers.

## Why the scorer logic is standalone, pure Python

Look at `extraction.py`'s structure: `extraction_recall(expected: dict, actual: dict) -> Score` and `citation_resolution(expected: dict, actual: dict) -> Score` are ordinary functions that take plain dicts and return a `Score` — they know nothing about Inspect's `TaskState`, `Target`, or the eval-run lifecycle. Separately, `recall_scorer()` and `citation_scorer()` are thin `@scorer`-decorated adapters that pull `actual` out of `state.metadata["actual_spec"]` and `expected` out of `target.text` (parsed as JSON), then delegate to the plain functions.

This split is deliberate, not incidental:

- **The scorer logic is unit-testable with zero Inspect machinery.** `packages/core/tests/test_eval_extraction.py` imports `extraction_recall` and `citation_resolution` directly and calls them with hand-built dicts — no `Task`, no dataset, no `inspect eval` CLI invocation, no event loop. This is the entire test suite for scoring correctness (recall math, vacuous-truth cases, citation completeness checks), and it runs in milliseconds as part of the normal `pytest` run.
- **The scoring rule is the thing you actually want to reason about and change.** When a threshold moves or a metric's definition changes, the diff should be in a pure function's logic, not tangled with Inspect's async scorer protocol.
- **It decouples "what does correct mean" from "how does Inspect wire this in."** If Inspect's API changes, or the harness later needs to compute the same recall number outside of an Inspect run (e.g. for the API-persisted `EvalRun` model, or for the report renderer), the pure function is reusable as-is; only the adapter would need to change.

If you're adding a new metric, follow this pattern: write the pure `(expected, actual) -> Score` function first, write plain-dict unit tests for it, then wrap it in a `@scorer(metrics=[mean()])`-decorated adapter that knows how to pull `expected`/`actual` out of Inspect's `TaskState`/`Target`, and add it to the relevant `Task`'s `scorer=[...]` list.

## What `ExtractionEval` actually measures

Two scorers, both operating on skill-spec dicts (the JSON/dict form of a `Skill`, not the Pydantic model). Real `Skill` specs — both hand-labeled ground truth in `data/eval/*/*.skill.yaml` and pipeline output from `assemble_skill` — have no top-level `rules` list; rules live under `decision_zones.{deterministic,llm_assisted,human_only}` per `schemas/skill.schema.json`, and rules have no `id` field either, so both scorers key on structure (`_rule_key`: canonical JSON of `condition` + `action`), not identity:

- **`extraction_recall(expected, actual)`** — `len(expected_rule_keys ∩ actual_rule_keys) / len(expected_rule_keys)`, comparing rules across all three decision zones by their structural `_rule_key`. Vacuously `1.0` if `expected` has no rules (nothing to recall). This is a recall-only metric today; precision (rules extracted that shouldn't have been) is not yet computed, despite being named in the plan and in DESIGN_DOCUMENT.md's description of the suite.
- **`citation_resolution(expected, actual)`** — walks every rule in `actual` (across all three decision zones); the first rule with no citation, an invalid schema-shaped `citation` (`span.start`, `span.end`, `quoted_text`), or an invalid legacy plural citation returns `0.0` immediately (short-circuit, not an average). All rules with complete citations return `1.0`. Vacuously `1.0` if `actual` has no rules. Citation resolution remains a hard invariant: a real extraction result with an unresolved citation is a broken eval run, not a tolerated quality drop.

**Citation shape:** the current extraction pipeline emits the schema's singular `citation` object on each rule. The scorer also accepts the older plural fixture shape to preserve scorer-test compatibility, but real pipeline output is evaluated through the schema shape.

## How contradiction detection is measured (`SimulationEval`)

`packages/core/src/skiljo_core/eval/simulation.py` scores two different things, both against dicts:

- **`simulation_match_rate(expected, actual)`** — zips `expected["results"]` against `actual["results"]` (both a list of per-ticket dicts with a `decision` key, in matching ticket order) and returns the fraction that agree. This mirrors `SimulationReport.match_rate` (see [`docs/simulation.md`](simulation.md#async-batch-processing-enginepy)) but is computed independently, against a labeled example's `results`, not by re-deriving it from a live `compute_report()` call.
- **`contradiction_detection_precision(expected, actual)` / `contradiction_detection_recall(expected, actual)`** — compare `actual["contradictions"]` (a list of real `Contradiction`-shaped dicts — see `skiljo_core.simulation.contradictions.Contradiction`) against `expected["planted_divergence_ids"]`. Real `Contradiction`s have no top-level `rule_id`, and the detector never populates the optional `citation` field either, so both scorers key each detected contradiction via `_contradiction_key`: `citation.rule_id` if present, otherwise a structural key over `cluster_key` + written/observed decision. This is the mechanically-measurable check that makes [planted contradiction](learning/GLOSSARY.md#planted-contradiction) detection a real eval metric rather than a vibe: a labeled example specifies exactly which `DivergenceSpec.rule_id`s were planted into its shadow policy (see [`docs/simulation.md`](simulation.md#shadow-policy-design-generatorpy)), and recall/precision are computed directly against that set. Precision is vacuously `1.0` when nothing was detected (no false positives to penalize); recall is vacuously `1.0` when nothing was planted. The acceptance target from CLAUDE.md is ≥0.8 recall on planted divergences with ≤1 false positive per run — the recall number this scorer produces is the direct measurement of that target, though the "≤1 false positive per run" half of the target is a count, not a rate, so it isn't fully captured by the precision score alone; check `len(detected - planted)` directly if you need the raw false-positive count. Note that until the detector actually attaches citations, the structural fallback key means detected contradictions can't line up with `planted_divergence_ids` by rule identity at all — see the code's docstring for the honest limitation this leaves in place.

`state.metadata["actual_spec"]` is populated by `extraction_solver()` after it calls `run_extraction_pipeline()` with an injected client. `state.metadata["actual_result"]` and `state.metadata["actual_e2e"]` still await simulation/e2e solver work and ticket-level ground truth.

## Dataset: train / dev / test split

**Target design** (DESIGN_DOCUMENT.md Section 9): `data/eval/train/` (30 examples, used freely during development), `data/eval/dev/` (15 examples, used to validate changes before opening a PR), `data/eval/test/` (15 examples, CI-only, CODEOWNERS-gated, never manually inspected).

**Current state:** the full 60-example split is landed — `data/eval/train/` has all 30 examples, `data/eval/dev/` has all 15, and `data/eval/test/` has all 15 (gated by a `.CODEOWNERS` placeholder at `data/eval/test/.CODEOWNERS`, contents `* @no-one` — nobody owns it, so it can't be casually approved for a merge that reads it). This is plan #51 ("expand labeled set to 60 examples with train/dev/test split"), complete. `data/eval/README.md` documents the split rationale and, notably, the corpus-allocation discipline: specific documents (Steam refund policy, Shopify subscription policy, Cloudflare Business SLA + Billing Policy, DigitalOcean Droplets SLA family) are reserved for `test/` specifically so a *new* rule cluster — not one already seen in `train/`/`dev/` — lands in the held-out set, rather than just holding out an arbitrary 15 examples that might duplicate patterns already used for iteration. Each example is a `NN_<slug>.policy.txt` / `NN_<slug>.skill.yaml` pair (e.g. `01_notion.policy.txt` / `01_notion.skill.yaml`), the latter a hand-labeled ground-truth `Skill` spec validated against `schemas/skill.schema.json`.

`skiljo_core.eval.dataset_loader` turns the train/dev pairs into Inspect `Sample`s (policy text as input, skill spec as target), and `ExtractionEval` wires that dataset into an explicit extraction solver. Call `ExtractionEval(split=..., llm_client=...)` or `collect_extraction_metrics(..., llm_client=...)` with an application-configured client to produce real extraction results. The collector intentionally does not construct a provider client itself, because every real LLM call must use the normal logging/configuration boundary. Simulation/e2e retain their current limited metrics until ticket-level ground truth and their execution solvers land.

**Why the split matters, and why `test/` is off-limits** (this is a hygiene discipline the codebase enforces even before the `test/` directory itself exists): train is for iterating on prompts and pipeline logic; dev is a check before opening a PR that you haven't quietly overfit to train; test is the only number that means anything about generalization, and the moment a human reads its contents to "understand a failure," it stops being held-out data — every future prompt tweak is then implicitly informed by knowledge of the test set, even unintentionally. CLAUDE.md's invariant is explicit: never read, print, summarize, or tune against `data/eval/test/`; if asked to debug a test-set failure, work from aggregate metrics only. The plan calls for a CODEOWNERS rule (`data/eval/test/.CODEOWNERS` naming a nobody-owner) as a light mechanical speed bump — but as DESIGN_DOCUMENT.md itself notes, this is "mostly social hygiene rather than enforcement." The actual guarantee is the discipline of the people running the harness, not a technical control.

## Running evals

**Today:** every suite's scorer logic is exercised via ordinary `pytest`, with no real dataset or LLM calls involved:

```bash
uv run pytest packages/core/tests/test_eval_extraction.py -v
uv run pytest packages/core/tests/test_eval_simulation.py -v
uv run pytest packages/core/tests/test_eval_e2e.py -v
```

This is folded into the normal `uv run pytest` / `make test` run.

Separately, `make eval-extraction` / `make eval-simulation` / `make eval-e2e` run each Task through Inspect's CLI. The extraction task loads train/dev data, but a CLI model name alone does not supply the pipeline's `LLMClient`; use the programmatic injected-client seam for real extraction until an application-configured eval entrypoint is added. `mockllm/model` needs no API key and makes no network call, which is why it remains the default for local/CI metrics.

`skiljo_core.eval.collect_metrics` (`uv run python -m skiljo_core.eval.collect_metrics --output eval-results.json`) runs all three suites this way and flattens their scorer means into the Section 9 metric names in one JSON file — this is what `.github/workflows/eval.yml` calls to produce the artifact `scripts/check_regression.py` gates on. See "CI status" below.

Real extraction metrics are available through the injected-client seam today. Simulation and end-to-end remain planned extensions: they need ticket-level ground truth plus solvers that populate their respective metadata keys before their metrics can become meaningful.

## Persistent metric history

`POST /eval-runs` and `GET /eval-runs` (`packages/api/src/skiljo_api/routers/evals.py`) are implemented and tested (`packages/api/tests/test_eval_runs.py`): `POST` records an `EvalRun` row (`commit_sha`, `dataset_version`, `model`, `metrics` as a JSONB blob, `ran_at`); `GET` lists runs most-recent-first with optional `model`/`commit_sha` filters. This is the persistence layer for "metric trends over time" — but nothing calls `POST /eval-runs` automatically yet, because there's no CI step that runs a suite and reports its numbers (see below). Right now the endpoint exists and works; it's just not wired to anything that produces real metrics. The `EvalRun` model (`packages/core/src/skiljo_core/db/models.py`) is backed by a committed Alembic migration — `packages/core/alembic/versions/fdf7e2230a2a_initial_schema.py` creates the `eval_runs` table as part of the initial schema — so a fresh database migrated via `alembic upgrade head` does have the table; it's just not written to outside of tests yet.

## CI status

`.github/workflows/ci.yml` runs `uv run pytest` (all Python tests, including every eval suite's scorer unit tests) and `uv run mypy` / `ruff check` on every push and PR.

`.github/workflows/eval.yml` (plan #52) is the dedicated eval gate, running on every `pull_request`:

1. Runs the eval-suite `pytest` files explicitly (redundant with `ci.yml`'s full run, but keeps eval-specific failures visible as their own check).
2. `uv run python -m skiljo_core.eval.collect_metrics --output eval-results.json` — runs all three Tasks against `mockllm/model` and writes their scorer means as `eval-results.json`.
3. `scripts/check_regression.py` normally diffs `eval-results.json` against `data/eval/baseline_metrics.json` **as committed on `origin/main`**. A PR that deliberately changes the baseline must receive the `approved-eval-baseline-refresh` label; only then does the workflow use that reviewed working-tree baseline before the post-merge refresh job runs. It fails the job if any metric drops beyond its Section 9 budget, or if `citation_resolution` isn't exactly `1.0`.
4. Uploads `eval-results.json` as a build artifact regardless of outcome.

**The honest caveat, stated plainly:** default local/CI collection has no injected `LLMClient`, so extraction recall is explicitly reported as `0.0` and citation resolution as vacuous `1.0`; these are availability placeholders, not real provider metrics. The committed baseline intentionally matches this offline unavailable-client state so the regression gate compares like with like. Simulation/e2e remain limited by missing ticket-level ground truth. Do not read a passing plumbing gate as a quality result. A deliberate, reviewed baseline update is required when real provider metrics are collected.

**Not yet wired:** `POST /eval-runs` (plan #53's persistence API) is not called from `eval.yml`. The table it writes to already exists via migration (see "Persistent metric history" above), so wiring this up is purely a matter of adding a step to `eval.yml` that POSTs `collect_metrics.py`'s output after it's produced.

## Regression thresholds (target — enforced by CI gating)

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
