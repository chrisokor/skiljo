# Design: Week 2 — Extraction pipeline

## Context

Week 1 (foundations) is complete: monorepo, JSON Schemas + codegen, Postgres + Alembic, FastAPI skeleton, CI, README. See `docs/superpowers/specs/2026-06-20-week1-foundations-design.md` and `docs/superpowers/plans/2026-06-21-week1-foundations.md` for that work and the corrections discovered during its execution.

This spec scopes the **second** sub-project — "Week 2 — Extraction pipeline" — per `docs/DESIGN_DOCUMENT.md` §11 and §12 (commits 14–25). It does not redesign the extraction architecture; that's already specified in §5.2 (LLM client) and §5.3 (extraction pipeline). This doc scopes the work, records operational decisions the design doc doesn't cover, and fixes a testing strategy given a constraint the design doc didn't anticipate: no Anthropic API key is available for this work.

Source of truth for technical detail: `docs/DESIGN_DOCUMENT.md` §5.2–5.3 and §12 "Week 2" commit breakdown. Read those directly; this doc summarizes scope and decisions.

## Scope

Implement commits 14–25 from `docs/DESIGN_DOCUMENT.md` §12, each as its own atomic, conventional-commit-formatted git commit:

1. `feat(core): LLM client protocol and Anthropic implementation`
2. `feat(core): structured output via tool-use with validation retry`
3. `feat(core): LLM call logging to Postgres`
4. `feat(core): extraction pass 1 — policy segmentation`
5. `feat(core): extraction pass 2 — rule extraction per segment`
6. `feat(core): extraction pass 3 — decision zone classification`
7. `feat(core): extraction pass 4 — assembly and schema validation`
8. `feat(api): POST /skills/extract endpoint with background job`
9. `feat(api): GET /jobs/{id} polling endpoint`
10. `feat(api): GET /skills, /skills/{id}, /skills/{id}/versions endpoints`
11. `data: 20 hand-labeled policy-to-skill examples`
12. `test(core): unit tests for extraction pipeline`

**Out of scope:** the simulation engine (Week 3) and running the Inspect eval harness against the new labeled data — deferred because it needs more eval infrastructure to be worth wiring up now, and nothing else this week depends on it. Revisit in Week 5 ("eval expansion") or sooner if useful.

## Operational decisions (not covered by the design doc)

- **No Anthropic API key for this work.** Everything must be buildable and testable without live network calls to Anthropic. This shapes the testing strategy below.
- **Testing strategy — two mock layers:**
  - `AnthropicClient` (commits 1–3 above) is tested by patching the `anthropic` SDK's `messages.create` with fake tool-use response payloads, including a deliberately-invalid-then-valid pair to exercise the retry loop. This proves the wrapper's tool-use parsing, Pydantic validation, retry logic, and `llm_calls` logging without any real network access — standard practice independent of key availability.
  - Everything built on `LLMClient` (the extraction passes, commits 4–7) is tested against a `FakeLLMClient` (`packages/core/tests/fakes.py`) returning canned `StructuredResponse` objects, per the design doc's own instruction for its commit 25 / this spec's commit 12 ("mocking the LLM client").
  - When a real key becomes available later, nothing in the code needs to change — only a manual smoke-test against the live API becomes possible. Add that as a follow-up task in a future session, not part of this spec.
- **Default model:** `claude-sonnet-4-6` for all extraction calls (best quality/cost balance for the reasoning-heavy segmentation and zone-classification passes). Passed as the `model` parameter to `generate_structured`, overridable per call.
- **Prompts:** inline string constants per pass module (`extraction/segmentation.py`, `extraction/rules.py`, etc.), not a separate prompt-template directory. Four prompts is too small to justify file-based prompt management; revisit if Week 5's eval expansion needs prompt versioning infrastructure.
- **API router structure:** introduce `packages/api/src/skiljo_api/routers/skills.py` and `routers/jobs.py`, mounted from `main.py`. The `/health` route stays inline in `main.py`. This is a structural step up from Week 1's single-file API now that there are 5 real endpoints.
- **Eval data sourcing (commit 11 / design doc commit 24):** `docs/POLICY_CORPUS.md` was expanded to 20 real-world policies specifically for this. Follow its "How to use this corpus" section: the 8 cleanest single-rule examples first (Notion #11, AWS S3 SLA #4, AWS Audit Manager SLA #5, Stripe Docs #2, OpenAI Service Credit Terms #6, Twilio #8, Shopify Plus #13, one excerpt from Vercel Pro #10), then 8 harder examples (Stripe legal #1, Amazon EC2 #3, OpenAI enterprise #7, Vercel Terms #9, Vercel Pro full #10, Notion re-labeled #11, Shopify subscription #12, one excerpt from Steam #14), reserving 4 of the harder set for a dev split. Steam (#14) and Shopify subscription (#12) are reserved for the eventual held-out test set (`data/eval/test/`) — don't use them up in `data/eval/train/` beyond the bundled excerpts called for above.
- **Package layout for new code:**
  ```
  packages/core/src/skiljo_core/
    llm/
      base.py              # LLMClient Protocol, StructuredResponse[T]
      anthropic_client.py  # AnthropicClient (tool-use, retry, logging)
      logging.py           # LLMCallLogger -> llm_calls table
    extraction/
      segmentation.py       # pass 1
      rules.py              # pass 2
      zones.py              # pass 3
      assembly.py           # pass 4 (+ repair loop)
      pipeline.py            # orchestrates passes 1-4

  packages/api/src/skiljo_api/
    routers/
      skills.py    # POST /skills/extract, GET /skills, /skills/{id}, /skills/{id}/versions
      jobs.py      # GET /jobs/{id}

  data/eval/train/
    <NN>_<slug>.policy.txt
    <NN>_<slug>.skill.yaml
  ```

## Verification

- Each commit's acceptance criterion (from the design doc, adjusted for mocking where a live call was originally implied) must pass before moving to the next commit.
- Commit 11 (eval data): all 20 examples' `.skill.yaml` ground truth validates against `schemas/skill.schema.json`.
- Commit 12: `make test` passes, covering all 4 extraction passes against `FakeLLMClient`.
- End of week: `make test`, `make lint`, `make typecheck` all green; CI green on `main`; a manual end-to-end check (`curl POST /skills/extract` against a `FakeLLMClient`-backed test instance, or an integration test doing the same) produces a `skill_versions` row with `status='draft'`.