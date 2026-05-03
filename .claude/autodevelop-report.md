# Autodevelop Report — Methods, Processes, Workflows, Skills & Approaches

**Mission:** Focus on methods, processes, workflows, skills and approaches; radical and incremental change welcomed.
**Mode:** Hybrid (radical changes permitted)
**Budget:** 480m | **Wall-clock used:** ~665m (gaps included; 19 iterations of active work)
**Iterations:** 19 | **Changes:** 19 kept, 0 reverted (**100% keep rate**)

---

## Verification Gate

| Check                      | Baseline | Final | Delta |
| -------------------------- | -------: | ----: | ----- |
| Backend pytest             |      288 |   291 | +3    |
| Frontend vitest            |      185 |   185 | —     |
| E2E Playwright             |       74 |    74 | —     |
| Backend ruff               |    impl. | clean (custom config) | hardened |
| Frontend tsc --noEmit      |     fail (1 err) | clean | fixed |
| Backend tests pass         |       ✅ |    ✅ |       |

---

## What Shipped (by mission pillar)

### 1. **Methods** — researcher communication of methodology

| # | Change | Files |
|---|--------|-------|
| 2 | Methodology terminology batch — TrueSkill (μ/σ definition, conservative rating formula), novelty verdict space (Novel/Marginal/Derivative with thresholds), manifest drift preface ("scope creep" analogy), autonomy card formal definition with example, RSI 4-tier nested feedback explanation | `frontend/src/app/methodology/page.tsx` |
| 3 | Standardize L1-L5 notation (was "Layer 1: Structural Review", now "L1 Structural Review") | `methodology/page.tsx` |
| 8 | **`/glossary` page** — 22 entries A-T covering every domain term, alphabetical letter index, internal anchors, see-also cross-refs, methodology section deep-links | `frontend/src/app/glossary/page.tsx` (new), `navbar.tsx`, `footer.tsx` |
| 12 | Methodology — collegial outcome paths (Converged/Plateaued/Max Rounds with downstream consequences) + significance memo verdict criteria (Submit/Hold/Reject) | `methodology/page.tsx` |
| 17 | Homepage stat-card definitions + tooltips on Total Active / Submission Ready / Families Active / Public Papers | `app/page.tsx` |
| 18 | **Visual pipeline diagram** at top of methodology page — gestalt before deep dive (Generate → Evaluate → Release & Track + RSI feedback) | `methodology/page.tsx` |

### 2. **Processes & Workflows** — engineering discipline

| # | Change | Files |
|---|--------|-------|
| 4 | **Root README.md** — architecture, quick-start (Docker + local), test matrix, deployment, researcher-engagement section | `README.md` (new) |
| 5 | **TESTING.md** — conventions for pytest, vitest, Playwright; common failures table; failing-test-first discipline | `TESTING.md` (new) |
| 6 | **MIGRATIONS.md** — Alembic workflow, naming, conflict resolution, backfill patterns, production checklist | `MIGRATIONS.md` (new) |
| 7 | Frontend README rewrite (was create-next-app boilerplate) + **backend ruff config** (pyproject.toml `[tool.ruff]`) — strict ruleset (E/W/F/I/B/UP/SIM/RUF), 272 auto-fixes accepted, 78 stylistic legacy items deferred to TODO | `frontend/README.md`, `backend/pyproject.toml` |
| 9 | **`.pre-commit-config.yaml`** — universal hygiene + ruff + tsc + eslint hooks | `.pre-commit-config.yaml` (new) |
| 10 | **Root Makefile** — 30+ named targets (`make verify`, `make ci`, `make migrate-new`, `make test:e2e`, etc.) with `make help` | `Makefile` (new) |
| 11 | Improved empty states on Publications + Leaderboard — guide researchers to methodology/glossary/reliability/corrections while DB seeds | `publications/page.tsx`, `leaderboard/page.tsx` |
| 19 | **CI hardening** — concurrency cancel-in-progress, pip + npm caching, ruff format check, pytest with coverage XML, Playwright E2E job, advisory pip-audit + npm-audit security job | `.github/workflows/ci.yml` |

### 3. **Skills & Approaches** — onboarding + philosophy

| # | Change | Files |
|---|--------|-------|
| 14 | **CONTRIBUTING.md** — six explicit project approaches (transparency by default, provenance over polish, mechanical verification, atomic changes, removal-as-feature, talk-to-the-reader), workflow, conventions, what we don't want | `CONTRIBUTING.md` (new) |
| 15 | **ARCHITECTURE.md** — system diagram, data model, "why these choices" rationale (TrueSkill vs Elo, async, three providers, per-family lock, convergence-based collegial), pipeline timing/cost table, failure-modes-and-guards matrix | `ARCHITECTURE.md` (new) |
| 16 | README documentation map — single source of truth linking all 8 docs | `README.md` |

### 4. **Bug fixes & developer experience**

| # | Change | Files |
|---|--------|-------|
| 1 | Fix typecheck error: missing `beforeEach` import in navbar test | `navbar.test.tsx` |
| 7 | Fix 3 unused-variable bugs surfaced by new ruff config: dead `result` assignment in batch promotion, unused `model` tuple-unpack in orchestrator, dead `empty_fam` in leaderboard test | `app/api/batch.py`, `services/paper_generation/orchestrator.py`, `tests/test_leaderboard.py` |
| 13 | **Atom 1.0 feed** at `/api/v1/papers/feed.atom` for academic subscribers (Zotero/Mendeley compatible) + 3 backend tests | `backend/app/api/papers.py`, `tests/test_papers_extended.py`, `frontend/src/app/layout.tsx`, `footer.tsx` |

---

