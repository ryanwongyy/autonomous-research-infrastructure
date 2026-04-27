import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

// Mock AbortSignal.timeout if not available in jsdom
if (typeof AbortSignal.timeout !== "function") {
  AbortSignal.timeout = (ms: number) => {
    const controller = new AbortController();
    setTimeout(() => controller.abort(), ms);
    return controller.signal;
  };
}

// We need to mock fetch before importing the module
const mockFetch = vi.fn();
vi.stubGlobal("fetch", mockFetch);

// Dynamic import so the module picks up our mocked fetch
const {
  API_BASE,
  getFamilies,
  getSources,
  getLeaderboard,
  getStats,
  getPaper,
  getCategories,
  getMatches,
  getReliabilityOverview,
  getCohorts,
} = await import("@/lib/api");

function mockJsonResponse(data: unknown, status = 200) {
  return Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    statusText: status === 200 ? "OK" : "Not Found",
    json: () => Promise.resolve(data),
  });
}

describe("API module", () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  // ── API_BASE ────────────────────────────────────────────────────────

  it("uses localhost fallback for API_BASE when env is unset", () => {
    expect(API_BASE).toBe("http://localhost:8000/api/v1");
  });

  // ── apiFetch internals (tested via public wrappers) ─────────────────

  it("constructs correct URL for getFamilies", async () => {
    mockFetch.mockReturnValueOnce(
      mockJsonResponse({ families: [], total: 0 })
    );
    await getFamilies();
    expect(mockFetch).toHaveBeenCalledOnce();
    const [url] = mockFetch.mock.calls[0];
    expect(url).toBe(`${API_BASE}/families`);
  });

  it("throws on non-ok response", async () => {
    mockFetch.mockReturnValueOnce(mockJsonResponse({}, 404));
    await expect(getPaper("nonexistent")).rejects.toThrow("API error: 404");
  });

  it("throws on network failure", async () => {
    mockFetch.mockRejectedValueOnce(new TypeError("Failed to fetch"));
    await expect(getStats()).rejects.toThrow("Failed to fetch");
  });

  it("includes Content-Type header", async () => {
    mockFetch.mockReturnValueOnce(mockJsonResponse([]));
    await getCategories();
    const [, options] = mockFetch.mock.calls[0];
    expect(options.headers["Content-Type"]).toBe("application/json");
  });

  it("includes AbortSignal for timeout", async () => {
    mockFetch.mockReturnValueOnce(mockJsonResponse([]));
    await getCategories();
    const [, options] = mockFetch.mock.calls[0];
    expect(options.signal).toBeInstanceOf(AbortSignal);
  });

  // ── Individual API functions ────────────────────────────────────────

  it("getSources passes tier parameter", async () => {
    mockFetch.mockReturnValueOnce(
      mockJsonResponse({ sources: [], total: 0 })
    );
    await getSources("T1");
    const [url] = mockFetch.mock.calls[0];
    expect(url).toContain("?tier=T1");
  });

  it("getLeaderboard constructs query string with all params", async () => {
    mockFetch.mockReturnValueOnce(
      mockJsonResponse({ entries: [], total: 0, page: 1, per_page: 20 })
    );
    await getLeaderboard({
      family_id: "F1",
      page: 2,
      sort_by: "elo",
      sort_dir: "desc",
    });
    const [url] = mockFetch.mock.calls[0];
    expect(url).toContain("family_id=F1");
    expect(url).toContain("page=2");
    expect(url).toContain("sort_by=elo");
    expect(url).toContain("sort_dir=desc");
  });

  it("getMatches passes limit parameter", async () => {
    mockFetch.mockReturnValueOnce(mockJsonResponse({ matches: [] }));
    await getMatches(10);
    const [url] = mockFetch.mock.calls[0];
    expect(url).toContain("limit=10");
  });

  it("getReliabilityOverview calls correct endpoint", async () => {
    mockFetch.mockReturnValueOnce(mockJsonResponse({}));
    await getReliabilityOverview();
    const [url] = mockFetch.mock.calls[0];
    expect(url).toBe(`${API_BASE}/reliability/overview`);
  });

  it("getCohorts calls correct endpoint", async () => {
    mockFetch.mockReturnValueOnce(mockJsonResponse({ cohorts: [] }));
    await getCohorts();
    const [url] = mockFetch.mock.calls[0];
    expect(url).toBe(`${API_BASE}/cohorts`);
  });

  it("returns parsed JSON data", async () => {
    const payload = { families: [{ id: "F1", name: "Test" }], total: 1 };
    mockFetch.mockReturnValueOnce(mockJsonResponse(payload));
    const result = await getFamilies();
    expect(result).toEqual(payload);
  });
});
