# Week 2, Task 10: GET /skills, /skills/{id}, /skills/{id}/versions endpoints

## What was built

Three read-only endpoints appended to the existing `routers/skills.py`:

- `GET /skills` — lists all skills (id, name, current_version_id)
- `GET /skills/{skill_id}` — returns one skill by ID, 404 if missing
- `GET /skills/{skill_id}/versions` — returns all versions for a skill, in insertion order

These complete the API's read surface: after a client polls `/jobs/{id}` and sees `status="completed"`, it can fetch the resulting `SkillVersion` by calling `/skills/{skill_id}/versions` and looking up the version ID from `result_ref`.

## Key concepts

**Route order and `{skill_id}` vs `/extract`.** FastAPI evaluates routes in registration order, but path parameters (`{skill_id}`) only match segments when no literal segment matches first. `GET /skills/extract` doesn't exist (it's a POST), so there's no collision — the `{skill_id}` parameter catches any segment in its position for GET requests. When registering routes, if you had both `GET /skills/extract` and `GET /skills/{skill_id}`, the literal `/extract` would need to be registered before the pattern. In this task, that ambiguity doesn't exist because the methods differ.

**`SkillSummary` and `SkillVersionSummary` as response models.** These are Pydantic `BaseModel` subclasses defined in the router file itself — they're API response shapes, not database models. FastAPI serializes the return value of each route handler against the declared return type, stripping any extra ORM attributes. Keeping them in the router file (rather than a shared `schemas.py`) is intentional: they're only ever used by these routes, so there's no benefit to a separate module.

**`session.query()` — legacy Query API.** The `list_skills` and `list_skill_versions` handlers use `session.query(Model).all()` and `session.query(Model).filter(Model.col == val).all()`. This is SQLAlchemy 1.x style. The SQLAlchemy 2.x equivalent uses `session.execute(select(Model))` with `scalars().all()`. Both work in SQLAlchemy 2.x (the 1.x API is still supported), but the 2.x style is preferred in new code. The plan specified the legacy form; a future cleanup would migrate these to 2.x style.

**Empty list vs 404 for missing parent.** `list_skill_versions` returns an empty list `[]` if the `skill_id` doesn't exist (no `SkillVersion` rows for it), rather than a 404. This is a common REST convention: a collection endpoint at `/skills/{id}/versions` returning empty means "this resource exists but has no versions" or "we don't distinguish between an absent parent and an empty collection." The plan does not specify a 404 here, so the empty-list behavior is intentional.

## Why this way

The three endpoints are read-only and stateless — each opens a session, queries, serializes, and returns. No `flush()`, no `commit()`, no background tasks. The session is closed by the context manager as soon as the query is done.

All three return typed Pydantic models, which FastAPI serializes to JSON automatically. Returning the ORM object directly would work at runtime but would serialize all columns (including internals like `__table__` references) and would break type-checking.

## Where to look

- [packages/api/src/skiljo_api/routers/skills.py](packages/api/src/skiljo_api/routers/skills.py) — the three new route handlers and `SkillSummary`/`SkillVersionSummary` models appended at the bottom.
- [packages/api/tests/test_skills_read.py](packages/api/tests/test_skills_read.py) — four tests covering list, get, 404, and versions, all seeded via a `_seed_skill_with_version()` helper.
