# Week 1 Foundations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bootstrap the Skiljo monorepo (commits 1–13 of `docs/DESIGN_DOCUMENT.md` §12) so a working Postgres-backed FastAPI skeleton, JSON-Schema-driven Pydantic/Zod codegen, and a green GitHub Actions CI pipeline all exist before any extraction/simulation logic is written.

**Architecture:** A `uv` workspace (`packages/core`, `packages/api`, `packages/demo`) plus a `pnpm` workspace (`packages/sdk-ts`), with four canonical JSON Schemas in `schemas/` as the single source of truth, codegen'd into Pydantic (Python) and Zod (TypeScript) types. Postgres 16 runs via Docker Compose; SQLAlchemy 2.x models + Alembic manage the 8-table schema from `docs/DESIGN_DOCUMENT.md` §4. FastAPI exposes a `/health` endpoint as the only route this week.

**Tech Stack:** Python 3.12 (`uv`), FastAPI, SQLAlchemy 2.x + Alembic + psycopg3, Pydantic v2, `datamodel-code-generator`; TypeScript 5.x (`pnpm`), Zod, `tsup`, `vitest`, `json-schema-to-zod` + `@apidevtools/json-schema-ref-parser`; Postgres 16 via Docker Compose; GitHub Actions CI; GitHub CLI (`gh`) for repo creation.

**Spec:** `docs/superpowers/specs/2026-06-20-week1-foundations-design.md` (scopes this work; technical detail lives in `docs/DESIGN_DOCUMENT.md` §11–12).

---

## Prerequisites (already done this session)

- `uv` and `gh` installed via Homebrew; confirm with `uv --version` and `gh --version`.
- `gh auth status` shows logged in as `chrisokor`.
- **Docker Desktop must be running** before Task 1's last step and before Task 11 — start it now if it isn't (`open -a Docker` and wait for `docker info` to succeed). Commits 4 and 11 cannot be verified without it.
- All commands below assume the working directory is `/Users/chrisokor/workspace/Skiljo`.

Every task below ends with a commit; push after each commit (`git push`) once the remote exists (created at the end of Task 1), so GitHub Actions (added in Task 12) can actually run.

---

### Task 1: Initialize repo, workspaces, and GitHub remote

**Files:**
- Create: `.gitignore`
- Create: `LICENSE`
- Create: `README.md` (placeholder — full version in Task 13)
- Create: `pyproject.toml`
- Create: `package.json`
- Create: `pnpm-workspace.yaml`

- [ ] **Step 1: Initialize git**

```bash
git init -b main
```

- [ ] **Step 2: Write `.gitignore`**

```
# Python
__pycache__/
*.py[cod]
*.egg-info/
.venv/
.pytest_cache/
.mypy_cache/
.ruff_cache/

# Node
node_modules/
dist/
*.tsbuildinfo

# Env
.env

# OS
.DS_Store
```

- [ ] **Step 3: Write `LICENSE`** (MIT)

```
MIT License

Copyright (c) 2026 Christus Okorochukwu

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

- [ ] **Step 4: Write placeholder `README.md`**

```markdown
# Skiljo

Governed workflow skills for AI agents, starting with finance-sensitive refunds and credits. See `docs/DESIGN_DOCUMENT.md` for the full design and build plan.

Setup and architecture docs land here in Week 1, commit 13.
```

- [ ] **Step 5: Write root `pyproject.toml` (uv workspace root)**

```toml
[project]
name = "skiljo-workspace"
version = "0.1.0"
requires-python = ">=3.12,<3.13"
dependencies = []

[tool.uv.workspace]
members = ["packages/*"]
exclude = ["packages/sdk-ts"]

[dependency-groups]
dev = [
    "ruff>=0.6",
    "mypy>=1.11",
    "pytest>=8.3",
    "httpx>=0.27",
    "datamodel-code-generator>=0.26",
]

[tool.ruff]
target-version = "py312"
extend-exclude = ["packages/core/src/skiljo_core/schemas"]

