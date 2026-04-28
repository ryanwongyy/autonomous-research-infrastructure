# Autodevelop Report — End-to-End Tests

**Mission:** Build end-to-end test suite for the ARI backend API
**Mode:** Develop
**Budget:** 240m | **Used:** ~25m (10%)
**Iterations:** 8 | **Changes:** 10 files created/edited, 0 reverts (100% keep rate)

## Verification Gate
| Check | Baseline | Final | Delta |
|-------|----------|-------|-------|
| Tests passing | 80 | 179 | +99 |
| Tests failing | 0 | 0 | 0 |
| Test duration | 13.2s | 14.0s | +0.8s |

## New Test Files Created

| File | Tests | Covers |
|------|-------|--------|
| `test_families.py` | 11 | GET /families, GET /families/{id}, active filter, paper counts, JSON parsing |
| `test_leaderboard.py` | 12 | GET /leaderboard, sort_by (conservative_rating, elo, mu), filters (source, category), pagination, 404/422 |
| `test_stats.py` | 8 | GET /stats, /stats/rating-distribution, /stats/trueskill-progression |
| `test_throughput.py` | 10 | GET /throughput/funnel, conversion-rates, bottlenecks, projections, daily-targets, work-queue |
| `test_health.py` | 5 | GET /health, security headers (X-Content-Type-Options, X-Frame-Options, Referrer-Policy), CORS, request ID |
| `test_batch.py` | 7 | POST /batch/seed-families (create + idempotency), /batch/review-pending, /batch/promote, /batch/generate, admin key gating |
| `test_papers_extended.py` | 6 | GET /papers/public, /papers/feed.json, /papers/{id}/export |
| `test_matches_tournament.py` | 7 | GET /matches, /matches/{id}, /tournament/runs, /tournament/runs/{id}, admin auth for POST /tournament/run |
| `test_release_api.py` | 7 | GET /release/status, /papers/{id}/release, /papers/{id}/release/preconditions, POST /papers/{id}/release/transition |
| `test_sources_api.py` | 8 | GET /sources, /sources/{id}, /sources/{id}/snapshots, tier filter, active filter |
| `test_reviews_api.py` | 6 | GET /papers/{id}/reviews, POST /papers/{id}/review, response shape |
| `test_reliability_outcomes.py` | 12 | GET /reliability/overview, /reliability/family/{id}, /reliability/paper/{id}, POST+GET /papers/{id}/outcomes, GET /outcomes/dashboard, GET /categories |

## Key Findings

1. **batch.py bypasses DI**: Uses `async_session` directly instead of `Depends(get_db)`. Must monkeypatch `app.api.batch.async_session` in tests.
2. **SourceCard requires NOT NULL**: `claim_permissions` and `claim_prohibitions` are NOT NULL columns — fixtures must provide JSON strings.
3. **Export needs artifacts**: `/papers/{id}/export` returns 404 if no PDF/TeX path is set on the paper.

## Remaining Gaps

1. **Frontend test infrastructure**: No test runner installed. Needs `vitest`, `@testing-library/react`, `@testing-library/jest-dom` as devDependencies. Cannot install without radical change authorization.
2. **Untested API modules**: `config.py` (4 endpoints), `autonomy.py` (2), `cohorts.py` (3), `significance_memos.py` (2), `provenance.py` (3) still have 0 tests.
3. **Mutation tests**: POST endpoints for papers/import, collegial review creation, and expert review creation have tests but no negative-path coverage (malformed payloads, boundary values).
4. **Integration tests with seeded pipeline data**: Tests currently use minimal fixtures. Richer fixtures simulating a full pipeline run (family → papers → ratings → reviews → tournament → release) would catch integration bugs.
5. **Playwright E2E**: True browser-based E2E testing the frontend→backend flow requires Playwright setup (new dependency).
