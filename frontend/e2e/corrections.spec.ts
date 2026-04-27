import { test, expect } from "@playwright/test";
import { mockAllApi } from "./helpers";
import { MOCK_PORT } from "./mock-server";

const MOCK_BASE = `http://127.0.0.1:${MOCK_PORT}`;

test.describe("Corrections page", () => {
  test("renders Corrections & Errata heading", async ({ page }) => {
    await mockAllApi(page, {
      "/corrections/dashboard": {
        families: [],
      },
    });
    await page.goto("/corrections");
    await expect(
      page.getByRole("heading", { level: 1, name: /Corrections/i }),
    ).toBeVisible({ timeout: 10_000 });
  });

  test("shows error state when API fails", async ({ page }) => {
    // Configure mock server to return 500
    await fetch(`${MOCK_BASE}/__mock/reset`, { method: "POST" });
    await fetch(`${MOCK_BASE}/__mock/set-routes`, {
      method: "POST",
      body: JSON.stringify({
        "/corrections/dashboard": { status: 500, body: { detail: "Server error" } },
      }),
    });
    await page.route("**/api/v1/**", (route) =>
      route.fulfill({ status: 500, json: { detail: "Server error" } }),
    );
    await page.goto("/corrections");
    await expect(
      page.getByText("Unable to connect to the API. Please try again later."),
    ).toBeVisible({ timeout: 10_000 });
  });

  test("displays family table with correction rates", async ({ page }) => {
    await mockAllApi(page, {
      "/corrections/dashboard": {
        families: [
          {
            family_id: "FAM1",
            short_name: "Alpha",
            total_public_papers: 20,
            total_corrections: 3,
            correction_rate: 0.15,
          },
          {
            family_id: "FAM2",
            short_name: "Beta",
            total_public_papers: 15,
            total_corrections: 0,
            correction_rate: 0,
          },
        ],
      },
    });
    await page.goto("/corrections");
    await expect(page.getByText("Alpha")).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText("Beta")).toBeVisible();
    await expect(page.getByText("By Paper Family")).toBeVisible();
    await expect(page.getByText("Public Papers").first()).toBeVisible();
    await expect(page.getByText("15.0%")).toBeVisible();
  });

  test("shows transparency notice text", async ({ page }) => {
    await mockAllApi(page, {
      "/corrections/dashboard": {
        families: [
          {
            family_id: "FAM1",
            short_name: "Alpha",
            total_public_papers: 10,
            total_corrections: 1,
            correction_rate: 0.1,
          },
        ],
      },
    });
    await page.goto("/corrections");
    await expect(
      page.getByText("Why we publish corrections:"),
    ).toBeVisible({ timeout: 10_000 });
    await expect(
      page.getByText(/Corrections are a feature, not a bug/),
    ).toBeVisible();
  });
});
