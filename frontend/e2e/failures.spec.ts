import { test, expect } from "@playwright/test";
import { mockAllApi } from "./helpers";
import { MOCK_PORT } from "./mock-server";

const MOCK_BASE = `http://127.0.0.1:${MOCK_PORT}`;

test.describe("Failures page", () => {
  test("renders Failure Taxonomy heading", async ({ page }) => {
    await mockAllApi(page);
    await page.goto("/failures");
    await expect(
      page.getByRole("heading", { level: 1, name: "Failure Taxonomy" }),
    ).toBeVisible({ timeout: 10_000 });
  });

  test("shows empty state when no failures recorded", async ({ page }) => {
    await mockAllApi(page, {
      "/failures/dashboard": { distribution: { total: 0, by_type: {}, by_severity: {}, by_stage: {} }, trends: [] },
    });
    await page.goto("/failures");
    await expect(
      page.getByText("No failures recorded yet."),
    ).toBeVisible({ timeout: 10_000 });
  });

  test("displays failure distribution data", async ({ page }) => {
    await mockAllApi(page, {
      "/failures/dashboard": {
        distribution: {
          total: 42,
          by_type: { hallucination: 15, logic_error: 12, data_error: 10, other: 5 },
          by_severity: { critical: 5, high: 12, medium: 20, low: 5 },
          by_stage: { generation: 18, screening: 14, review: 10 },
        },
        trends: [
          { date: "2025-03-01", total: 7 },
          { date: "2025-03-08", total: 5 },
        ],
      },
    });
    await page.goto("/failures");
    await expect(page.getByText("Total Failures")).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText("42")).toBeVisible();
    await expect(page.getByText("Hallucination")).toBeVisible();
    await expect(page.getByText("By Failure Type")).toBeVisible();
    await expect(page.getByText("By Detection Stage")).toBeVisible();
  });

  test("shows API error state", async ({ page }) => {
    // Configure mock server to return 500 for all routes
    await fetch(`${MOCK_BASE}/__mock/reset`, { method: "POST" });
    await fetch(`${MOCK_BASE}/__mock/set-routes`, {
      method: "POST",
      body: JSON.stringify({
        "/failures/dashboard": { status: 500, body: { detail: "Server error" } },
      }),
    });
    // Also intercept client-side requests
    await page.route("**/api/v1/**", (route) =>
      route.fulfill({ status: 500, json: { detail: "Server error" } }),
    );
    await page.goto("/failures");
    await expect(
      page.getByText("Unable to connect to the API. Failure data may be unavailable."),
    ).toBeVisible({ timeout: 10_000 });
  });
});