[tool.pytest.ini_options]
testpaths = ["packages"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
bypass-selection = true
```

> Note: the root project itself ships no code (it's a workspace root + shared dev tooling), so `[tool.hatch.build.targets.wheel] bypass-selection = true` lets hatchling build an empty wheel for it without complaining about missing packages.

- [ ] **Step 6: Write root `package.json` (pnpm workspace root)**

```json
{
  "name": "skiljo-workspace",
  "private": true,
  "version": "0.1.0",
  "devDependencies": {
    "tsx": "^4.19.0",
    "ajv": "^8.17.0",
    "ajv-cli": "^5.0.0",
    "ajv-formats": "^3.0.1",
    "json-schema-to-zod": "^2.4.0",
    "@apidevtools/json-schema-ref-parser": "^11.7.0"
  }
}
```

- [ ] **Step 7: Write `pnpm-workspace.yaml`**

```yaml
packages:
  - "packages/sdk-ts"
```

- [ ] **Step 8: Verify both package managers resolve cleanly**

```bash
uv sync
pnpm install
```

Expected: both succeed with exit code 0 (uv will download Python 3.12 automatically since `requires-python` pins `<3.13` and the system default is 3.13 — this is expected and fine). `uv.lock` and `pnpm-lock.yaml` are created.

- [ ] **Step 9: Commit**

```bash
git add .gitignore LICENSE README.md pyproject.toml package.json pnpm-workspace.yaml uv.lock pnpm-lock.yaml
git commit -m "chore: initialize repo with uv workspaces and pnpm workspace"
```

- [ ] **Step 10: Create the GitHub repo and push**

```bash
gh repo create chrisokor/skiljo --private --source=. --remote=origin --push
```

Expected: repo created at `https://github.com/chrisokor/skiljo`, `origin` remote added, `main` pushed.

---

### Task 2: Python package skeletons (core, api, demo)

**Files:**
- Create: `packages/core/pyproject.toml`, `packages/core/README.md`, `packages/core/src/skiljo_core/__init__.py`
- Create: `packages/api/pyproject.toml`, `packages/api/README.md`, `packages/api/src/skiljo_api/__init__.py`
- Create: `packages/demo/pyproject.toml`, `packages/demo/README.md`, `packages/demo/src/skiljo_demo/__init__.py`

- [ ] **Step 1: Create `packages/core/pyproject.toml`**

```toml
[project]
name = "skiljo-core"
version = "0.1.0"
description = "Core extraction, simulation, and storage logic for Skiljo"
requires-python = ">=3.12,<3.13"
dependencies = [
    "pydantic>=2.9",
    "sqlalchemy>=2.0",
    "alembic>=1.13",
    "psycopg[binary]>=3.2",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/skiljo_core"]
```

- [ ] **Step 2: Create `packages/core/README.md`**

```markdown
# skiljo-core

Core extraction, simulation, and storage logic shared by the API and demo.
```

- [ ] **Step 3: Create `packages/core/src/skiljo_core/__init__.py`** (empty file)

- [ ] **Step 4: Create `packages/api/pyproject.toml`**

```toml
[project]
name = "skiljo-api"
version = "0.1.0"
description = "FastAPI backend for Skiljo"
requires-python = ">=3.12,<3.13"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "skiljo-core",
]

[tool.uv.sources]
skiljo-core = { workspace = true }

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/skiljo_api"]
```

- [ ] **Step 5: Create `packages/api/README.md`**

```markdown
# skiljo-api

FastAPI backend exposing the Skiljo REST API.
```

- [ ] **Step 6: Create `packages/api/src/skiljo_api/__init__.py`** (empty file)

- [ ] **Step 7: Create `packages/demo/pyproject.toml`**

```toml
[project]
name = "skiljo-demo"
version = "0.1.0"
description = "Streamlit demo UI for Skiljo"
requires-python = ">=3.12,<3.13"
dependencies = [
    "streamlit>=1.38",
    "skiljo-core",
]

[tool.uv.sources]
skiljo-core = { workspace = true }

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/skiljo_demo"]
```

- [ ] **Step 8: Create `packages/demo/README.md`**

```markdown
# skiljo-demo

Streamlit demo UI: upload a policy, review the extracted skill, run a simulation. (Content lands in Week 4.)
```

- [ ] **Step 9: Create `packages/demo/src/skiljo_demo/__init__.py`** (empty file)

- [ ] **Step 10: Verify each package resolves via uv**

```bash
uv sync
uv run python -c "import skiljo_core, skiljo_api, skiljo_demo; print('all importable')"
```

Expected: `all importable` printed, no errors.

- [ ] **Step 11: Commit and push**

```bash
git add packages/core packages/api packages/demo uv.lock
git commit -m "chore: add Python package skeletons (core, api, demo)"
git push
```

---

### Task 3: TypeScript SDK skeleton

**Files:**
- Create: `packages/sdk-ts/package.json`
- Create: `packages/sdk-ts/tsconfig.json`
- Create: `packages/sdk-ts/vitest.config.ts`
- Create: `packages/sdk-ts/src/index.ts`
- Test: `packages/sdk-ts/src/index.test.ts`

- [ ] **Step 1: Create `packages/sdk-ts/package.json`**

```json
{
  "name": "@skiljo/sdk",
  "version": "0.1.0",
  "type": "module",
  "main": "dist/index.cjs",
  "module": "dist/index.js",
  "types": "dist/index.d.ts",
  "scripts": {
    "build": "tsup src/index.ts --format esm,cjs --dts",
    "test": "vitest run"
  },
  "dependencies": {
    "zod": "^3.23.0"
  },
  "devDependencies": {
    "typescript": "^5.6.0",
    "tsup": "^8.3.0",
    "vitest": "^2.1.0"
  }
}
```

- [ ] **Step 2: Create `packages/sdk-ts/tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "strict": true,
    "declaration": true,
    "outDir": "dist",
    "esModuleInterop": true,
    "skipLibCheck": true
  },
  "include": ["src"]
}
```

- [ ] **Step 3: Create `packages/sdk-ts/vitest.config.ts`**

```typescript
import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "node",
  },
});
```

- [ ] **Step 4: Write the failing test — `packages/sdk-ts/src/index.test.ts`**

```typescript
import { describe, expect, it } from "vitest";
import { SDK_VERSION } from "./index";

describe("SDK_VERSION", () => {
  it("is defined", () => {
    expect(SDK_VERSION).toBe("0.1.0");
  });
});
```

- [ ] **Step 5: Install deps and run the test to verify it fails**

```bash
pnpm install
pnpm --filter @skiljo/sdk test
```

Expected: FAIL — `index.ts` doesn't exist yet, so `SDK_VERSION` can't be imported.

- [ ] **Step 6: Write minimal implementation — `packages/sdk-ts/src/index.ts`**

```typescript
export const SDK_VERSION = "0.1.0";
```

- [ ] **Step 7: Run test to verify it passes**

```bash
pnpm --filter @skiljo/sdk test
```

Expected: PASS (1 test).

- [ ] **Step 8: Verify the build produces a dist/ directory**

```bash
pnpm --filter @skiljo/sdk build
ls packages/sdk-ts/dist
```

Expected: `index.js`, `index.cjs`, `index.d.ts` present.

- [ ] **Step 9: Commit and push**

```bash
git add packages/sdk-ts pnpm-lock.yaml
git commit -m "chore: add TypeScript SDK skeleton"
git push
```

---

### Task 4: Docker Compose with Postgres 16

**Files:**
- Create: `docker-compose.yml`
- Create: `.env.example`

- [ ] **Step 1: Create `docker-compose.yml`**

```yaml
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_USER: skiljo
      POSTGRES_PASSWORD: skiljo
      POSTGRES_DB: skiljo
    ports:
      - "5433:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U skiljo"]
      interval: 5s
      timeout: 5s
      retries: 5

volumes:
  postgres_data:
```

> Correction from actual Week 1 execution: mapped to host port 5433, not 5432 — this machine has a pre-existing native Postgres install already listening on 5432, which silently intercepted connections meant for the container (`role "skiljo" does not exist`, since that's a different, unrelated Postgres instance). If your machine doesn't have anything else on 5432, you could use that instead, but 5433 avoids the conflict either way. `DATABASE_URL` in `.env.example`/`.env` must match.

- [ ] **Step 2: Create `.env.example`**

```
DATABASE_URL=postgresql+psycopg://skiljo:skiljo@localhost:5433/skiljo
ANTHROPIC_API_KEY=
SKILJO_API_KEY=dev-local-key
```

- [ ] **Step 3: Copy to a real `.env` for local dev** (not committed — already gitignored)

```bash
cp .env.example .env
```

- [ ] **Step 4: Verify Postgres starts and becomes healthy**

```bash
docker compose up -d postgres
docker compose ps postgres
```

Expected: status becomes `healthy` within a few seconds. If Docker Desktop isn't running, start it first (`open -a Docker`) and wait for `docker info` to succeed before retrying.

- [ ] **Step 5: Commit and push**

```bash
git add docker-compose.yml .env.example
git commit -m "chore: docker-compose with Postgres 16"
git push
```

---

### Task 5: Makefile with common dev tasks

**Files:**
- Create: `Makefile`

- [ ] **Step 1: Create `Makefile`**

```makefile
.PHONY: help setup codegen test lint typecheck api demo migrate clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "%-12s %s\n", $$1, $$2}'

setup: ## Install all dependencies and apply migrations
	uv sync --all-packages
	pnpm install
	$(MAKE) migrate

codegen: ## Regenerate Pydantic and Zod types from the canonical JSON Schemas
	uv run python schemas/codegen/generate_pydantic.py
	pnpm exec tsx schemas/codegen/generate_zod.ts

test: ## Run Python and TypeScript test suites
	uv run pytest
	pnpm -r test

lint: ## Lint Python sources
	uv run ruff check .

typecheck: ## Typecheck Python and TypeScript sources
	uv run mypy packages/core/src packages/api/src packages/demo/src --exclude 'schemas/'
	pnpm --filter @skiljo/sdk exec tsc --noEmit

api: ## Run the FastAPI dev server
	uv run uvicorn skiljo_api.main:app --reload --port 8000

demo: ## Run the Streamlit demo (functional from Week 4 onward)
	uv run streamlit run packages/demo/src/skiljo_demo/app.py

migrate: ## Apply database migrations
	uv run alembic -c packages/core/alembic.ini upgrade head

clean: ## Remove caches and build artifacts
	find . -type d -name '__pycache__' -exec rm -rf {} +
	rm -rf .pytest_cache .mypy_cache .ruff_cache
	rm -rf packages/sdk-ts/dist
```

- [ ] **Step 2: Verify `make help` lists all targets**

```bash
make help
```

Expected: all 9 targets (`help`, `setup`, `codegen`, `test`, `lint`, `typecheck`, `api`, `demo`, `migrate`, `clean`) listed with descriptions.

- [ ] **Step 3: Commit and push**

```bash
git add Makefile
git commit -m "chore: Makefile with common dev tasks"
git push
```

---

### Task 6: JSON Schemas — skill and rule

**Files:**
- Create: `schemas/skill.schema.json`
- Create: `schemas/rule.schema.json`

- [ ] **Step 1: Create `schemas/rule.schema.json`**

This encodes the constrained predicate language from `docs/DESIGN_DOCUMENT.md` §4 ("The Rule predicate language"): `all`/`any` composition over predicates with a fixed operator set.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://skiljo.ai/schemas/rule.schema.json",
  "title": "Rule",
  "$defs": {
    "Operator": {
      "type": "string",
      "enum": ["eq", "neq", "lt", "lte", "gt", "gte", "in", "not_in", "contains", "empty", "not_empty"]
    },
    "Predicate": {
      "type": "object",
      "required": ["field", "op"],
      "properties": {
        "field": { "type": "string" },
        "op": { "$ref": "#/$defs/Operator" },
        "value": {}
      }
    },
    "ConditionOrPredicate": {
      "anyOf": [
        { "$ref": "#/$defs/Predicate" },
        { "$ref": "#/$defs/Condition" }
      ]
    },
    "Condition": {
      "type": "object",
      "minProperties": 1,
      "maxProperties": 1,
      "properties": {
        "all": { "type": "array", "items": { "$ref": "#/$defs/ConditionOrPredicate" } },
        "any": { "type": "array", "items": { "$ref": "#/$defs/ConditionOrPredicate" } }
      }
    },
    "DeterministicRule": {
      "type": "object",
      "required": ["condition", "action"],
      "properties": {
        "condition": { "$ref": "#/$defs/Condition" },
        "action": { "type": "string" }
      }
    },
    "LLMAssistedRule": {
      "type": "object",
      "required": ["condition", "action", "requires_human_approval"],
      "properties": {
        "condition": { "$ref": "#/$defs/Condition" },
        "action": { "type": "string" },
        "requires_human_approval": { "type": "boolean", "const": true }
      }
    },
    "HumanOnlyRule": {
      "type": "object",
      "required": ["condition", "action"],
      "properties": {
        "condition": { "$ref": "#/$defs/Condition" },
        "action": { "type": "string" }
      }
    }
  }
}
```

- [ ] **Step 2: Create `schemas/skill.schema.json`** (verbatim from `docs/DESIGN_DOCUMENT.md` Appendix A)

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://skiljo.ai/schemas/skill.schema.json",
  "title": "Skill",
  "type": "object",
  "required": ["skill_name", "version", "trigger", "inputs", "decision_zones"],
  "properties": {
    "skill_name": { "type": "string", "pattern": "^[a-z_][a-z0-9_]*$" },
    "owner": { "type": "string" },
    "co_owners": { "type": "array", "items": { "type": "string" } },
    "version": { "type": "integer", "minimum": 1 },
    "trigger": { "type": "string" },
    "inputs": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["name", "type"],
        "properties": {
          "name": { "type": "string" },
          "type": { "enum": ["string", "number", "integer", "boolean", "array"] },
          "description": { "type": "string" }
        }
      }
    },
    "decision_zones": {
      "type": "object",
      "required": ["deterministic", "llm_assisted", "human_only"],
      "properties": {
        "deterministic": { "type": "array", "items": { "$ref": "rule.schema.json#/$defs/DeterministicRule" } },
        "llm_assisted": { "type": "array", "items": { "$ref": "rule.schema.json#/$defs/LLMAssistedRule" } },
        "human_only": { "type": "array", "items": { "$ref": "rule.schema.json#/$defs/HumanOnlyRule" } }
      }
    },
    "audit_requirements": { "type": "array", "items": { "type": "string" } }
  }
}
```

- [ ] **Step 3: Verify both schemas validate against the meta-schema and resolve cross-file `$ref`s**

```bash
pnpm install
pnpm exec ajv compile -s schemas/skill.schema.json -r schemas/rule.schema.json --spec=draft2020 -c ajv-formats
```

Expected: `schema schemas/skill.schema.json is valid`. (Verified working during plan research — confirmed with this exact command against this exact schema content.)

- [ ] **Step 4: Commit and push**

```bash
git add schemas/skill.schema.json schemas/rule.schema.json pnpm-lock.yaml
git commit -m "feat(schemas): define skill.schema.json and rule.schema.json"
git push
```

---

### Task 7: JSON Schemas — ticket and simulation_report

**Files:**
- Create: `schemas/ticket.schema.json`
- Create: `schemas/simulation_report.schema.json`

- [ ] **Step 1: Create `schemas/ticket.schema.json`**

Fields per `docs/DESIGN_DOCUMENT.md` §4 ("The Ticket primitive"): amount, days since purchase, customer segment, fraud indicators, refund reason, ground-truth decision.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://skiljo.ai/schemas/ticket.schema.json",
  "title": "Ticket",
  "type": "object",
  "required": ["ticket_id", "refund_amount", "purchase_days_ago", "ground_truth_decision"],
  "properties": {
    "ticket_id": { "type": "string", "format": "uuid" },
    "refund_amount": { "type": "number" },
    "purchase_days_ago": { "type": "integer" },
    "customer_segment": { "type": "string" },
    "fraud_flags": { "type": "array", "items": { "type": "string" } },
    "refund_reason": { "type": "string" },
    "ground_truth_decision": { "type": "string" }
  }
}
```

- [ ] **Step 2: Create `schemas/simulation_report.schema.json`**

Fields per `docs/DESIGN_DOCUMENT.md` §4 ("The SimulationReport primitive") and the `simulation_results` table columns.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://skiljo.ai/schemas/simulation_report.schema.json",
  "title": "SimulationReport",
  "type": "object",
  "required": ["skill_version_id", "match_rate", "escalation_accuracy", "results"],
  "properties": {
    "skill_version_id": { "type": "string", "format": "uuid" },
    "match_rate": { "type": "number", "minimum": 0, "maximum": 1 },
    "escalation_accuracy": { "type": "number", "minimum": 0, "maximum": 1 },
    "contradiction_count": { "type": "integer", "minimum": 0 },
    "automation_candidate_count": { "type": "integer", "minimum": 0 },
    "results": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["ticket_id", "decision", "zone"],
        "properties": {
          "ticket_id": { "type": "string", "format": "uuid" },
          "decision": { "type": "string" },
          "zone": { "type": "string", "enum": ["deterministic", "llm_assisted", "human_only"] },
          "matched_human_decision": { "type": "boolean" },
          "reasoning": { "type": "string" }
        }
      }
    }
  }
}
```

