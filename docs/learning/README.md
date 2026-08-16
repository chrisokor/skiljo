# Learning Debriefs

An index of written explanations for each implementation task — what was built, the non-obvious concepts involved, why that approach was chosen, and where to look in the code. See `docs/superpowers/specs/2026-06-21-learning-debrief-process-design.md` for the process this follows.

See `GLOSSARY.md` for a running list of concepts introduced across debriefs.

## Week 8 - Project readiness hardening

1. [Task 1: Complete diagnostic workflow](week8-task1-diagnostic-workflow.md)
2. [Task 2: Extraction eval solver](week8-task2-extraction-eval-solver.md)
3. [Task 3: Sample diagnostic report artifact](week8-task3-sample-report-artifact.md)

## Week 7 - Citations and v1.05 product

4. [Task 4: Eval ground-truth citations](week7-task4-eval-citations.md)
5. [Task 5: HTML report rendering](week7-task5-html-report-rendering.md)
6. [Task 6: Cross-document contradiction UI](week7-task6-cross-document-ui.md)
7. [Task 7: Consistency checker workflow](week7-task7-consistency-checker-workflow.md)
8. [Task 8: Integration testing and final polish](week7-task8-integration-testing-final-polish.md)
9. [Task 9: Final review fix wave](week7-task9-final-fix-wave.md)

## Week 6 — v1.0 completion

7. [Task 7: v1.0 completion — dataset loader, CI baseline refresh, SDK parity, A6 contradiction clustering, shipping](week6-task7-v1.0-completion.md)

## Week 5 — Eval harness expansion and cross-document contradictions

10. [Task 10: Eval harness integration and final cleanup](week5-task10-eval-harness-integration.md)

## Week 4 — Demo UI, SDK, integration, and documentation

12. [Task 12: ARCHITECTURE.md with full system deep dive](week4-task12-architecture-documentation.md)

## Week 3 — Simulation engine

1. [Task 1: LLM response cache (scope addition A1)](week3-task1-llm-cache.md)
2. [Task 2: Simulation engine — asyncio batch execution, zone routing, report aggregation](week3-task2-simulation-engine.md)
3. [Task 3: Rule evaluator for deterministic zone](week3-task3-rule-evaluator.md)
4. [Task 4: Shadow-policy ticket generator](week3-task4-shadow-policy-generator.md)
5. [Task 5: Contradiction detection](week3-task5-contradiction-detection.md)
6. [Task 6: Simulation API endpoints POST /simulations, GET /simulations/{id}/report](week3-task6-simulation-api.md)
7. [Task 7: Synthetic ticket generation with planted divergences](week3-task7-synthetic-tickets.md)
8. [Task 8: Golden fixture tests for end-to-end simulation](week3-task8-golden-tests.md)

## Week 2 — Extraction pipeline

1. [Task 1: LLM client protocol and Anthropic implementation](week2-task1-llm-client-protocol.md)
2. [Task 2: Structured output via tool-use with validation retry](week2-task2-structured-output-retry.md)
3. [Task 3: LLM call logging to Postgres](week2-task3-llm-call-logging.md)
4. [Task 4: Extraction pass 1 — policy segmentation](week2-task4-policy-segmentation.md)
5. [Task 5: Extraction pass 2 — rule extraction per segment](week2-task5-rule-extraction.md)
6. [Task 6: Extraction pass 3 — decision zone classification](week2-task6-zone-classification.md)
7. [Task 7: Extraction pass 4 — assembly, schema validation, and pipeline orchestration](week2-task7-assembly-pipeline.md)
8. [Task 8: POST /skills/extract endpoint with background job](week2-task8-extract-endpoint.md)
9. [Task 9: GET /jobs/{id} polling endpoint](week2-task9-jobs-endpoint.md)
10. [Task 10: GET /skills, /skills/{id}, /skills/{id}/versions endpoints](week2-task10-skills-read-endpoints.md)
11. [Task 11: 20 hand-labeled policy-to-skill examples](week2-task11-eval-data.md)
12. [Task 12: Unit tests for extraction pipeline — close coverage gaps](week2-task12-coverage.md)
