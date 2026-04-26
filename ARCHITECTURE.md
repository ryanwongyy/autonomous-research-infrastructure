# Architecture

How the autonomous research infrastructure is engineered. Updated when
structural decisions change.

---

## System overview

```
┌──────────────────────────────────────────────────────────────────────┐
│                        Browser                                       │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │  Next.js 16 (App Router) — Vercel                              │  │
│  │   • Server Components fetch via serverFetch()                  │  │
│  │   • Client Components fetch via clientFetch()                  │  │
│  │   • Tailwind v4 + shadcn/ui components                         │  │
│  └─────────────────────────────────┬──────────────────────────────┘  │
└────────────────────────────────────┼─────────────────────────────────┘
                                     │ HTTPS · NEXT_PUBLIC_API_URL
                                     ▼
┌──────────────────────────────────────────────────────────────────────┐
│  FastAPI · Render / Fly                                              │
│  ┌──────────────────────────────────────────────────────────────┐    │
│  │  api/                Routers (papers, reviews, leaderboard…) │    │
│  │  services/                                                    │    │
│  │    paper_generation/   7-role generation orchestrator         │    │
│  │    review_pipeline/    L1-L5 independent reviews              │    │
│  │    tournament/         TrueSkill match scheduling + judging   │    │
│  │    collegial/          Convergence-based draft refinement     │    │
│  │    novelty/            Jaccard similarity gate                │    │
│  │    release/            Release-stage transitions              │    │
│  │    rsi/                Recursive self-improvement loops       │    │
│  │    outcomes/           Submission outcome tracking            │    │
│  │    provenance/         Source-card / claim-permission audit   │    │
│  │  models/             SQLAlchemy ORM (declarative)             │    │
│  │  schemas/            Pydantic request/response types          │    │
│  │  tasks/              APScheduler background jobs              │    │
│  └──────────────────────────────────────────────────────────────┘    │
└────────────────────────────────────┬─────────────────────────────────┘
                                     │ asyncpg / aiosqlite
                                     ▼
                          ┌─────────────────────┐
                          │  PostgreSQL 16      │
                          │  (SQLite for dev)   │
                          └─────────────────────┘
                                     │
                                     ▼
                       ┌─────────────────────────┐
                       │  LLM Providers          │
                       │  Anthropic / OpenAI /   │
                       │  Google GenAI           │
                       └─────────────────────────┘
```

---

## Engineering approach

### Async everywhere

Backend uses SQLAlchemy 2.0 async + asyncpg in production. There is no
sync ORM session in the request path. All FastAPI route handlers are
`async def`. All tests use `pytest-asyncio` in `auto` mode.

### Single source of truth for types

- Pydantic schemas (`backend/app/schemas/`) own the API contract.
- Types in `frontend/src/lib/types.ts` mirror the schemas by hand
  (intentionally — no runtime codegen, easy to read in PRs).
- When schema changes, update both sides in the same PR.

### Server-first frontend

Default to Server Components. Reach for Client Components only for
interactivity, browser APIs, or state. This keeps bundles small and
makes API calls (via `serverFetch`) immediate rather than waterfalled.

### Explicit auth boundaries

- Public GET endpoints (papers, leaderboard, reliability) require no auth.
- Mutations require `APE_API_KEY` via `MutationAuthMiddleware`.
- Admin actions require `APE_ADMIN_KEY` via `admin_key_required` dep.
- Auth is centralized in `app/auth.py`; routers don't reimplement it.

---

## Data model — key entities

| Entity                | File                                    | Notes                                                              |
| --------------------- | --------------------------------------- | ------------------------------------------------------------------ |
| `Paper`               | `models/paper.py`                       | Central. Has `release_status`, `funnel_stage`, `family_id`         |
| `PaperFamily`         | `models/paper_family.py`                | One of the 11 families; locks methodology and target venues        |
| `Rating`              | `models/rating.py`                      | TrueSkill (μ, σ, conservative, Elo) — one row per paper            |
| `Review`              | `models/review.py`                      | L1-L5 layers; `stage` enum                                         |
| `Match`               | `models/match.py`                       | Tournament head-to-head record                                     |
| `CollegialSession`    | `models/collegial.py`                   | Convergence-based refinement transcript                            |
| `SignificanceMemo`    | `models/significance_memo.py`           | Human verdict (Submit / Hold / Reject)                             |
| `ExpertReview`        | `models/expert_review.py`               | External domain expert scores                                      |
| `Correction`          | `models/correction.py`                  | Post-publication errata, updates, retractions                      |
| `SourceCard`          | `models/source_card.py`                 | Tier + claim-permission profile                                    |
| `AutonomyCard`        | `models/autonomy_card.py`               | Per-paper role-by-role automation level                            |
| `RsiExperiment`       | `models/rsi_experiment.py`              | A/B experiment registry for self-improvement                       |

The Paper lifecycle moves through `funnel_stage` (scout → designer →
data_steward → analyst → drafter → verifier → packager → published) and
`release_status` (internal → candidate → submitted → public) on
orthogonal axes.

---

## Why these choices

### Why FastAPI + SQLAlchemy 2 async + asyncpg?

