# Week 5, Task 10: Eval Harness Integration and Final Cleanup

## What was built

Task 10 is the week's integration checkpoint, not a new feature: verify that
the eval harness built across Tasks 1–9 actually holds together as one
system, then do the "cleanup pass on core package" the plan specifies
(dead-code sweep, type-hint audit, coverage check). The integration
verification found everything green — extraction/simulation/e2e eval
suites, the 60-example train/dev/test dataset split, the CI regression
gate, persistent metric history, cross-document contradiction detection,
and documentation all landed and compose correctly. The cleanup pass found
one real gap (a `TODO` for LLM call cost estimation, never resolved since
week 3) and one type-hygiene gap (14 function signatures using bare `dict`
instead of a parameterized type) and fixed both.

**Files created:**
- `packages/core/src/skiljo_core/llm/pricing.py` — static per-model
  `$/1M tokens` rate table + `estimate_cost_usd()`
- `packages/core/tests/test_llm_pricing.py` — unit tests for the pricing
  function's edge cases (missing tokens, unknown model)

**Files modified:**
- `packages/core/src/skiljo_core/llm/logging.py` — calls
  `estimate_cost_usd()` instead of leaving `cost_estimate_usd` unset
- `packages/core/tests/test_anthropic_client.py` — asserts the DB row now
  carries a computed cost estimate
- `packages/core/src/skiljo_core/eval/{extraction,simulation,e2e}.py` —
  `dict` → `dict[str, Any]` on 14 parameters/returns

## What the eval harness measures, and why each metric matters

The harness (`packages/core/src/skiljo_core/eval/`) has three suites, each
an [Inspect AI](https://inspect.aisi.org.uk/) `Task` wrapping one or more
`Scorer`s:

| Suite | Metric | What it catches |
|---|---|---|
| `extraction.py` | `extraction_recall` | Rules the pipeline missed entirely — the fastest way policy fidelity silently degrades |
| `extraction.py` | `citation_resolution` | A rule with no resolvable citation is a hallucination per CLAUDE.md invariant #3 — this metric is a hard gate, not a quality score |
| `simulation.py` | `simulation_match_rate` | How often the skill's decision agrees with shadow-policy ground truth |
| `simulation.py` | `contradiction_detection_precision` / `_recall` | Whether the contradiction detector finds real planted divergences without crying wolf — the acceptance bar from CLAUDE.md is ≥0.8 recall, ≤1 false positive per run |
| `e2e.py` | `e2e_accuracy` | Whether the *whole* pipeline (extract → simulate) degrades even when each stage looks fine in isolation |

Each metric maps directly to a regression threshold in
`DESIGN_DOCUMENT.md` Section 9 (extraction recall −2pts, citation
resolution 100% no tolerance, contradiction recall −5pts, simulation match
−3pts, e2e accuracy −3pts), and those exact thresholds are what
`.github/workflows/eval.yml` enforces on every PR via
`scripts/check_regression.py`.

**The honesty property worth calling out:** every one of these scorers is
currently *vacuous* — see the "Vacuous score" glossary entry — because no
dataset loader or solver yet populates `state.metadata["actual_spec"]` /
`"actual_result"` / `"actual_e2e"` from a real pipeline run against
`data/eval/train/`. `packages/core/src/skiljo_core/eval/collect_metrics.py`
says this explicitly in its module docstring rather than papering over it,
and runs against Inspect's `mockllm/model` provider so CI needs no API key
and produces no fabricated quality numbers. This is exactly the CLAUDE.md
instruction "never fabricate quality numbers" applied to infrastructure
that isn't finished yet — the plumbing (collect → diff against baseline →
block on regression) is real and tested; the numbers it produces today are
placeholders by design, wired so that plugging in a real solver later
requires no change to the CI file or the regression script.

## How tests verify the evals

Two layers, matching the project's "pure function + thin framework wrapper"
pattern used throughout (see `simulation/executor.py` for the same shape):

1. **Pure scorer functions** (`extraction_recall`, `citation_resolution`,
   `simulation_match_rate`, etc.) take plain `dict[str, Any]` inputs and
   return a `Score` — no Inspect machinery required. `test_eval_extraction.py`
   / `test_eval_simulation.py` / `test_eval_e2e.py` exercise these directly
   with hand-built fixtures, including the vacuous-truth edge cases (empty
   expected set → score 1.0, not division by zero).
2. **Inspect `Task` wiring** (`ExtractionEval()`, `SimulationEval()`,
   `E2EEval()`) is checked structurally — `eval_task.name == "extract"`,
   `eval_task.scorer is not None` — confirming the task is importable and
   instantiable without live eval data (`dataset=None` supplies a dummy
   sample for exactly this reason).