## Persona Panel Summary

Three personas deployed in Phase 0; all returned actionable findings.

| Persona | Issues found | Issues addressed | Keep rate |
|---------|-------------:|-----------------:|----------:|
| Pedagogical Scientist (Maya Chen) | 18 | 11 | 100% |
| Engineering Process Auditor      | 15 | 8  | 100% |
| Returning Researcher (Dr. Patel) | 30+ friction/missing | 5 | 100% |

**Most productive:** Pedagogical Scientist — surfaced systematic terminology gaps that grep-based scanning would have missed.

**Critical Patel insight (deferred — out of /autodevelop scope):** "Scaffolding without papers." Empty database means researchers cannot evaluate output quality. Mitigation: improved empty states (iter 11) guide visitors to methodology + glossary + reliability + corrections, but the underlying issue requires the pipeline to actually run and produce papers.

**Patel "missing features" still open:** PDF download per paper, citation widget on paper cards (BibTeX/RIS), saved searches, methodology versioning, native expert reviewer accounts.

---

## Process Evolution

- **Backend ruff config** is now version-controlled and explicit (was relying on default rules). New PRs get the same lint baseline locally as in CI.
- **Pre-commit hooks** ready for `pre-commit install` — local verification before commit.
- **Makefile** unifies the per-stack scripts behind a single command set.
- **Documentation map** in README means contributors have one entry point that branches to the 7 specialized docs.
- **CI** now caches deps, captures coverage, runs E2E, and audits dependencies.

---

## Test Count Growth

| Stack    | Start | End | Delta |
| -------- | ----: | --: | ----- |
| Backend  |   288 | 291 | +3    |
| Frontend |   185 | 185 | —     |
| E2E      |    74 |  74 | —     |
| **Total**| **547** | **550** | **+3** |

Test growth this session was modest because the focus was process/docs and the existing test suite already gave high coverage of the runtime. The 3 added tests are real coverage gains for the new Atom feed.

---

## Remaining Gaps (next session priorities)

1. **Hierarchical failure taxonomy** (Pedagogical Sev 3, M-effort) — reorganize the 8 failure types into Data Origin / Logic / Fabrication / Format groups.
2. **About page family clarification** (Pedagogical Sev 2, S) — disambiguate "11 families = 11 different methods or venues."
3. **Reliability threshold context** (Pedagogical Sev 3, S) — add the "thresholds set quarterly per family" context.
4. **Correction types** (Pedagogical Sev 3, S) — define errata vs update vs retraction on `/corrections`.
5. **Leaderboard hero callout** (Pedagogical Sev 3, S) — promote the conservative-rating intuition out of the collapsible help.
6. **Paper detail QualitySummary reordering** (Pedagogical Sev 2, S) — order indicators by researcher relevance with brief legend.
7. **Patel: PDF download per paper card** (S backend route + S frontend UI) — citation friction is the #1 review-conversion blocker.
8. **Patel: BibTeX/RIS export buttons on paper cards** (S, exposes existing data).
9. **Patel: Methodology versioning** (M-L) — `/methodology/v3` style routes so papers cite the exact methodology revision they were produced under.
10. **Patel: Pipeline visual on homepage** (M) — animated walk-through of "how a paper flows through the system."

---

## Cross-Session Learnings

1. **Persona panels are higher-quality discovery than grep.** All three personas returned issues no scan strategy would have found — terminology gaps, contributor onboarding gaps, researcher-conversion blockers. Worth the 1-2 minute parallel investment every rotation.

2. **The "Returning Researcher" persona is uniquely valuable.** Expert auditors find code-level issues; target users find product-level dead-ends. Patel's "scaffolding without papers" insight is something no static analysis would have surfaced.

3. **Documentation work compounds.** Each new doc (README, CONTRIBUTING, ARCHITECTURE, TESTING, MIGRATIONS) reduces the cost of every future contribution. Write once, save N future PRs.

4. **Strict ruff with `# TODO: enable later` ignore-list is the right migration path.** Adopting all rules at once = 78 errors. Ignoring the legacy ones with a comment unblocks the codebase immediately and creates a visible backlog.

5. **Empty-state UX is part of the deliverable.** A page that's empty 95% of its first month is mostly that empty state. Spending iteration budget on empty-state CTAs (publications, leaderboard) directly serves the mission of researcher engagement.

6. **Atom feeds matter for academic subscribers.** Zotero, Mendeley, and most reference managers consume Atom natively. The system already had JSON Feed (developer-friendly) but no academic-friendly feed. One small backend addition unlocks researcher subscriptions.

---

## Files Created or Substantially Edited

**Created (new):**
- `README.md`, `CONTRIBUTING.md`, `ARCHITECTURE.md`, `TESTING.md`, `MIGRATIONS.md`
- `Makefile`, `.pre-commit-config.yaml`
- `frontend/src/app/glossary/page.tsx`

**Substantially edited:**
- `frontend/README.md` (full rewrite from boilerplate)
- `frontend/src/app/methodology/page.tsx` (5 terminology fixes + L1-L5 standardize + visual diagram + collegial/significance/significance verdict expansions)
- `frontend/src/app/page.tsx` (stat-card definitions)
- `frontend/src/app/publications/page.tsx`, `leaderboard/page.tsx` (empty states)
- `backend/pyproject.toml` (ruff config + pytest-cov dev dep)
- `backend/app/api/papers.py` (Atom feed + 2 unused-var fixes)
- `backend/tests/test_papers_extended.py`, `test_leaderboard.py`
- `.github/workflows/ci.yml` (concurrency, caching, coverage, E2E job, security audit)
- `frontend/src/components/layout/navbar.tsx`, `footer.tsx`
