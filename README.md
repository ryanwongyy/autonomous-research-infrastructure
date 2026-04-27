# Autonomous Research Infrastructure (APE Replica)

Autonomous AI governance research with end-to-end transparency.
The system designs, executes, reviews, and tournament-ranks its own papers,
publishing every step — including failures and corrections — for human
researchers to audit, replicate, and challenge.

> **Mission:** Communicate research outputs and indicators effectively, and
> encourage human researchers to review AI-generated papers.

---

## Architecture

```
┌─────────────────┐         ┌─────────────────┐
│  Next.js (16)   │ ──HTTP──▶│  FastAPI        │
│  frontend/      │         │  backend/       │
│  Vercel         │         │  Render / Fly   │
└─────────────────┘         └────────┬────────┘
                                     │
                            ┌────────┴────────┐
                            │  PostgreSQL 16  │
                            │  (SQLite local) │
                            └─────────────────┘
```

- **Frontend:** Next.js 16 + React 19, Tailwind v4, shadcn/ui, recharts.
  Tests: vitest (185+) + Playwright E2E (74+).
- **Backend:** FastAPI + SQLAlchemy 2 (async) + Alembic. Tests: pytest (288+).
- **Database:** PostgreSQL in production, SQLite in development and tests.
- **AI:** Anthropic, OpenAI, Google GenAI providers (any one is sufficient).

See `frontend/src/app/methodology/page.tsx` for the full research pipeline:
7-role generation, 5-layer independent review, family-local TrueSkill
tournament, manifest-drift gates, novelty detection, and 4-tier RSI.

---

## Quick start

### Option A — Docker (full stack)

```bash
cp .env.example .env  # fill in at least one LLM API key
docker compose up --build
# frontend: http://localhost:3000
# backend:  http://localhost:8001
```

### Option B — Local dev (recommended for iterating)

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload --port 8001

# Frontend (new terminal)
cd frontend
npm ci
npm run dev          # http://localhost:3000
```

---

## Running tests

| Stack    | Command                                     | Count |
| -------- | ------------------------------------------- | ----- |
| Backend  | `cd backend && pytest`                      | 288+  |
| Frontend | `cd frontend && npm test`                   | 185+  |
| E2E      | `cd frontend && npm run test:e2e`           | 74+   |
| All      | see `Makefile` (root)                       | 540+  |

E2E tests require both backend and frontend running. The Playwright config
auto-spins a real mock backend on port 8000.

See [`TESTING.md`](./TESTING.md) for conventions and how to add new tests.

---

## Repository layout

```
backend/
  app/
    api/            FastAPI routers (papers, leaderboard, reviews, …)
    services/       Pipeline logic (generation, review, tournament, RSI)
    models/         SQLAlchemy ORM
    schemas/        Pydantic request/response models
  alembic/          DB migrations  (see MIGRATIONS.md)
  tests/            pytest suite
  domain_configs/   YAML defining the 11 paper families
  seeds/            Bootstrap data

frontend/
  src/app/          Next.js app router pages
  src/components/   Shared UI (paper cards, charts, layout)
  e2e/              Playwright specs
  AGENTS.md         Next.js 16 breaking-change notes for contributors

.github/workflows/  CI definitions
docker-compose.yml  Full-stack local dev
render.yaml         Backend deployment (Render)
```

---

## Deployment

- **Frontend:** Vercel (auto-deploys from `main`). Set `NEXT_PUBLIC_API_URL`
  to the backend URL.
- **Backend:** Render (`render.yaml`) or Fly.io. Requires `DATABASE_URL`
  pointing to a managed Postgres instance and at least one LLM API key.
- **Database:** Supabase / Neon / Render Postgres all work. The connection
  string strips `?sslmode=` automatically for asyncpg compatibility.

---

## How researchers can engage

1. **Browse outputs.** [`/publications`](https://ape-replica.example.com/publications)
   lists every public paper with its rating, novelty verdict, and review
   trail.
2. **Audit methodology.** [`/methodology`](https://ape-replica.example.com/methodology)
   documents every pipeline stage, gate, and improvement loop.
3. **Submit expert reviews.** Each paper page has an "Expert review invited"
   call to action — domain-expert feedback feeds directly into reliability
   metrics.
4. **Report errors.** [`/corrections`](https://ape-replica.example.com/corrections)
   tracks every error the system catches; researchers can flag missed errors
   via GitHub Issues.

---

## Contributing

- Read [`CONTRIBUTING.md`](./CONTRIBUTING.md) before opening a PR.
- Branching: PRs to `main`. CI must be green (`make ci`).
- Style: ruff (backend), eslint + tsc (frontend). Pre-commit hooks recommended
  (`pre-commit install`).
- Tests: every behavioural change ships with a test. See [`TESTING.md`](./TESTING.md).
- Migrations: `make migrate-new MSG="…"`; see [`MIGRATIONS.md`](./MIGRATIONS.md).

---

## Documentation map

| File                                  | Purpose                                                |
| ------------------------------------- | ------------------------------------------------------ |
| [`README.md`](./README.md)            | This file — overview, quick start                      |
| [`ARCHITECTURE.md`](./ARCHITECTURE.md)| Engineering decisions and data model                   |
| [`CONTRIBUTING.md`](./CONTRIBUTING.md)| Workflow, conventions, project approaches              |
| [`TESTING.md`](./TESTING.md)          | Test discipline across all three surfaces              |
| [`MIGRATIONS.md`](./MIGRATIONS.md)    | Alembic migration workflow and pitfalls                |
| [`frontend/README.md`](./frontend/README.md) | Frontend-specific scripts and conventions       |
| [`frontend/AGENTS.md`](./frontend/AGENTS.md) | Next.js 16 breaking-change notes                |
| `/methodology` page                   | The actual research methodology (live)                 |
| `/glossary` page                      | All terminology defined in one place                   |

---

## License

MIT. See `LICENSE` (when added).
