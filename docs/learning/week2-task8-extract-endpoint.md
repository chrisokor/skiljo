# Week 2, Task 8: POST /skills/extract endpoint with background job

## What was built

The first API endpoint that calls the extraction pipeline. `POST /skills/extract` accepts a policy text and skill metadata, immediately returns a 202 with a job ID, then runs the four-pass extraction pipeline inside a FastAPI `BackgroundTask` — writing a `Policy` row, a `Skill` row, a `SkillVersion` row (status `"draft"`), and updating the `Job` row to `"completed"` when done.

Also added: `dependencies.py` — a module-level singleton factory for the real `AnthropicClient`, overridable in tests via FastAPI's `dependency_overrides` mechanism.

## Key concepts

**FastAPI `BackgroundTasks` — fire and return.**
`BackgroundTasks` is FastAPI's built-in mechanism for work that should happen after the HTTP response has been sent. The endpoint registers a function via `background_tasks.add_task(...)` and returns the response immediately — the background function runs afterward. This is how the endpoint returns 202 ("accepted, processing") without blocking the caller for the full pipeline duration.

One subtlety for testing: Starlette's `TestClient` (which wraps `httpx` synchronously) runs background tasks *before* returning the simulated response, so tests can assert on DB state immediately after `client.post(...)` without polling. In production (with a real ASGI server like `uvicorn`), the task runs after the response is sent.

**`app.dependency_overrides` — replacing dependencies in tests.**
FastAPI's `Depends(get_llm_client)` is an injection point: FastAPI calls the dependency function to get the value to inject. `app.dependency_overrides[get_llm_client] = lambda: fake_client` replaces the real singleton factory with a lambda that returns the test fake for the duration of the test. This is the idiomatic FastAPI testing pattern — no monkeypatching, no mocks, just a dict entry that FastAPI checks at request time. The `try/finally` in the test ensures `app.dependency_overrides.clear()` runs even if the test fails, so the override doesn't leak into other tests.

**Session-per-unit-of-work — two sessions, not one.**
The endpoint uses `with SessionLocal() as session:` twice: once in the request handler (to create `Policy` and `Job` rows and commit before returning) and once in `_run_extraction_job` (to update the job, create `Skill` and `SkillVersion`, and commit when done). Using two separate sessions matters here: the background function is called after the request handler's session has already committed and closed. If the same session were shared, the background function might operate on a stale transaction context. Each `with SessionLocal() as session:` block is an independent unit of work.

**`session.flush()` before `session.commit()`.**
`session.flush()` sends pending SQL to the database (triggering auto-generated IDs like `id` on new rows) without committing the transaction. The code calls `flush()` after adding `Skill` and `SkillVersion` rows so it can read `skill_row.id` / `version_row.id` to wire them together (`SkillVersion.skill_id = skill_row.id`, `Job.result_ref = version_row.id`), then calls `commit()` once at the end to make everything permanent. Without the `flush()`, the IDs wouldn't be populated yet and the wiring would fail.

**`model_dump(mode="json")` for the spec column.**
The `SkillVersion.spec` column is a Postgres JSONB column (mapped to `dict` in SQLAlchemy). `skill_spec.model_dump(mode="json")` converts the `Skill` Pydantic model to a plain Python dict with all values JSON-serializable (enums as strings, UUIDs as strings, etc.). This is the same pattern used in Task 7's assembly step — see [Task 7](week2-task7-assembly-pipeline.md) for context.

## Why this way

The endpoint intentionally separates "create the job record" (synchronous, before returning 202) from "run the pipeline" (background task). This ensures the job ID returned in the 202 response is always findable in the database immediately — the caller can start polling `GET /jobs/{id}` without a race condition. If the job creation were also in the background, the caller might poll before the row existed.

The `dependencies.py` singleton (`_client: LLMClient | None = None`) avoids creating a new Anthropic SDK client on every request (each client creates a connection pool). The module-level singleton pattern is simple and sufficient for the single-process MVP; a production service might use a proper DI container or request-scoped session management.

## Where to look

- [packages/api/src/skiljo_api/dependencies.py](packages/api/src/skiljo_api/dependencies.py) — `get_llm_client()` singleton.
- [packages/api/src/skiljo_api/routers/skills.py](packages/api/src/skiljo_api/routers/skills.py) — `ExtractRequest`, `ExtractResponse`, `_run_extraction_job`, `extract_skill` endpoint.
- [packages/api/src/skiljo_api/main.py](packages/api/src/skiljo_api/main.py) — updated to mount the skills router.
- [packages/api/tests/test_skills_extract.py](packages/api/tests/test_skills_extract.py) — the test, showing `dependency_overrides` pattern and immediate DB assertion after the POST.