- [ ] **Step 3: Verify all four schemas pass `ajv compile`**

```bash
pnpm exec ajv compile -s schemas/skill.schema.json -r schemas/rule.schema.json --spec=draft2020 -c ajv-formats
pnpm exec ajv compile -s schemas/ticket.schema.json --spec=draft2020 -c ajv-formats
pnpm exec ajv compile -s schemas/simulation_report.schema.json --spec=draft2020 -c ajv-formats
```

Expected: all three commands print `schema ... is valid`.

- [ ] **Step 4: Commit and push**

```bash
git add schemas/ticket.schema.json schemas/simulation_report.schema.json
git commit -m "feat(schemas): define ticket.schema.json and simulation_report.schema.json"
git push
```

---

### Task 8: Pydantic codegen via datamodel-code-generator

**Files:**
- Create: `schemas/codegen/generate_pydantic.py`

- [ ] **Step 1: Create `schemas/codegen/generate_pydantic.py`**

```python
"""Generate Pydantic v2 models from the canonical JSON Schemas in schemas/."""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMAS_DIR = REPO_ROOT / "schemas"
OUTPUT_DIR = REPO_ROOT / "packages" / "core" / "src" / "skiljo_core" / "schemas"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    # datamodel-codegen recursively parses every file under --input, so point it at a
    # directory containing only the *.schema.json files — schemas/codegen/ itself (this
    # script, generate_zod.ts) is not valid JSON/YAML and would otherwise hard-fail.
    with tempfile.TemporaryDirectory() as tmp_dir:
        for schema_file in SCHEMAS_DIR.glob("*.schema.json"):
            shutil.copy2(schema_file, tmp_dir)
        result = subprocess.run(
            [
                "datamodel-codegen",
                "--input", tmp_dir,
                "--input-file-type", "jsonschema",
                "--output", str(OUTPUT_DIR),
                "--output-model-type", "pydantic_v2.BaseModel",
            ],
            check=False,
        )
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
```

