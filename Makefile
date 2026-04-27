# Autonomous Research Infrastructure — root convenience targets.
#
# Run `make help` for a list. Targets are named so they read like English
# (`make test`, `make lint-backend`, `make docker-up`).
#
# Most targets simply delegate to backend/ or frontend/ — the value is
# having a single consistent entry point.

.PHONY: help install install-backend install-frontend \
        dev dev-backend dev-frontend \
        test test-backend test-frontend test-e2e \
        lint lint-backend lint-frontend \
        format format-backend \
        typecheck typecheck-frontend \
        build build-frontend \
        migrate migrate-up migrate-down migrate-new \
        docker-up docker-down docker-logs \
        clean clean-pyc clean-node \
        verify ci

# Default goal
.DEFAULT_GOAL := help

# ── Help ─────────────────────────────────────────────────────────────

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?##' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?##"}; {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}'

# ── Install ──────────────────────────────────────────────────────────

install: install-backend install-frontend  ## Install all dependencies (both stacks)

install-backend:  ## Install backend Python deps
	cd backend && python -m pip install -e ".[dev]"

install-frontend:  ## Install frontend npm deps
	cd frontend && npm ci

# ── Development ──────────────────────────────────────────────────────

dev:  ## Start frontend + backend dev servers (run in two terminals)
	@echo "Run these in two terminals:"
	@echo "  make dev-backend"
	@echo "  make dev-frontend"

dev-backend:  ## Backend dev server with hot reload (port 8001)
	cd backend && uvicorn app.main:app --reload --port 8001

dev-frontend:  ## Frontend dev server with HMR (port 3000)
	cd frontend && npm run dev

# ── Tests ────────────────────────────────────────────────────────────

test: test-backend test-frontend  ## Run backend + frontend unit/integration tests

test-backend:  ## Backend pytest suite (288+ tests)
	cd backend && pytest -q

test-frontend:  ## Frontend vitest suite (185+ tests)
	cd frontend && npm test

test-e2e:  ## End-to-end Playwright tests (74+ tests, requires backend mock)
	cd frontend && npm run test:e2e

# ── Lint / Type / Format ────────────────────────────────────────────

lint: lint-backend lint-frontend  ## Lint both stacks

lint-backend:  ## ruff check
	cd backend && ruff check app/ tests/

lint-frontend:  ## eslint
	cd frontend && npm run lint

format: format-backend  ## Auto-format (currently backend only)

format-backend:  ## ruff format + ruff check --fix
	cd backend && ruff format app/ tests/ && ruff check app/ tests/ --fix

typecheck: typecheck-frontend  ## Typecheck (frontend only; backend uses runtime types)

typecheck-frontend:  ## tsc --noEmit
	cd frontend && npx tsc --noEmit

# ── Build ────────────────────────────────────────────────────────────

build: build-frontend  ## Build for production

build-frontend:  ## Next.js production build
	cd frontend && npm run build

# ── Database migrations ──────────────────────────────────────────────

migrate: migrate-up  ## Alias for migrate-up

migrate-up:  ## Apply all pending migrations
	cd backend && alembic upgrade head

migrate-down:  ## Roll back the most recent migration
	cd backend && alembic downgrade -1

migrate-new:  ## Auto-generate a new migration. Usage: make migrate-new MSG="add x column"
	@if [ -z "$(MSG)" ]; then echo "Usage: make migrate-new MSG=\"description\""; exit 1; fi
	cd backend && alembic revision --autogenerate -m "$(MSG)"

# ── Docker ───────────────────────────────────────────────────────────

docker-up:  ## Start full stack via docker compose
	docker compose up --build -d

docker-down:  ## Stop and remove containers
	docker compose down

docker-logs:  ## Tail logs from all services
	docker compose logs -f

# ── Cleanup ──────────────────────────────────────────────────────────

clean: clean-pyc clean-node  ## Remove caches and build artifacts

clean-pyc:  ## Remove Python bytecode caches
	find . -type d -name "__pycache__" -not -path "./node_modules/*" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -not -path "./node_modules/*" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -not -path "./node_modules/*" -exec rm -rf {} + 2>/dev/null || true

clean-node:  ## Remove Next.js build cache and node_modules
	rm -rf frontend/.next frontend/node_modules

# ── Composite gates ──────────────────────────────────────────────────

verify: lint typecheck test  ## Pre-PR gate: lint + typecheck + test (no e2e, no build)

ci: lint typecheck test build  ## Full CI gate: lint + typecheck + test + build (matches GitHub Actions)
