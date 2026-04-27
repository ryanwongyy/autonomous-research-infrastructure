import { test, expect } from "@playwright/test";
import { mockAllApi } from "./helpers";
import { MOCK_PORT } from "./mock-server";

const MOCK_BASE = `http://127.0.0.1:${MOCK_PORT}`;

test.describe("Outcomes page", () => {
  test("renders Submission Outcomes heading", async ({ page }) => {
    await mockAllApi(page);
    await page.goto("/outcomes");
    await expect(
      page.getByRole("heading", { level: 1, name: "Submission Outcomes" }),
    ).toBeVisible({ timeout: 10_000 });
  });

  test("shows empty state when no data", async ({ page }) => {
    // The page shows different messages depending on how dashboard is null:
    // - API error (500) => "Unable to connect to the API. Please try again later."
    // - Null dashboard without error => "No submission outcome data available yet."
    // We test the API error path since that's the realistic way dashboard stays null.
    await mockAllApi(page);
    await fetch(`${MOCK_BASE}/__mock/set-routes`, {
      method: "POST",
      body: JSON.stringify({
        "/outcomes/dashboard": { status: 500, body: { detail: "Server error" } },
      }),
    });
    await page.goto("/outcomes");
    await expect(
      page.getByText("Unable to connect to the API. Please try again later."),
    ).toBeVisible({ timeout: 10_000 });
  });

  test("displays overall stat cards", async ({ page }) => {
    await mockAllApi(page, {
      "/outcomes/dashboard": {
        overall: {
          total: 50,
          accepted: 20,
          rejected: 15,
          desk_reject: 5,
          r_and_r: 4,
          pending: 6,
          acceptance_rate: 0.4,
        },
        per_family: [],
      },
    });
    await page.goto("/outcomes");
    await expect(page.getByText("Total Submitted")).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText("Accepted").first()).toBeVisible();
    await expect(page.getByText("Rejected").first()).toBeVisible();
    await expect(page.getByText("Desk Reject")).toBeVisible();
    await expect(page.getByText("Pending")).toBeVisible();
    await expect(page.getByText("40.0%")).toBeVisible();
  });

  test("displays per-family breakdown table", async ({ page }) => {
    await mockAllApi(page, {
      "/outcomes/dashboard": {
        overall: {
          total: 30,
          accepted: 12,
          rejected: 10,
          desk_reject: 3,
          r_and_r: 2,
          pending: 3,
          acceptance_rate: 0.4,
        },
        per_family: [
          {
            family_id: "FAM1",
            short_name: "Alpha",
            total: 18,
            accepted: 8,
            rejected: 6,
            acceptance_rate: 0.444,
          },
          {
            family_id: "FAM2",
            short_name: "Beta",
            total: 12,
            accepted: 4,
            rejected: 4,
            acceptance_rate: 0.333,
          },
        ],
      },
    });
    await page.goto("/outcomes");
    await expect(page.getByText("By Paper Family")).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText("Alpha")).toBeVisible();
    await expect(page.getByText("Beta")).toBeVisible();
    await expect(page.getByText("Acceptance Rate").first()).toBeVisible();
  });
});
