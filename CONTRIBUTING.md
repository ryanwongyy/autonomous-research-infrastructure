# Contributing

Thanks for considering a contribution. This project's mission is twofold:

1. **Communicate research outputs and indicators effectively.**
2. **Encourage human researchers to review AI-generated papers.**

Every change should serve at least one of those goals. If a PR makes the
system easier to *understand*, easier to *trust*, or easier to *audit*, it
fits.

---

## Before you start

- Read [`README.md`](./README.md) for the architecture overview.
- Read [`TESTING.md`](./TESTING.md) for test conventions across all surfaces.
- Read [`MIGRATIONS.md`](./MIGRATIONS.md) if your change touches the DB.
- Read [`frontend/AGENTS.md`](./frontend/AGENTS.md) before writing any
  Next.js code — Next.js 16 has breaking changes you may not know.
- Skim the [`/methodology`](./frontend/src/app/methodology/page.tsx) page
  to understand what the system *does*.

---

## Approaches we follow

These are *approaches*, not rigid rules. The point is to keep the project
auditable and trustworthy at scale.

### 1. Transparency by default

If a piece of internal state can reasonably be exposed, expose it. Every
review verdict, rating distribution, drift score, and correction is a
public surface. The default answer to "should we publish X?" is **yes**.

If something can't be public — usually because it's PII, an API key, or
embargo material — say so explicitly in code comments and docs.

### 2. Provenance over polish

A rougher feature with full provenance trail is better than a polished
feature whose data origin is unclear. If a number appears on a page, the
reader should be one click from "where does this come from?".

### 3. Mechanical verification

We don't merge changes that aren't covered by an executable check —
test, type, build, or lint. Subjective "looks good to me" is not a gate.

### 4. Atomic, reversible changes

One concern per PR. If a PR touches 5 unrelated things, it's actually 5
PRs. Smaller, atomic changes are easier to review, easier to revert, and
easier to attribute when something breaks.

### 5. Removal is a feature

When a page, component, or endpoint adds confusion without value, deleting
it is a net improvement. We celebrate `git diff --stat` showing more
deletions than additions.

### 6. Talk to the reader

The system is read by domain experts who don't know our jargon. Every
new term gets defined the first time it appears. The
[Glossary](./frontend/src/app/glossary/page.tsx) is the canonical place.

---

## Workflow

1. **Pick an issue.** Existing issues live in GitHub. If you have a new
   idea, open one before coding so the design can be discussed.

2. **Branch from `main`.** Use a short kebab-case name: `add-glossary`,
   `fix-leaderboard-empty`. Avoid the `feat/`, `fix/` prefixes — the
   commit message says enough.

3. **Make atomic commits.** Each commit should leave the tree in a
   working state (tests + types + build all pass). Commit message style:

   ```
   short imperative summary in lowercase

   Optional body explaining the why, not the what. Wrap at 72 chars.
   References issues by number where relevant.
   ```

4. **Run the verification gate.** Before pushing:

   ```bash
   make verify   # lint + typecheck + test (excludes e2e + build)
   ```

   Or for the full CI gate:

   ```bash
   make ci       # everything
   ```

5. **Open a PR.** Title in the same style as commit messages. Body
   should answer:
   - What does this change?
   - Why does this serve the mission?
   - What did you test?
   - Any follow-up work this enables or depends on?

6. **Review.** Expect feedback. The reviewer's job is to keep the system
   coherent — not to gate-keep. Push back if you disagree, and explain.

7. **Merge.** Squash-merge by default. The PR title becomes the commit
   message on `main`.

---

## Conventions

### Naming

- **Files:** kebab-case for components and pages (`paper-card.tsx`),
  snake_case for Python modules (`review_pipeline.py`).
- **Functions:** `camelCase` in TypeScript, `snake_case` in Python.
- **Types/Classes:** `PascalCase` in both languages.
- **API routes:** `/papers/{id}/reviews` not `/getPaperReviews`.

### Imports

- Backend: ruff-isort handles ordering; let it.
- Frontend: external before internal, internal grouped by depth
  (`@/lib/...` before `@/components/...` before `./local`).
- **Always import vitest hooks explicitly** (`describe`, `it`, `expect`,
  `beforeEach`). The runtime tolerates implicit globals; tsc does not.

### Components

- Server Components by default. Add `"use client"` only when you need
  state, effects, or browser APIs.
- Extract a component when the same JSX appears more than twice. Put it
  next to the consumer until it has a third caller, then move it to
  `components/`.
- Test colocated: `__tests__/<component>.test.tsx` next to the source.

### Pages

- Add to `navbar.tsx` (primary nav for trust pages, system dropdown for
  internal pages).
- Add an E2E smoke test in `frontend/e2e/`.
- Add to `app/sitemap.ts` if it should be indexed.

---

## Adding a methodology change

When you change the *research pipeline itself* (a new role, a new review
layer, a new gate):

1. Update the SQLAlchemy model and write an Alembic migration.
2. Update the methodology page text — every researcher reads this.
3. Update the glossary if you introduced a new term.
4. Update the autonomy card or per-paper page to surface the new field.
5. Add backend + E2E tests covering the new pipeline behaviour.
6. Note the change in the PR body's "What this enables" section.

---

## Adding a researcher-facing page

Two questions to answer before you start:

- **Does this build trust?** (e.g. corrections, reliability — yes; family
  detail — also yes; internal admin — probably belongs in System dropdown.)
- **What's the empty state?** Most pages will be empty for visitors who
  arrive before the pipeline has produced public papers. The empty state
  is part of the deliverable, not an afterthought. See
  `publications/page.tsx` for the canonical pattern: explain the funnel
  and link to methodology + glossary + reliability + corrections.

---

## What we *don't* want

- **PRs that add a dependency without strong justification.** Each new
  package is a security and maintenance liability. Ask in an issue first.
- **Mocking what should be tested.** If you find yourself mocking your way
  out of a real integration, that's usually a sign the design is wrong.
- **Renaming for taste.** If existing names follow the conventions above,
  leave them.
- **Comments that describe *what* the code does.** The code already does
  that. Comments should explain *why* — the surprising context, the
  alternative considered and rejected, the bug being avoided.

---

## Code of conduct

Be specific. Be kind. Disagree on the substance, never on the person.

When reviewing, ask yourself: *would this comment be welcome at 11pm on
a Friday?* If not, rewrite it.

---

## Getting unstuck

- Architecture questions: open a discussion, link the affected files.
- Test infrastructure: see `TESTING.md`, then ping in PR.
- Migration mishap: see `MIGRATIONS.md`, then ping before touching prod.
- Anything else: open an issue tagged `question`.
