import type { Page } from "@playwright/test";
import { MOCK_PORT } from "./mock-server";

const MOCK_BASE = `http://127.0.0.1:${MOCK_PORT}`;

/**
 * Reset mock server to defaults, then apply any overrides.
 * Works for both server components (SSR fetch) and client components (browser fetch).
 *
 * Also installs page.route() interception as a fallback for any client-side
 * requests that go directly to the API (non-server-component pages).
 */
export async function mockAllApi(page: Page, overrides: Record<string, unknown> = {}) {
  // Reset mock server to defaults
  await fetch(`${MOCK_BASE}/__mock/reset`, { method: "POST" });

  // Apply overrides to mock server
  if (Object.keys(overrides).length > 0) {
    const routeMap: Record<string, { status: number; body: unknown }> = {};
    for (const [path, data] of Object.entries(overrides)) {
      routeMap[path] = { status: 200, body: data };
    }
    await fetch(`${MOCK_BASE}/__mock/set-routes`, {
      method: "POST",
      body: JSON.stringify(routeMap),
    });
  }

  // Also set up page.route() for client-side fetches (client components)
  await page.route("**/api/v1/**", async (route) => {
    const url = route.request().url();
    const path = new URL(url).pathname.replace("/api/v1", "");

    // Forward to mock server
    try {
      const resp = await fetch(`${MOCK_BASE}/api/v1${path}`);
      const body = await resp.json();
      return route.fulfill({ status: resp.status, json: body });
    } catch {
      return route.fulfill({ json: {} });
    }
  });
}

/**
 * Configure mock server for paper detail page tests.
 * Sets up the 10 parallel fetches that PaperPage makes via Promise.allSettled.
 */
export async function mockPaperDetailApi(
  page: Page,
  paperId: string,
  overrides: Record<string, unknown> = {},
) {
  const defaultPaper = {
    id: paperId,
    title: "Mock Paper Title",
    abstract: "This is a mock abstract for testing purposes.",
    source: "ape",
    category: "ai_governance",
    country: "US",
    method: "qualitative",
    status: "public",
    review_status: "peer_reviewed",
    release_status: "public",
    funnel_stage: "published",
    mu: 25.0,
    sigma: 4.2,
    conservative_rating: 12.4,
    elo: 1650,
    matches_played: 8,
    rank: 3,
    created_at: "2025-01-15T00:00:00Z",
  };

  const defaults: Record<string, { status: number; body: unknown }> = {
    [`/papers/${paperId}`]: { status: 200, body: defaultPaper },
    [`/papers/${paperId}/reviews`]: { status: 200, body: [] },
    [`/papers/${paperId}/collegial-session`]: { status: 404, body: { detail: "Not found" } },
    [`/papers/${paperId}/significance-memo`]: { status: 404, body: { detail: "Not found" } },
    [`/papers/${paperId}/expert-reviews`]: { status: 200, body: [] },
    [`/papers/${paperId}/outcomes`]: { status: 200, body: [] },
    [`/papers/${paperId}/novelty-check`]: { status: 404, body: { detail: "Not found" } },
    [`/papers/${paperId}/autonomy-card`]: { status: 404, body: { detail: "Not found" } },
    [`/papers/${paperId}/corrections`]: { status: 200, body: [] },
    ["/collegial/profiles"]: { status: 200, body: { profiles: [] } },
  };

  // Reset and apply defaults
  await fetch(`${MOCK_BASE}/__mock/reset`, { method: "POST" });
  await fetch(`${MOCK_BASE}/__mock/set-routes`, {
    method: "POST",
    body: JSON.stringify(defaults),
  });

  // Apply overrides
  if (Object.keys(overrides).length > 0) {
    const routeMap: Record<string, { status: number; body: unknown }> = {};
    for (const [path, data] of Object.entries(overrides)) {
      if (typeof data === "object" && data !== null && "status" in data && "json" in data && typeof (data as Record<string, unknown>).status === "number") {
        const d = data as { status: number; json: unknown };
        routeMap[path] = { status: d.status, body: d.json };
      } else {
        routeMap[path] = { status: 200, body: data };
      }
    }
    await fetch(`${MOCK_BASE}/__mock/set-routes`, {
      method: "POST",
      body: JSON.stringify(routeMap),
    });
  }

  // Also set up page.route() for client-side fetches
  await page.route("**/api/v1/**", async (route) => {
    const url = route.request().url();
    const path = new URL(url).pathname.replace("/api/v1", "");

    try {
      const resp = await fetch(`${MOCK_BASE}/api/v1${path}`);
      const body = await resp.json();
      return route.fulfill({ status: resp.status, json: body });
    } catch {
      return route.fulfill({ json: {} });
    }
  });
}
