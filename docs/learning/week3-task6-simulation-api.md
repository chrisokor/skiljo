# Week 3 Task 6 — Simulation API Endpoints

## What was built

Two REST endpoints that expose the simulation engine (built in tasks 3–5) via HTTP:

- `POST /simulations` — accepts a `skill_version_id` and a list of ticket dicts; creates a `SimulationRun` row and a `Job` row; enqueues a background job; returns `202 {job_id, status: "pending"}`.
- `GET /simulations/{id}` — returns the run's current status and summary (or `null` if not yet complete).
- `GET /simulations/{id}/report` — returns the full `SimulationReport` JSON once the run is `completed`; returns `409` if it isn't.

**Files:**
- Created: `packages/api/src/skiljo_api/routers/simulations.py`
- Modified: `packages/api/src/skiljo_api/main.py` (added `simulations` router import and `include_router`)
- Created: `packages/api/tests/test_simulations.py`
- Modified: `packages/api/tests/test_skills_read.py`, `test_skills_extract.py` (added `SimulationResult`/`SimulationRun` cleanup to prevent FK violations across tests)

## The background job pattern (mirrored from extraction)

The simulation endpoint follows exactly the same async-job contract as the extraction endpoint ([week2-task8-extract-endpoint.md](week2-task8-extract-endpoint.md)):

1. The endpoint handler creates the DB rows (`SimulationRun` + `Job`), commits, captures their IDs.
2. It calls `background_tasks.add_task(_run_simulation_job, ...)`, passing the captured IDs and any other data needed by the background function.
3. It returns `202` immediately.

The background function `_run_simulation_job` runs after the response is sent. It re-opens a DB session, transitions the job to `running`, does the real work, then either transitions to `completed` or `failed`.

**Why capture IDs before `add_task`?** The SQLAlchemy session is closed before the background function runs. SQLAlchemy objects can't be used across session boundaries. Passing raw `uuid.UUID` values is safe; passing ORM instances is not.

## Why `asyncio.run()` inside the background task

`simulate_batch` is an `async` function that uses `asyncio.gather` internally for concurrency. FastAPI's `BackgroundTasks` are synchronous — they run in a thread, not in an event loop. To call an async function from that thread context, the background function must start its own event loop with `asyncio.run(simulate_batch(...))`.

This is distinct from FastAPI's async path handling. An `async def` endpoint runs in the existing event loop; a background task registered via `add_task` with a `def` function runs in a thread pool. Using `asyncio.run()` bridges the gap correctly.

See also [FastAPI BackgroundTasks](GLOSSARY.md#fastapi-backgroundtasks) in the glossary.

## How `sim_run_id` ties the job table to the simulation run

The `Job` row stores `result_ref: UUID`. In the extraction endpoint, `result_ref` points to the `SkillVersion` that was produced. In the simulation endpoint, `result_ref` points to the `SimulationRun` row.

The test uses this linkage directly:
```python
job = session.get(Job, job_id)
if job.status == "completed" and job.result_ref is not None:
    sim_id = job.result_ref
    report_resp = client.get(f"/simulations/{sim_id}/report")
```

The `summary` column on `SimulationRun` stores the full `SimulationReport` as JSONB. The report endpoint reads it back and returns it as-is — no re-computation at query time.

## Cross-test FK violation fix

After the simulation tests run, `SimulationRun` rows remain in the DB referencing `SkillVersion` rows. The existing `_clean_tables()` in `test_skills_read.py` and `test_skills_extract.py` tried to `DELETE FROM skill_versions` first, which Postgres rejected due to the FK constraint. The fix: delete `SimulationResult` then `SimulationRun` before deleting `SkillVersion`. This is a general pattern: when cleaning up between tests, always delete child tables before parent tables in FK order.

## Where to look

- Router: `packages/api/src/skiljo_api/routers/simulations.py`
- Endpoint mount: `packages/api/src/skiljo_api/main.py`
- Tests: `packages/api/tests/test_simulations.py`
- Background job function: `_run_simulation_job` in `simulations.py`
- The extraction endpoint it mirrors: `packages/api/src/skiljo_api/routers/skills.py`
