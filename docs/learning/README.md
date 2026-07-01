# Learning Debriefs

An index of written explanations for each implementation task — what was built, the non-obvious concepts involved, why that approach was chosen, and where to look in the code. See `docs/superpowers/specs/2026-06-21-learning-debrief-process-design.md` for the process this follows.

See `GLOSSARY.md` for a running list of concepts introduced across debriefs.

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