`test_eval_regression.py` and `test_eval_collect_metrics.py` test the CI
plumbing itself: given a current-metrics JSON and a baseline-metrics JSON,
does `check_metric()` correctly flag a regression past threshold, respect
the `citation_resolution` hard floor, and handle a missing baseline (first
PR to introduce a metric) as "nothing to regress against" rather than a
failure?

## Why this way

**Why pure functions wrapped by `@scorer`, not scorers written directly
against Inspect's `TaskState`.** Testing a `TaskState`-shaped scorer means
constructing Inspect's internal objects in every test. Extracting the
comparison logic into a plain function taking two dicts makes the test
suite fast (no Inspect runtime) and the logic auditable independent of the
framework — the same "boundary" principle as `LLMClient` in week 2 (see
[Task 1](week2-task1-llm-client-protocol.md)): keep the third-party
framework at the edges, keep your own logic plain and directly testable.

**Why `dict[str, Any]` instead of a `TypedDict` for the scorer inputs.**
The brief for this task explicitly calls out "overly broad types (e.g.,
`dict` instead of specific TypedDict)" as something to fix. A `TypedDict`
was considered and rejected here: the shapes genuinely vary per scorer
(`{"results": [...]}` vs. `{"planted_divergence_ids": [...]}` vs.
`{"contracitions": [...]}`), tests deliberately pass partial/empty dicts
(`{}`) relying on `.get()` defaults, and the docstrings already specify the
expected shape precisely in prose. Forcing a shared `TypedDict` would mean
either one large `total=False` type with fields that don't apply to most
callers, or a proliferation of near-identical per-function types — type
noise without a corresponding safety gain. `dict[str, Any]` is the honest
middle point: it says "this is a JSON-shaped bag of data, read defensively"
without claiming a precision the code doesn't have.

**Why the cost estimate is a static table, not a live lookup.** The
Anthropic Models API returns capabilities, not price — there's no
`GET /v1/models/{id}/price` to call. A hand-maintained
`dict[str, tuple[float, float]]` keyed by model ID, returning `None` for
tokens missing (a cache hit made no API call) or a model with no known
rate, matches the project's existing "never fabricate, prefer an honest
gap" pattern rather than guessing a rate for an unrecognized model string.

## Where to look

- `packages/core/src/skiljo_core/eval/extraction.py`,
  `simulation.py`, `e2e.py` — the three eval suites; each has a
  "standalone scorer logic" section (pure, tested directly) and an
  "Inspect AI scorer factories" section (thin wrapper)
- `packages/core/src/skiljo_core/eval/collect_metrics.py` — bridges the
  three `Task`s to the flat metric-name JSON the CI gate consumes; read its
  module docstring for the vacuous-metrics honesty note
- `packages/core/src/skiljo_core/eval/regression.py` +
  `scripts/check_regression.py` — the regression-gating comparison logic
  and its CLI entry point
- `.github/workflows/eval.yml` — runs the eval-suite tests, collects
  metrics, diffs against `data/eval/baseline_metrics.json` at
  `origin/main`, uploads the results artifact
- `data/eval/README.md` — the train/dev/test split rationale and the
  per-document corpus-allocation discipline that keeps the same rule
  cluster from leaking across splits
- `packages/api/src/skiljo_api/routers/evals.py` — `POST`/`GET
  /eval-runs`, the persisted metric-history endpoints backed by the
  `EvalRun` model (already present in `db/models.py` since the initial
  schema migration, wired up for real in this week's Task 6)
- `packages/core/src/skiljo_core/simulation/cross_document.py` — the A3
  cross-document contradiction detector: LLM-assisted decision-surface
  alignment gated by a mechanical conflict check, so a hallucinated
  "conflict" from the alignment step can never surface on its own
- `packages/core/src/skiljo_core/llm/pricing.py` +
  `packages/core/src/skiljo_core/llm/logging.py` — this task's own
  contribution: cost estimation wired into every logged LLM call

## Concerns for the next planning pass

`DESIGN_DOCUMENT.md` Section 12 documents a scope addition **A6**
("contradiction clustering to spec" — adding reason-category and
time-window clustering dimensions, replacing the bare frequency threshold
with a binomial test) slotted "week 5, after commit 54, before A3". A6 is
**not** one of the 10 tasks in
`docs/superpowers/plans/2026-07-13-week5-eval-expansion.md`, and it was not
built this week — `simulation/contradictions.py` still clusters only on
`(amount_band, customer_segment)` with a bare frequency threshold, exactly
as it was at the end of week 3. This looks like a planning-doc note that
was written before the actual week-5 execution plan was finalized and never
reconciled. Flagging rather than silently building it (out of this week's
assigned scope) or silently leaving the design doc wrong.
