# Week 2, Task 9: GET /jobs/{id} polling endpoint

## What was built

`GET /jobs/{job_id}` — a read endpoint callers use to poll a job's status after posting to `/skills/extract`. Returns the job's `status`, `result_ref` (the `SkillVersion.id` when completed), and `error` (if failed). Returns 404 if the job doesn't exist.

This is deliberately minimal: no long-polling, no server-sent events, no WebSocket — just a simple status fetch the client can call repeatedly.

## Key concepts

**`HTTPException` for 404.**
FastAPI's idiomatic way to abort a request with an HTTP error code is `raise HTTPException(status_code=404, detail="...")`. The `detail` string becomes the `"detail"` field in the JSON error body. No need to construct a `Response` object or return early — FastAPI's exception handler catches it and turns it into the appropriate HTTP response.

**Path parameter typing — `job_id: uuid.UUID`.**
Declaring the path parameter as `uuid.UUID` rather than `str` tells FastAPI to validate and coerce the path segment before the function is called: if the client sends a non-UUID string, FastAPI returns a 422 (Unprocessable Entity) automatically, without any manual parsing in the handler. The validated `uuid.UUID` value is passed directly to `session.get(Job, job_id)`.

**`session.get(Model, pk)` — the 2.x primary-key lookup.**
`session.get(Job, job_id)` is SQLAlchemy 2.x's preferred way to fetch a row by primary key. It returns `T | None`, making the None check explicit (`if job is None: raise HTTPException(...)`). The legacy 1.x equivalent was `session.query(Job).filter_by(id=job_id).first()` — avoid this in new code; SQLAlchemy 2.x encourages the newer `select` statement API and `session.get` for PK lookups.

## Why this way

The 202-then-poll pattern (Task 8 returns 202 immediately, this endpoint is polled for completion) is a standard approach for long-running API operations that avoids HTTP timeout issues. A typical flow: client POSTs to `/skills/extract`, gets back `{job_id, status: "pending"}`, then polls `GET /jobs/{job_id}` every few seconds until `status` is `"completed"` or `"failed"`. The `result_ref` in the completed response tells the client which `SkillVersion` to fetch next via the `/skills` endpoints (Task 10).

## Where to look

- [packages/api/src/skiljo_api/routers/jobs.py](packages/api/src/skiljo_api/routers/jobs.py) — `JobResponse`, `get_job` handler.
- [packages/api/src/skiljo_api/main.py](packages/api/src/skiljo_api/main.py) — updated to include the jobs router.
- [packages/api/tests/test_jobs.py](packages/api/tests/test_jobs.py) — two tests: 200 with a seeded completed job, and 404 for an unknown UUID.
