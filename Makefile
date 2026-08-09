.PHONY: help setup codegen test lint typecheck api demo migrate clean eval-extraction eval-simulation eval-e2e

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
	uv run streamlit run packages/demo/src/app.py

migrate: ## Apply database migrations
	uv run alembic -c packages/core/alembic.ini upgrade head

# Eval suites run against Inspect's mockllm/model by default (no API key, no cost).
# None has a dataset loader/solver wired to data/eval/train/ yet, so scores are
# vacuous (1.0) until that lands -- see docs/evals.md. Override with MODEL=... once
# it does, e.g. `make eval-extraction MODEL=anthropic/claude-sonnet-4-6`.
MODEL ?= mockllm/model

eval-extraction: ## Run the extraction eval suite
	uv run inspect eval packages/core/src/skiljo_core/eval/extraction.py --model $(MODEL)

eval-simulation: ## Run the simulation eval suite
	uv run inspect eval packages/core/src/skiljo_core/eval/simulation.py --model $(MODEL)

eval-e2e: ## Run the end-to-end eval suite
	uv run inspect eval packages/core/src/skiljo_core/eval/e2e.py --model $(MODEL)

clean: ## Remove caches and build artifacts
	find . -type d -name '__pycache__' -exec rm -rf {} +
	rm -rf .pytest_cache .mypy_cache .ruff_cache
	rm -rf packages/sdk-ts/dist
	rm -rf logs eval-results.json
