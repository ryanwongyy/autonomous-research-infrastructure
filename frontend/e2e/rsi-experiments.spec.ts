import { test, expect } from "@playwright/test";
import { mockAllApi } from "./helpers";

test.describe("RSI Experiments page", () => {
  test("renders RSI Experiments heading", async ({ page }) => {
    await mockAllApi(page);
    await page.goto("/rsi/experiments");
    await expect(
      page.getByRole("heading", { level: 1, name: "RSI Experiments" }),
    ).toBeVisible({ timeout: 10_000 });
  });

  test("shows empty state when no experiments", async ({ page }) => {
    await mockAllApi(page, {
      "/rsi/experiments": [],
    });
    await page.goto("/rsi/experiments");
    await expect(
      page.getByText("No experiments found"),
    ).toBeVisible({ timeout: 10_000 });
  });

  test("displays experiment table with status badges", async ({ page }) => {
    await mockAllApi(page, {
      "/rsi/experiments": [
        {
          id: 1,
          tier: "1a",
          name: "Prompt Tuning v2",
          status: "active",
          cohort_id: null,
          family_id: "FAM1",
          created_by: "system",
          proposed_at: "2025-02-01",
          activated_at: "2025-02-05",
          rolled_back_at: null,
          config_snapshot: null,
          result_summary: null,
        },
        {
          id: 2,
          tier: "2b",
          name: "Drift Threshold Experiment",
          status: "rolled_back",
          cohort_id: null,
          family_id: null,
          created_by: "system",
          proposed_at: "2025-01-15",
          activated_at: "2025-01-20",
          rolled_back_at: "2025-01-25",
          config_snapshot: null,
          result_summary: { improvement: -0.02 },
        },
      ],
    });
    await page.goto("/rsi/experiments");
    await expect(page.getByText("Prompt Tuning v2")).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText("Drift Threshold Experiment")).toBeVisible();
    await expect(page.getByText("active").first()).toBeVisible();
    await expect(page.getByText("rolled back").first()).toBeVisible();
  });
});
