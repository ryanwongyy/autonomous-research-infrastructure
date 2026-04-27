# Frontend — Autonomous Research Infrastructure

Next.js 16 + React 19 frontend for the autonomous AI governance research
platform. Communicates outputs and indicators effectively, and encourages
human researchers to review AI-generated papers.

> ⚠ **This is NOT the Next.js you know.** Next.js 16 has breaking changes
> from 14/15. See [`AGENTS.md`](./AGENTS.md) before writing code.

---

## Quick start

```bash
npm ci
npm run dev          # http://localhost:3000
```

By default the frontend talks to a backend at `http://localhost:8001`. To
override:

```bash
NEXT_PUBLIC_API_URL=https://api.example.com npm run dev
```

---

## Scripts

| Script                | What it does                                                  |
| --------------------- | ------------------------------------------------------------- |
| `npm run dev`         | Dev server with HMR                                           |
| `npm run build`       | Production build (must pass before merge)                     |
| `npm run start`       | Run the production build locally                              |
| `npm run lint`        | ESLint                                                        |
| `npm test`            | Vitest (unit + component)                                     |
| `npm run test:watch`  | Vitest in watch mode                                          |
| `npm run test:e2e`    | Playwright E2E (spins up real backend mock on port 8000)      |

See [`../TESTING.md`](../TESTING.md) for test conventions.

---

## Layout

```
src/
  app/                  Next.js App Router pages
    page.tsx              Homepage — hero + latest papers + system pulse
    publications/         Paper listing
    papers/[id]/          Paper detail + reviews + ratings + corrections
    methodology/          Full pipeline documentation
    leaderboard/          Family-local TrueSkill rankings
    reliability/          5-metric reliability dashboard
    corrections/          Self-correction transparency
    families/             Per-family detail
    about/                Project mission + governance
    sources/              Source-tier registry
    failures/             Failure taxonomy explorer
    outcomes/             Submission outcomes dashboard
    rsi/                  Recursive self-improvement experiments
  components/
    paper/                Paper-specific components (review pipeline, citations, …)
    layout/               Navbar, Footer, Page wrapper
    charts/               Recharts wrappers
    ui/                   shadcn/ui primitives
  lib/                  api client, utilities, types
e2e/                    Playwright specs + mock backend
```

---

## Design system

- **Tailwind v4** with `@tailwindcss/postcss`.
- **shadcn/ui** components colocated under `src/components/ui/`.
- **Dark mode** via `class` strategy. Use semantic tokens
  (`bg-background`, `text-muted-foreground`, `border-border`) not raw colors.
- **Color-coded scoring** convention used across reliability + paper detail:
  - Emerald (≥ 70%) — pass / good
  - Amber (≥ 50%) — warning / borderline
  - Red (< 50%) — fail / poor

---

## Adding a page

1. Create `src/app/<route>/page.tsx`.
2. If the page fetches data, use `serverFetch` from `lib/api.ts` (server
   components) or `clientFetch` (client components).
3. Add it to the navbar (`src/components/layout/navbar.tsx`) — primary nav
   for trust-building pages, System dropdown for internal pages.
4. Add an E2E smoke test in `e2e/<route>.spec.ts`.
5. Add to `app/sitemap.ts` if it should be indexed.

---

## Adding a paper component

1. Create `src/components/paper/<name>.tsx`. Keep it focused — extract
   reusable pieces aggressively.
2. Add a vitest test at `src/components/paper/__tests__/<name>.test.tsx`.
3. Always import vitest hooks explicitly (`describe`, `it`, `expect`,
   `beforeEach`) — the tsc gate requires this even though runtime allows
   globals.

---

## Deployment

- Hosted on **Vercel**. `main` deploys to production; PR previews are auto-generated.
- `NEXT_PUBLIC_API_URL` must point to the backend.
- Sitemap and robots.txt are auto-generated from the App Router.

---

## See also

- [`../README.md`](../README.md) — full-stack overview
- [`../TESTING.md`](../TESTING.md) — test conventions across all surfaces
- [`AGENTS.md`](./AGENTS.md) — Next.js 16 breaking-change notes