> Correction from actual Week 1 execution: with `datamodel-code-generator` 0.64.1, pointing `--input` straight at `schemas/` does **not** skip non-JSON files gracefully — it recursively parses everything under the directory, including `schemas/codegen/generate_pydantic.py` itself, and hard-fails trying to parse Python source as YAML. The fix (above) copies only the top-level `*.schema.json` files into a temp directory and points `--input` there, which also preserves directory-mode's cross-module imports (`skill_schema.py` does `from . import rule_schema` rather than inlining `rule.schema.json`'s defs) — confirmed by running it for real during Task 8.

- [ ] **Step 2: Run it via `make codegen` and verify output**

```bash
uv run python schemas/codegen/generate_pydantic.py
find packages/core/src/skiljo_core/schemas -type f
```

Expected: `__init__.py`, `skill_schema.py`, `rule_schema.py`, `ticket_schema.py`, `simulation_report_schema.py`.

- [ ] **Step 3: Verify the generated models are importable and validate real data**

```bash
uv run python -c "
from skiljo_core.schemas.skill_schema import Skill
from skiljo_core.schemas.rule_schema import DeterministicRule

rule = DeterministicRule(
    condition={'all': [{'field': 'purchase_days_ago', 'op': 'lte', 'value': 30}, {'field': 'fraud_flags', 'op': 'empty'}]},
    action='approve_refund',
)
skill = Skill(
    skill_name='process_refund_request',
    version=1,
    trigger='customer_requests_refund',
    inputs=[{'name': 'refund_amount', 'type': 'number'}],
    decision_zones={'deterministic': [rule.model_dump()], 'llm_assisted': [], 'human_only': []},
)
print('skill ok:', skill.skill_name, skill.version)
"
```

