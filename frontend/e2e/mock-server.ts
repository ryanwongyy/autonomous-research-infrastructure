import http from "node:http";
import type { AddressInfo } from "node:net";

/**
 * Mock API server for E2E tests.
 *
 * Next.js server components call `serverFetch()` which hits
 * http://localhost:8000/api/v1/... from the Node process.
 * Playwright's `page.route()` only intercepts browser requests,
 * so we run a real HTTP server on port 8000 to serve mock data.
 *
 * Route configuration from tests:
 *   POST /__mock/set-routes  — body is JSON map of { path: { status, body } }
 *   POST /__mock/reset       — clear all custom routes, restore defaults
 *
 * All /api/v1/* requests are matched against the configured routes.
 */

export const MOCK_PORT = 8000;

let routes = new Map<string, { status: number; body: unknown }>();

const DEFAULT_ROUTES: Record<string, { status: number; body: unknown }> = {
  "/families": { status: 200, body: { families: [], total: 0 } },
  "/sources": { status: 200, body: { sources: [], total: 0 } },
  "/leaderboard": { status: 200, body: { entries: [], total: 0, page: 1, per_page: 20 } },
  "/throughput/funnel": { status: 200, body: { stages: [] } },
  "/throughput/conversion-rates": { status: 200, body: { conversions: [] } },
  "/throughput/bottlenecks": { status: 200, body: { bottlenecks: [] } },
  "/throughput/projections": { status: 200, body: { monthly_target: 0, on_track: true } },
  "/throughput/daily-targets": { status: 200, body: { targets: [] } },
  "/throughput/work-queue": { status: 200, body: { items: [] } },
  "/stats/rating-distribution": { status: 200, body: { buckets: [] } },
  "/stats/trueskill-progression": { status: 200, body: [] },
  "/stats": { status: 200, body: { total_papers: 0, total_families: 0, total_matches: 0 } },
  "/categories": { status: 200, body: [] },
  "/matches": { status: 200, body: { matches: [] } },
  "/tournament/runs": { status: 200, body: { runs: [] } },
  "/release/status": { status: 200, body: { papers_by_status: {} } },
  "/papers/public": { status: 200, body: [] },
  "/papers/feed.json": { status: 200, body: { title: "ARI", items: [] } },
  "/reliability/overview": { status: 200, body: { families: [] } },
  "/cohorts": { status: 200, body: { cohorts: [] } },
  "/outcomes/dashboard": { status: 200, body: { overall: { total: 0 }, per_family: [] } },
  "/corrections/dashboard": { status: 200, body: { families: [] } },
  "/failures/dashboard": { status: 200, body: { distribution: { total: 0, by_type: {}, by_severity: {}, by_stage: {} }, trends: [] } },
  "/rsi/dashboard": { status: 200, body: { tiers: [] } },
  "/rsi/experiments": { status: 200, body: [] },
  "/collegial/profiles": { status: 200, body: { profiles: [] } },
  "/config/domains": { status: 200, body: [] },
  "/config/models": { status: 200, body: { providers: {} } },
  "/health": { status: 200, body: { status: "ok" } },
};

function resetRoutes() {
  routes = new Map(Object.entries(DEFAULT_ROUTES));
}

function matchRoute(pathname: string): { status: number; body: unknown } | undefined {
  if (routes.has(pathname)) return routes.get(pathname);
  // Prefix match — longest key first
  const sorted = [...routes.keys()].sort((a, b) => b.length - a.length);
  for (const pattern of sorted) {
    if (pathname.startsWith(pattern)) return routes.get(pattern);
  }
  return undefined;
}

function readBody(req: http.IncomingMessage): Promise<string> {
  return new Promise((resolve) => {
    let data = "";
    req.on("data", (chunk: string) => { data += chunk; });
    req.on("end", () => resolve(data));
  });
}

let server: http.Server | null = null;

export function startMockServer(): Promise<number> {
  return new Promise((resolve, reject) => {
    resetRoutes();

    server = http.createServer(async (req, res) => {
      const url = new URL(req.url ?? "/", `http://localhost:${MOCK_PORT}`);
      const headers: Record<string, string> = {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, PUT, PATCH, DELETE, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, Authorization",
      };

      // CORS preflight
      if (req.method === "OPTIONS") {
        res.writeHead(204, headers);
        return res.end();
      }

      // Control endpoint: set routes
      if (url.pathname === "/__mock/set-routes" && req.method === "POST") {
        const body = await readBody(req);
        const routeMap = JSON.parse(body) as Record<string, { status: number; body: unknown }>;
        for (const [path, config] of Object.entries(routeMap)) {
          routes.set(path, config);
        }
        res.writeHead(200, headers);
        return res.end(JSON.stringify({ ok: true }));
      }

      // Control endpoint: reset
      if (url.pathname === "/__mock/reset" && req.method === "POST") {
        resetRoutes();
        res.writeHead(200, headers);
        return res.end(JSON.stringify({ ok: true }));
      }

      // API route handling — strip /api/v1 prefix
      const apiPath = url.pathname.replace("/api/v1", "");
      const match = matchRoute(apiPath);

      if (match && typeof match.status === "number") {
        res.writeHead(match.status, headers);
        return res.end(JSON.stringify(match.body));
      }

      // Fallback
      res.writeHead(200, headers);
      res.end(JSON.stringify(match?.body ?? {}));
    });

    server.on("error", reject);
    server.listen(MOCK_PORT, "127.0.0.1", () => {
      const addr = server!.address() as AddressInfo;
      resolve(addr.port);
    });
  });
}

export function stopMockServer(): Promise<void> {
  return new Promise((resolve) => {
    if (server) {
      server.close(() => resolve());
      server = null;
    } else {
      resolve();
    }
  });
}
