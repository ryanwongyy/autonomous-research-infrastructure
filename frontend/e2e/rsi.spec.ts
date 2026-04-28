import { test, expect } from "@playwright/test";
import { mockAllApi } from "./helpers";
import { MOCK_PORT } from "./mock-server";

const MOCK_BASE = `http://127.0.0.1:${MOCK_PORT}`;

test.describe("RSI page", () => {
  test("renders Recursive Self-Improvement heading", async ({ page }) => {
    await mockAllApi(page);
    await page.goto("/rsi");
    await expect(
      page.getByRole("heading", { level: 1, name: "Recursive Self-Improvement" }),
    ).toBeVisible({ timeout: 10_000 });
  });

  test("shows empty state when no dashboard data", async ({ page }) => {
    // The page shows "No RSI data available" only when serverFetch throws
    // (dashboard is null). A successful response with empty data still renders
    // the content section. Override with 500 to trigger the error path.
    await mockAllApi(page);
    await fetch(`${MOCK_BASE}/__mock/set-routes`, {
      method: "POST",
      body: JSON.stringify({
        "/rsi/dashboard": { status: 500, body: { detail: "Not found" } },
      }),
    });
    await page.goto("/rsi");
    await expect(
      page.getByText("No RSI data available"),
    ).toBeVisible({ timeout: 10_000 });
  });

  test("displays tier summary cards", async ({ page }) => {
    await mockAllApi(page, {
      "/rsi/dashboard": {
        by_tier: { "1a": 3, "1b": 1, "2a": 0 },
        by_status: { active: 2, proposed: 1, rolled_back: 1 },
        recent_gates: [],
        total_experiments: 4,
      },
    });
    await page.goto("/rsi");
    await expect(page.getByText("Total Experiments")).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText("Tier Health")).toBeVisible();
    await expect(page.getByText("Role Prompts")).toBeVisible();
    await expect(page.getByText("Tier 1a")).toBeVisible();
  });

  test("displays gate log entries", async ({ page }) => {
    await mockAllApi(page, {
      "/rsi/dashboard": {
        by_tier: { "1a": 2 },
        by_status: { active: 1, promoted: 1 },
        recent_gates: [
          {
            id: 1,
            experiment_id: 101,
            gate_type: "quality",
            decision: "promote",
            decided_at: "2025-03-01T12:00:00Z",
            notes: "All metrics passed threshold.",
          },
        ],
        total_experiments: 2,
      },
    });
    await page.goto("/rsi");
    await expect(page.getByText("Recent Gate Decisions")).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText("promote").first()).toBeVisible();
    await expect(page.getByText("All metrics passed threshold.")).toBeVisible();
  });
});