Expected: `skill ok: process_refund_request 1`. (Verified working during plan research with this exact example data, matching the worked example in `docs/DESIGN_DOCUMENT.md` §4.)

- [ ] **Step 4: Commit and push** (including the generated output — codegen output is committed deliberately so diffs are visible in review, per `docs/DESIGN_DOCUMENT.md` §5.1)

```bash
git add schemas/codegen/generate_pydantic.py packages/core/src/skiljo_core/schemas
git commit -m "feat(schemas): Pydantic codegen via datamodel-code-generator"
git push
```

---

### Task 9: Zod codegen via json-schema-to-zod

**Files:**
- Create: `schemas/codegen/generate_zod.ts`

- [ ] **Step 1: Create `schemas/codegen/generate_zod.ts`**

Cross-file `$ref`s (skill → rule) are dereferenced with `@apidevtools/json-schema-ref-parser` before handing the schema to `json-schema-to-zod`, since that library only resolves refs within a single document — verified during plan research.

```typescript
import { writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import $RefParser from "@apidevtools/json-schema-ref-parser";
import { jsonSchemaToZod } from "json-schema-to-zod";

const __dirname = dirname(fileURLToPath(import.meta.url));
const SCHEMAS_DIR = resolve(__dirname, "..");
const OUTPUT_FILE = resolve(__dirname, "..", "..", "packages", "sdk-ts", "src", "types.ts");

const SCHEMAS: Array<[file: string, name: string]> = [
  ["skill.schema.json", "skillSchema"],
  ["rule.schema.json", "ruleSchema"],
  ["ticket.schema.json", "ticketSchema"],
  ["simulation_report.schema.json", "simulationReportSchema"],
];

async function main(): Promise<void> {
  let output = `import { z } from "zod";\n\n`;
  for (const [file, name] of SCHEMAS) {
    const dereferenced = await $RefParser.dereference(resolve(SCHEMAS_DIR, file));
    const generated = jsonSchemaToZod(dereferenced, { module: "esm", name });
    const exportLine = generated.split("\n").find((line) => line.startsWith("export const"));
    if (!exportLine) {
      throw new Error(`failed to generate zod schema for ${file}`);
    }
    output += `${exportLine}\n\n`;
  }
  writeFileSync(OUTPUT_FILE, output);
}

main().catch((error: unknown) => {
  console.error(error);
  process.exitCode = 1;
});
```

