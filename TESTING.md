# Testing Guide

The project has three test surfaces. All three must pass before a PR can merge.

| Surface       | Tool       | Command                                  | Approx. count | Speed   |
| ------------- | ---------- | ---------------------------------------- | ------------- | ------- |
| Backend unit + integration | pytest     | `cd backend && pytest`                   | 288+          | ~25 s   |
| Frontend unit + component  | vitest     | `cd frontend && npm test`                | 185+          | ~15 s   |
| End-to-end browser         | Playwright | `cd frontend && npm run test:e2e`        | 74+           | ~60 s   |

---

## Backend (pytest)

### Conventions

- **Async by default.** `pytest-asyncio` is configured in `auto` mode
  (`pyproject.toml`). Test functions can be `async def` without decorators.
- **In-memory SQLite.** All tests run against a fresh in-memory database
  via `conftest.py`. The fixture uses `StaticPool` + `check_same_thread=False`
  so every connection sees the same DB.
- **Models import order.** `Base.metadata.create_all` only sees models that
  have been imported. `conftest.py` imports the entire `app.models` package
  before creating tables — keep that import to avoid empty schemas.
- **DI overrides.** Use `app.dependency_overrides[get_db] = …` to inject the
  test session. Some routers (e.g. `app.api.batch`) bypass DI and use the
  `async_session` global directly — those tests monkeypatch the global.

### File layout

```
backend/tests/
  conftest.py              # shared fixtures (db_session, client, sample_paper)
  test_<endpoint>.py       # one file per API surface
  test_<service>.py        # one file per service module
  helpers/                 # factories for paper/review/family fixtures
```

### Adding a backend test

1. Create `tests/test_my_feature.py`.
2. Import `from app.main import app` and use the `client` fixture
   (returns `httpx.AsyncClient` bound to ASGI transport — no real network).
3. Use the `db_session` fixture for direct ORM access.
4. Run `pytest tests/test_my_feature.py -v` to confirm.

---

## Frontend (vitest)

### Conventions

- **JSDOM environment.** Configured in `vitest.config.ts`. Don't use
  Node-only APIs; use the `globalThis` form when in doubt.
- **Test colocated.** Component tests live in `__tests__/` next to the source:
  `src/components/paper/quality-summary.tsx`
  → `src/components/paper/__tests__/quality-summary.test.tsx`.
- **Always import vitest hooks.** `describe`, `it`, `expect`, `vi`,
  `beforeEach` — even if globals "work" at runtime, the tsc gate requires
  explicit imports.
- **Mock `next/navigation` and `next/link`** when testing components that
  use them — see `navbar.test.tsx` for the canonical pattern.
- **Avoid testing implementation.** Prefer `getByRole` / `getByText` over
  `getByTestId`. If a component is hard to query by role, fix the component.

### Adding a component test

```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MyComponent } from "../my-component";

describe("MyComponent", () => {
  it("renders the heading", () => {
    render(<MyComponent title="Hello" />);
    expect(screen.getByRole("heading", { name: "Hello" })).toBeInTheDocument();
  });
});
```

---

## End-to-end (Playwright)

### Conventions

- **SSR-compatible mocking.** `page.route()` only intercepts browser-side
  fetches. Next.js Server Components fetch on the server, so the project
  runs a **real HTTP mock server on port 8000** (`e2e/mock-server.ts`).
  The Playwright `webServer` config starts it before tests.
- **Helpers for fixtures.** `e2e/helpers.ts` exports factory functions
  (`makePaper()`, `makeReview()`, `mockApi()`) — use these instead of
  inline JSON.
- **Wait for hydration.** Use `await page.waitForLoadState("domcontentloaded")`
  before asserting on interactive elements.
- **Don't hard-code IDs.** Use semantic locators (`page.getByRole`,
  `page.getByLabel`) for accessibility coverage.

### Adding an E2E test

1. Create `e2e/my-flow.spec.ts`.
2. Import `mockApi`, `makePaper` from `./helpers`.
3. Set up route mocks before navigation:
   ```ts
   await mockApi(page, { paper: makePaper({ id: "test-1" }) });
   await page.goto("/papers/test-1");
   ```
4. Run `npx playwright test e2e/my-flow.spec.ts --headed` to debug visually.

---

## Running everything

From the repository root (after a `Makefile` is added):

```bash
make test         # runs all three suites in parallel
make test:backend # backend only
make test:fe      # frontend only
make test:e2e     # E2E only
```

Or directly:

```bash
(cd backend && pytest -q) && (cd frontend && npm test -- --reporter=basic) && \
  (cd frontend && npm run test:e2e)
```

---

## Coverage

Coverage is not yet enforced in CI. To run locally:

- Backend: `pytest --cov=app --cov-report=term-missing`
- Frontend: `vitest run --coverage`

Aim for **70%+ line coverage** on new modules. Modules below 50% should
have a coverage TODO in their top-level docstring.

---

## Common failures

| Symptom                                     | Likely cause                                                                |
| ------------------------------------------- | --------------------------------------------------------------------------- |
| `sqlite3.OperationalError: no such table`   | `conftest.py` imports missing — see "Models import order" above.            |
| `TypeError: Cannot read properties of null` | Component depends on a Next.js context that wasn't mocked.                  |
| Playwright timeout in `webServer.start()`   | Port 8000 already in use — kill stray `node` processes.                     |
| `beforeEach` not found (tsc error)          | Missing import from "vitest". The runtime tolerates this; tsc does not.    |

---

## Where to add a failing test before a fix

When fixing a bug, write the failing test first, in the same surface as the
bug:

- Backend bug → new test in `backend/tests/test_<area>.py`
- Component bug → new test next to the component
- Cross-stack bug → new spec in `frontend/e2e/`

Commit the failing test first (red), then the fix (green). The diff
should show both clearly.
