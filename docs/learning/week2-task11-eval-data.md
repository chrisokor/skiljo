# Week 2, Task 11: 20 hand-labeled policy-to-skill examples

## What was built

Twenty ground-truth policy-to-skill pairs in `data/eval/train/`, covering 20 real company refund/billing policies from Skiljo's corpus. Each pair is a `.policy.txt` (the raw policy text or excerpt) and a `.skill.yaml` (the hand-written correct `Skill` spec). A validation test in `packages/core/tests/test_eval_data.py` asserts that all 20 YAML files are schema-valid against `Skill.model_validate()`.

These become the training/eval fixtures for the Week 5 extraction eval harness: a run of the extraction pipeline on each `.policy.txt` is compared against its `.skill.yaml` to produce recall and precision metrics.

## Key concepts

**Ground truth as the eval contract.**
The `.skill.yaml` files are not just example outputs — they define *correct behavior* for the extraction pipeline. When the eval harness (Week 5) runs `run_extraction_pipeline(llm_client, policy_text, ...)` on each `.policy.txt`, the output is scored against the corresponding `.skill.yaml`. This means the quality of the eval harness is fundamentally capped by the quality of these labels. A mislabeled rule (e.g., a deterministic threshold labeled `llm_assisted`) produces a false negative in the eval metric.

**Zone classification in the ground truth — the Vercel "anomalous use" test.**
Row 12 (Vercel ToS, `12_vercel_tos.skill.yaml`) is the corpus's deliberate zone-classification test case: Vercel's "anomalous use" override allows Vercel to suspend accounts at its "sole discretion" — a classic `llm_assisted` trigger (requires judgment to assess whether use is actually anomalous) rather than a `deterministic` one (which would require a specific, mechanically testable threshold). The ground truth correctly labels this `llm_assisted` with `requires_human_approval: true`. If the extraction pipeline's zone classification pass labels it `deterministic`, that's a true negative in the Week 5 eval.

**DSL coverage gaps documented in ground truth.**
The Predicate DSL supports field-vs-constant comparisons (`field op value`) but not field-vs-field comparisons (`field1 op field2`). Row 17 (Square payment terms) has a rule like "refund cannot exceed the original payment amount" — this is a field-to-field constraint (`refund_amount lte original_payment_amount`) that the current DSL cannot express. The `.skill.yaml` omits this rule (correctly) and the `.policy.txt` has a note explaining why. This is the first concrete example of a DSL coverage gap that may need to be addressed in a future schema extension.

**Synthesized vs. fetched policy text.**
Four of the 20 `.policy.txt` files are synthesized from POLICY_CORPUS.md research notes rather than verbatim-fetched from the live URL (OpenAI ×2 returned 403, Shopify Plus redirected to an authenticated endpoint, Google Cloud's page was truncated). The `.policy.txt` files include a header noting synthesis. Synthesized text is acceptable for the initial training set — it still covers the extraction challenges described in the corpus — but should be replaced with verbatim fetched text before any production eval run.

**`pyyaml` as an explicit dev dependency.**
PyYAML was already present transitively (via `datamodel-code-generator`) but is now declared explicitly in the root `pyproject.toml` dev group. The principle: any package your test code imports directly should be declared as a direct dependency, even if it's already reachable transitively. Transitive dependencies can change (a codegen tool might switch YAML parsers), so direct usage warrants direct declaration.

## Why this way

The "train" directory lives at `data/eval/train/` (not `packages/core/tests/fixtures/` or similar) because eval data isn't test infrastructure — it's product data that belongs alongside the code but is managed separately from the test suite. The Week 5 eval harness loads it at runtime, and the paths.py in the eval runner will reference `data/eval/train/` and `data/eval/test/` as siblings.

The validation test (`test_eval_data.py`) is a schema gate, not a content check. It confirms that every `.skill.yaml` can be parsed by `Skill.model_validate()` — catching obvious structural errors (missing required fields, wrong types, invalid `skill_name` patterns). It does not check that the labeled rules are *correct*, which would require human review or a separate annotation pipeline.

## Where to look

- [data/eval/train/](data/eval/train/) — the 20 `.policy.txt` / `.skill.yaml` pairs.
- [data/eval/train/01_notion.skill.yaml](data/eval/train/01_notion.skill.yaml) — the worked example from the brief, with nested `any`/`all` conditions demonstrating the full YAML format.
- [data/eval/train/12_vercel_tos.skill.yaml](data/eval/train/12_vercel_tos.skill.yaml) — the `llm_assisted` zone classification test case.
- [packages/core/tests/test_eval_data.py](packages/core/tests/test_eval_data.py) — validation test (20 files, all schema-valid, all have non-empty policy text).