- [ ] **Step 2: Run it via `make codegen` and inspect output**

```bash
pnpm install
pnpm exec tsx schemas/codegen/generate_zod.ts
cat packages/sdk-ts/src/types.ts
```

Expected: `types.ts` contains `skillSchema`, `ruleSchema`, `ticketSchema`, `simulationReportSchema` as exported `z.object(...)` (or `z.any()` for `ruleSchema`, which has no usable root type on its own — it's a `$defs`-only file consumed via `$ref`, only ever used inlined into `skillSchema`).

- [ ] **Step 3: Verify the Zod schemas parse valid example data — add a test**

`packages/sdk-ts/src/types.test.ts`:

```typescript
import { describe, expect, it } from "vitest";
import { skillSchema, ticketSchema } from "./types";

describe("generated zod schemas", () => {
  it("parses a valid skill", () => {
    const skill = skillSchema.parse({
      skill_name: "process_refund_request",
      version: 1,
      trigger: "customer_requests_refund",
      inputs: [{ name: "refund_amount", type: "number" }],
      decision_zones: {
        deterministic: [
          { condition: { all: [{ field: "purchase_days_ago", op: "lte", value: 30 }] }, action: "approve_refund" },
        ],
        llm_assisted: [],
        human_only: [],
      },
    });
    expect(skill.skill_name).toBe("process_refund_request");
  });

  it("parses a valid ticket", () => {
    const ticket = ticketSchema.parse({
      ticket_id: "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
      refund_amount: 42.5,
      purchase_days_ago: 10,
      ground_truth_decision: "approve",
    });
    expect(ticket.refund_amount).toBe(42.5);
  });
});
```

```bash
pnpm --filter @skiljo/sdk test
```

Expected: PASS (2 tests). (Verified working during plan research with this exact data.)

- [ ] **Step 4: Commit and push**

```bash
git add schemas/codegen/generate_zod.ts packages/sdk-ts/src/types.ts packages/sdk-ts/src/types.test.ts package.json pnpm-lock.yaml
git commit -m "feat(schemas): Zod codegen via json-schema-to-zod"
git push
```

---

### Task 10: FastAPI skeleton with /health endpoint

**Files:**
- Create: `packages/api/src/skiljo_api/main.py`
- Test: `packages/api/tests/test_health.py`

- [ ] **Step 1: Write the failing test — `packages/api/tests/test_health.py`**

```python
from fastapi.testclient import TestClient

from skiljo_api.main import app


def test_health_returns_ok() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest packages/api/tests/test_health.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'skiljo_api.main'`.

- [ ] **Step 3: Write minimal implementation — `packages/api/src/skiljo_api/main.py`**

```python
from fastapi import FastAPI

app = FastAPI(title="Skiljo API")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

> Correction from actual Week 1 execution: dropped the originally-planned `import os` — nothing in Week 1 scope reads `DATABASE_URL` yet, and an unused import would fail `ruff check .` (F401) in Task 12's CI.

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest packages/api/tests/test_health.py -v
```

Expected: PASS.

- [ ] **Step 5: Verify the dev server actually serves it**

```bash
make api &
sleep 2
curl -s localhost:8000/health
kill %1
```

Expected: `{"status":"ok"}`.

- [ ] **Step 6: Commit and push**

```bash
git add packages/api/src/skiljo_api/main.py packages/api/tests/test_health.py
git commit -m "feat(api): FastAPI skeleton with /health endpoint"
git push
```

---

### Task 11: SQLAlchemy models and Alembic setup

**Files:**
- Create: `packages/core/src/skiljo_core/db/__init__.py`
- Create: `packages/core/src/skiljo_core/db/models.py`
- Test: `packages/core/tests/test_models.py`
- Create: `packages/core/alembic.ini`
- Create: `packages/core/alembic/env.py`
- Create: `packages/core/alembic/script.py.mako`
- Create: `packages/core/alembic/versions/` (autogenerated migration)

This is the 8-table schema from `docs/DESIGN_DOCUMENT.md` §4 ("Database schema"), translated literally — including which FKs are real `REFERENCES` constraints in the SQL vs. plain UUID columns documented only as logical references (`skills.current_version_id`, `simulation_runs.ticket_batch_id`, `simulation_results.ticket_id`, `jobs.result_ref` are **not** real FK constraints in the source SQL; everything else with `REFERENCES` in the SQL is).

- [ ] **Step 1: Write the failing test — `packages/core/tests/test_models.py`**

```python
from skiljo_core.db.models import Base


def test_all_tables_registered() -> None:
    expected = {
        "policies",
        "skills",
        "skill_versions",
        "simulation_runs",
        "simulation_results",
        "llm_calls",
        "jobs",
        "eval_runs",
    }
    assert set(Base.metadata.tables.keys()) == expected
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest packages/core/tests/test_models.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'skiljo_core.db.models'`.

- [ ] **Step 3: Create `packages/core/src/skiljo_core/db/__init__.py`** (empty file)

- [ ] **Step 4: Write minimal implementation — `packages/core/src/skiljo_core/db/models.py`**

```python
import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Numeric, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Policy(Base):
    __tablename__ = "policies"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_filename: Mapped[str | None] = mapped_column(Text)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(server_default=func.now())


class Skill(Base):
    __tablename__ = "skills"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    owner: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    current_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))


class SkillVersion(Base):
    __tablename__ = "skill_versions"
    __table_args__ = (UniqueConstraint("skill_id", "version_number"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    skill_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("skills.id"), nullable=False)
    version_number: Mapped[int] = mapped_column(nullable=False)
    spec: Mapped[dict] = mapped_column(JSONB, nullable=False)
    parent_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("skill_versions.id"))
    source_policy_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("policies.id"))
    status: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class SimulationRun(Base):
    __tablename__ = "simulation_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    skill_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("skill_versions.id"), nullable=False)
    ticket_batch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column()
    completed_at: Mapped[datetime | None] = mapped_column()
    summary: Mapped[dict | None] = mapped_column(JSONB)


class SimulationResult(Base):
    __tablename__ = "simulation_results"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("simulation_runs.id"), nullable=False)
    ticket_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    ticket_data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    decision: Mapped[str] = mapped_column(Text, nullable=False)
    zone: Mapped[str] = mapped_column(Text, nullable=False)
    matched_human_decision: Mapped[bool | None] = mapped_column()
    reasoning: Mapped[str | None] = mapped_column(Text)
    llm_call_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("llm_calls.id"))


class LLMCall(Base):
    __tablename__ = "llm_calls"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_version: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_text: Mapped[str] = mapped_column(Text, nullable=False)
    response_text: Mapped[str] = mapped_column(Text, nullable=False)
    input_tokens: Mapped[int | None] = mapped_column()
    output_tokens: Mapped[int | None] = mapped_column()
    latency_ms: Mapped[int | None] = mapped_column()
    cost_estimate_usd: Mapped[float | None] = mapped_column(Numeric(10, 6))
    called_at: Mapped[datetime] = mapped_column(server_default=func.now())


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict | None] = mapped_column(JSONB)
    result_ref: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column()
    completed_at: Mapped[datetime | None] = mapped_column()


class EvalRun(Base):
    __tablename__ = "eval_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    commit_sha: Mapped[str] = mapped_column(Text, nullable=False)
    dataset_version: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str] = mapped_column(Text, nullable=False)
    metrics: Mapped[dict] = mapped_column(JSONB, nullable=False)
    ran_at: Mapped[datetime] = mapped_column(server_default=func.now())
```

- [ ] **Step 5: Run test to verify it passes**

```bash
uv run pytest packages/core/tests/test_models.py -v
```

Expected: PASS.

- [ ] **Step 6: Set up Alembic — `packages/core/alembic.ini`**

> Correction from actual Week 1 execution: `script_location = alembic` (bare relative path) resolves against the *current working directory*, not the ini file's directory. Since `alembic -c packages/core/alembic.ini` is invoked from the repo root, that looked for `./alembic` and failed with "Path doesn't exist: alembic." Alembic 1.18.4 (newer than this plan's `>=1.13` floor) supports the `%(here)s` token specifically for this — use `script_location = %(here)s/alembic` instead.

```ini
[alembic]
script_location = %(here)s/alembic

[loggers]
keys = root,sqlalchemy,alembic

[logger_root]
level = WARNING
handlers = console
qualname =

[logger_sqlalchemy]
level = WARNING
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handlers]
keys = console

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatters]
keys = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

- [ ] **Step 7: Create `packages/core/alembic/script.py.mako`** (Alembic's standard template)

```mako
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

# revision identifiers, used by Alembic.
revision: str = ${repr(up_revision)}
down_revision: Union[str, None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```

- [ ] **Step 8: Create `packages/core/alembic/env.py`**

```python
import os

from alembic import context
from sqlalchemy import engine_from_config, pool

from skiljo_core.db.models import Base

config = context.config
config.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"])

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 9: Make sure Postgres is up and `.env` is loaded, then generate the initial migration**

```bash
docker compose up -d postgres
set -a; source .env; set +a
uv run alembic -c packages/core/alembic.ini revision --autogenerate -m "initial schema"
```

Expected: a new file under `packages/core/alembic/versions/` containing `op.create_table(...)` calls for all 8 tables.

- [ ] **Step 10: Apply the migration and verify**

```bash
make migrate
docker compose exec postgres psql -U skiljo -d skiljo -c "\dt"
```

Expected: `make migrate` exits 0; `\dt` lists all 8 tables.

- [ ] **Step 11: Commit and push**

```bash
git add packages/core/src/skiljo_core/db packages/core/tests/test_models.py packages/core/alembic.ini packages/core/alembic
git commit -m "feat(db): SQLAlchemy models and Alembic setup"
git push
```

---

### Task 12: GitHub Actions CI for lint, typecheck, test

**Files:**
- Create: `.github/workflows/ci.yml`

- [ ] **Step 1: Create `.github/workflows/ci.yml`**

```yaml
name: CI

on:
  push:
    branches: ["**"]
  pull_request:

jobs:
  python:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
        with:
          version: "latest"
      - run: uv sync --all-packages
      - run: uv run ruff check .
      - run: uv run mypy packages/core/src packages/api/src packages/demo/src --exclude 'schemas/'
      - run: uv run pytest

  typescript:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: pnpm/action-setup@v4
        with:
          version: "10"
      - uses: actions/setup-node@v4
        with:
          node-version: "22"
          cache: "pnpm"
      - run: pnpm install --frozen-lockfile
      - run: pnpm --filter @skiljo/sdk exec tsc --noEmit
      - run: pnpm -r test
```

- [ ] **Step 2: Run the same checks locally first, to catch failures before pushing**

```bash
uv run ruff check .
uv run mypy packages/core/src packages/api/src packages/demo/src --exclude 'schemas/'
uv run pytest
pnpm --filter @skiljo/sdk exec tsc --noEmit
pnpm -r test
```

Expected: all exit 0. Fix anything that doesn't before proceeding (likely candidates: ruff complaining about generated `schemas/codegen/generate_*` scripts' import order, or mypy complaining about the `Mapped[dict]` columns needing `dict[str, Any]` — adjust types as needed, these are real fixes, not placeholders to defer).

- [ ] **Step 3: Commit and push, then watch the Actions run on GitHub**

```bash
git add .github/workflows/ci.yml
git commit -m "chore: GitHub Actions CI for lint, typecheck, test"
git push
gh run watch
```

Expected: `gh run watch` follows the run to completion with both `python` and `typescript` jobs green. This is the acceptance criterion for this commit — fix forward on any CI-only failures (e.g. lockfile drift caught by `--frozen-lockfile`) until it's green.

---

### Task 13: README with architecture overview and setup instructions

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Replace the placeholder `README.md`**

```markdown
# Skiljo

Skiljo extracts a company's refund, credit, and billing-adjustment policies — plus how the team actually handles cases historically — into versioned, executable **Skills**: structured workflow specs an AI agent can run safely, with approval gates and a full audit trail.

The MVP's value isn't live automation. It's a historical simulation report plus a "policy vs. practice" contradiction report: where written policy and actual behavior diverge. See `docs/BRD.md` and `docs/PRFAQ.md` for the product framing, and `docs/DESIGN_DOCUMENT.md` for the full technical design and the 6-week, commit-by-commit build plan this repo follows.

**Status:** Week 1 of 6 complete — foundations only (this commit). No extraction, simulation, or demo UI logic exists yet; see `docs/DESIGN_DOCUMENT.md` §11 for what's planned each week.

## Architecture

A Python monorepo (`core`, `api`, `demo`) plus a TypeScript SDK (`sdk-ts`), with JSON Schema as the single source of truth for data shapes — codegen produces Pydantic models for Python and Zod schemas for TypeScript.

```
┌─────────────────────────────────────────────────────────────────┐
│                     Streamlit Demo (Python)                      │
│       upload policy → extract skill → review → simulate          │
└──────────────────────────────┬──────────────────────────────────┘
                               │ HTTP
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                       FastAPI Backend (Python)                   │
│  Background tasks via FastAPI BackgroundTasks                    │
│  Job state tracked in Postgres                                   │
└────┬─────────────────────────┬──────────────────┬───────────────┘
     │                         │                  │
     ▼                         ▼                  ▼
┌──────────┐            ┌─────────────┐    ┌────────────────┐
│   LLM    │            │  Postgres   │    │  Eval Harness  │
│  Client  │            │  (8 tables) │    │   (Inspect)    │
└──────────┘            └─────────────┘    └────────────────┘
         ▲                                          ▲
         └────── consumed by ──── TypeScript SDK ───┘
                                  (Zod types from
                                   same JSON Schema)
```

Three invariants hold throughout: every LLM call is logged to `llm_calls`; skill specs are immutable (new versions are new `skill_versions` rows, never updates); the eval harness runs in CI on every PR and blocks merge on regression. Full detail in `docs/DESIGN_DOCUMENT.md` §3.

## Setup

Prerequisites: [uv](https://docs.astral.sh/uv/), [pnpm](https://pnpm.io/), Docker Desktop.

```bash
git clone https://github.com/chrisokor/skiljo.git
cd skiljo
cp .env.example .env
docker compose up -d postgres
make setup
make api
```

`make api` starts the FastAPI server on `localhost:8000` — confirm with `curl localhost:8000/health`.

## Daily dev

```bash
make api         # FastAPI dev server
make demo        # Streamlit demo (functional from Week 4 onward)
make test        # pytest + vitest
make lint        # ruff
make typecheck   # mypy + tsc
make codegen     # regenerate Pydantic/Zod types after a schema change
```

Run `make help` for the full list of targets.

## Repo layout

- `schemas/` — canonical JSON Schemas (source of truth) and the codegen scripts that generate Pydantic/Zod types from them.
- `packages/core/` — extraction, simulation, and storage logic; SQLAlchemy models and Alembic migrations.
- `packages/api/` — FastAPI backend.
- `packages/demo/` — Streamlit demo UI.
- `packages/sdk-ts/` — TypeScript client SDK.
- `docs/` — business requirements, design document, press release/FAQ, and the evaluation policy corpus.

## License

MIT — see `LICENSE`.
```

- [ ] **Step 2: Clean-room verification — confirm a reader following only this README can set up the project**

```bash
docker compose down -v
rm -rf .venv node_modules packages/*/node_modules packages/sdk-ts/dist .env
cp .env.example .env
docker compose up -d postgres
make setup
make api &
sleep 2
curl -s localhost:8000/health
kill %1
```

Expected: `{"status":"ok"}` — the exact acceptance criterion for this commit.

- [ ] **Step 3: Commit and push**

```bash
git add README.md
git commit -m "docs: README with architecture overview and setup instructions"
git push
```

---

## Final verification (Week 1 complete)

- [ ] `gh run list --limit 1` shows the latest CI run as green on `main`.
- [ ] `make setup && make api` works from a clean clone (re-verify per Task 13 Step 2 if anything changed since).
- [ ] `git log --oneline` shows 13 commits matching the conventional-commit messages above.
- [ ] Cross-check against `docs/DESIGN_DOCUMENT.md` §11 "Week 1 — Foundations" deliverables list — every item is present.
