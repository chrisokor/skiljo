# Week 6 Task 7: v1.0 Completion

## What shipped

Week 6 closed out v1.0 with six commits landing before this one:

1. **Inspect dataset loader** (`17c13d6`, plan #57) — `packages/core/src/skiljo_core/eval/dataset_loader.py` turns the labeled `data/eval/{train,dev}/NN_slug.{policy.txt,skill.yaml}` pairs into Inspect `Sample`s, replacing the single vacuous dummy sample the eval suites ran against before. `ExtractionEval`/`SimulationEval`/`E2EEval` now iterate 30 train / 15 dev real examples.
2. **CI baseline refresh** (`493e95c`, plan #58) — `packages/core/src/skiljo_core/eval/baseline.py` + `scripts/update_baseline.py`, wired into `.github/workflows/eval.yml` to refresh `data/eval/baseline_metrics.json` on merge to `main` so the regression gate compares against current reality instead of a stale snapshot.
3. **TypeScript SDK parity** (`bda9919`, plan #59) — `EvalRunsResource` and `CrossDocumentResource` added to `packages/sdk-ts/src/`, giving the SDK full coverage of the API surface (`evalRuns.create/list`, `crossDocument.detect`).
4. **Real policy corpus** (`157ba36` + fixup `bb8c567`, plan #59-addendum) — five real public policy excerpts (Shopify ToS, Shopify help center, Stripe, Cloudflare, DigitalOcean) under `data/policies/`, sized for the cross-document contradiction detector's acceptance case. The fixup commit trimmed the Shopify excerpts after the initial cut risked reproducing test-set-adjacent document text verbatim.
5. **Quality pass** (`1427a64`, plan #60) — `TaskState` import moved from the private `inspect_ai.scorer._scorer` to the public `inspect_ai.solver`; a bearer-auth negative test (`test_bearer_auth_negative.py`); a consistent `{"error": {"code", "message", "details"}}` envelope (`packages/api/src/skiljo_api/error_handler.py`) registered for `HTTPException`, `RequestValidationError`, and any uncaught exception; DESIGN_DOCUMENT.md Section 8/16 updated with the eval-runs and cross-document endpoints.
6. **A6 — contradiction clustering to spec** (`bd9a872`, plan #61) — `packages/core/src/skiljo_core/simulation/contradiction_stats.py` adds a binomial significance test, and `contradictions.py` extends clustering from (amount band × segment) to (amount band × segment × reason × time-window), replacing the week-3 bare frequency threshold with a statistically supported flag.

This task (Task 7) verified all of the above, updated `CLAUDE.md`'s status section, and is writing this debrief.

## Non-obvious concepts

**Honest partial activation (dataset loader).** Wiring a real dataset to `ExtractionEval` does not, by itself, make `extraction_recall` meaningful — no solver step yet calls `run_extraction_pipeline()` per sample and writes the result into task state, so `actual` stays `{}` and recall now scores genuinely low (not a bug) instead of vacuously 1.0. The dataset loader's docstring is explicit about which half of the gap is closed (dataset landed) and which isn't (solver still doesn't exist), rather than letting the commit message imply "eval is now real." Same story for `SimulationEval`/`E2EEval`: they get the real 30/15-example corpus size, but `simulation_match_rate` and contradiction precision/recall keep hitting vacuous-1.0 fallbacks because there's no ticket-level ground truth in `data/eval/` yet. See `GLOSSARY.md`'s existing "Vacuous score" entry — this is the same pattern one level up the stack.

**Binomial test as the statistical-support layer, not a new dependency.** A6 needed to distinguish "this cluster's divergence rate is unusual" from "this cluster's divergence rate is what you'd expect from ordinary noise around the system's baseline error rate." Rather than adding `scipy` for one function, `contradiction_stats.py` implements an exact two-sided binomial test in pure Python (`math.comb` + summing probability mass ≤ the observed outcome's mass) — consistent with CLAUDE.md's "no infrastructure beyond the design" stance extending even to dependencies, not just services.

**Error envelope needs three registration points, not one.** A single `{"error": {...}}` shape has to be produced from three different FastAPI/Starlette failure paths that don't share a code path: explicit `HTTPException`s raised by handlers, Pydantic's `RequestValidationError` on malformed request bodies, and genuinely uncaught exceptions (caught only by registering against the base `Exception` type). `error_handler.py` registers one converter function per path in `main.py` rather than trying to intercept all three in one handler.

## Where the code lives

- **Eval dataset loader**: `packages/core/src/skiljo_core/eval/dataset_loader.py`, tests in `packages/core/tests/test_eval_dataset_loader.py`
- **CI baseline refresh**: `packages/core/src/skiljo_core/eval/baseline.py`, `scripts/update_baseline.py`, `.github/workflows/eval.yml`
- **Contradiction statistics (A6)**: `packages/core/src/skiljo_core/simulation/contradiction_stats.py`, wired into `contradictions.py`
- **SDK parity**: `packages/sdk-ts/src/eval-runs.ts`, `packages/sdk-ts/src/cross-document.ts`
- **Error envelope**: `packages/api/src/skiljo_api/error_handler.py`, registered in `packages/api/src/skiljo_api/main.py`
- **Real policy corpus**: `data/policies/` (Shopify, Stripe, Cloudflare, DigitalOcean excerpts + README)

## Verification for this task

`make lint typecheck test` — ruff clean, mypy clean (`tsc --noEmit` clean), **203 Python passed + 2 skipped, 27 TypeScript passed**. No outstanding `TODO`/`FIXME`/`XXX` markers in `packages/{core,api,demo,sdk-ts}` (one docstring cross-reference in `llm/pricing.py` mentions a *resolved* TODO by name; not an open one).

## Known gaps carried into v1.05

- **Eval solvers**: the dataset loader activates real *inputs*; no solver populates `actual_spec`/`results` yet, so extraction recall will score near-zero against a real model until a solver step is added. This is the natural next eval-harness task, not a regression.
- **Citations**: still no character-offset span field on extracted rules (schema addition, multi-commit).
- **Contradiction detector scale**: still O(n²)-ish sequential clustering; fine under ~50-rule documents, flagged for optimization if the corpus grows.
- **DESIGN_DOCUMENT.md commit-plan drift**: week 6 executed a revised plan (dataset/SDK/A6 work) rather than the document's original commit 57–63 breakdown (which described a Render deployment blueprint). The commit table in DESIGN_DOCUMENT.md Section 12 has not been reconciled — flagged in `CLAUDE.md`'s status section rather than silently resolved; do this before assigning v1.05 commit numbers against that table.

## Next: v1.05

v1.05 is the first revenue product: a self-serve policy consistency checker built on A2 (rendered HTML report) + A3 (cross-document contradiction detector), delivered white-glove to a Controller/Head of Finance Ops. See DESIGN_DOCUMENT.md Section 14 for the full v1.05–v1.5 roadmap.