LLM calls dominate the latency budget. Async lets a single worker handle
many in-flight generations without thread overhead. `asyncpg` is the
fastest Postgres driver available; the only reason to use anything else
is if you need a sync feature it doesn't expose.

### Why SQLite in tests?

Tests don't exercise vendor-specific Postgres features. SQLite in-memory
+ `StaticPool` is ~3× faster than ephemeral Postgres containers and
reproduces 99% of bugs. The 1% (case-sensitive collation, JSON ops,
specific constraint behaviour) is covered by integration tests in CI
that opt into Postgres.

### Why TrueSkill not Elo?

Elo treats every match equally — a paper with one win and one loss has
the same rating as a paper with 50 wins and 50 losses. TrueSkill encodes
uncertainty (σ) and the conservative rating (μ − 3σ) penalises sparse
data. For a small cohort of papers per family, that uncertainty-awareness
matters.

### Why three LLM providers?

No single model is reliably best at all roles. Drafter and Adversarial
reviewer use different families (Claude vs GPT-4 vs Gemini) to reduce
correlated failures. The provider router (`services/llm/`) selects
per-role based on family config. This also gives us a fallback when one
provider has an outage.

### Why per-family lock protocols?

Without locked methodology, a family becomes a dumping ground. The
Designer role can only choose from a fixed set of identification
strategies per family (e.g. RDD, DiD, IV, QCA). This keeps tournaments
fair (you're comparing comparable papers) and makes per-family
benchmarking possible against peer-reviewed literature.

### Why convergence-based collegial review?

Fixed-round review wastes effort on already-good papers and rushes weak
ones. Convergence-based review keeps iterating until quality plateaus,
then exits. The 5-round cap prevents infinite loops on papers that
fundamentally can't be saved.

---

## Pipeline timing (rough)

| Stage             | Duration (typical)  | Cost (typical)      |
| ----------------- | ------------------- | ------------------- |
| Scout             | 30 s                | $0.05               |
| Designer          | 60 s                | $0.20               |
| Data Steward      | 120 s               | $0.30               |
| Analyst           | 300 s               | $0.50               |
| Drafter           | 240 s               | $0.80               |
| L1 + L2 reviews   | 60 s (parallel)     | $0.10               |
| L3 + L4 reviews   | 180 s (parallel)    | $0.40               |
| Tournament (10 m) | 600 s               | $1.50               |
| Collegial (5 r)   | 600 s               | $1.20               |
| **Total**         | **≈ 30-40 min**     | **≈ $5 per paper**  |

Actual numbers vary widely by family and provider mix. RSI tunes prompts
to compress these.

---

## Failure modes & guards

| Failure                                | Guard                                                              |
| -------------------------------------- | ------------------------------------------------------------------ |
| Designer fabricates data sources       | Source-card registry; Designer can only pick from registered cards |
| Analyst diverges from locked design    | Manifest-drift gate (Analysis-Design Alignment) before drafting    |
| Drafter overstates findings            | Manifest-drift gate (Claims-Analysis Alignment) before packaging   |
| L3 method review rubber-stamps         | Different LLM family from Drafter; non-Claude or human             |
| Tournament judge has positional bias   | Position-swapped judging; if judges disagree → draw                |
| RSI degrades performance silently      | Shadow mode + A/B + auto-rollback if > 10% degradation             |
| Novelty check accepts derivative       | Hard threshold at 0.6 Jaccard; family-local                        |
| Source drifts post-publication         | Reliability dashboard; periodic re-validation                      |

---

## Operational notes

- **Background jobs** run in APScheduler inside the FastAPI process.
  This is fine up to ~100 jobs/hour. Beyond that, externalise to a
  separate worker process.
- **Idempotency:** mutation endpoints accept an `Idempotency-Key` header
  where it matters (paper import, batch promotion). Repeats return the
  prior result rather than duplicating work.
- **Rate limiting:** `slowapi` is wired into select public endpoints to
  prevent scraping abuse. Internal endpoints are unlimited.
- **Observability:** Sentry SDK captures errors. Structured logs via
  Python `logging` with JSON formatter. Add a request ID middleware for
  cross-service correlation when adding new entry points.

---

## Future work (sketches, not commitments)

- **Object storage for paper bodies.** Paper markdown currently lives
  in the DB. Once the corpus exceeds a few hundred MB, move to S3/R2
  with content-addressed keys for stable provenance URIs. See
  [`README.md`](./README.md) for the storage tier discussion.
- **Versioned methodology.** Today the methodology page is the live
  state. A versioned form (`/methodology/v3` etc.) would let papers
  cite the exact methodology revision they were produced under.
- **External reviewer accounts.** Currently expert review submissions
  go through GitHub Issues. Native accounts + scoped tokens would
  reduce friction.
- **Federated tournaments.** Family-local tournaments are family-local
  by design, but inter-family comparisons (with explicit caveats)
  could be useful for portfolio-level reporting.

---

## See also

- [`README.md`](./README.md) — architecture overview, quick start
- [`CONTRIBUTING.md`](./CONTRIBUTING.md) — workflow, conventions
- [`TESTING.md`](./TESTING.md) — test discipline
- [`MIGRATIONS.md`](./MIGRATIONS.md) — DB migration discipline
- [`/methodology`](./frontend/src/app/methodology/page.tsx) — what the
  system actually *does*
