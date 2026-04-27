import { test, expect } from "@playwright/test";
import { mockAllApi } from "./helpers";

test.describe("Reliability page", () => {
  test("renders Reliability Dashboard heading", async ({ page }) => {
    await mockAllApi(page);
    await page.goto("/reliability");
    await expect(
      page.getByRole("heading", { level: 1, name: "Reliability Dashboard" }),
    ).toBeVisible({ timeout: 10_000 });
  });

  test("shows empty state when no families", async ({ page }) => {
    await mockAllApi(page, {
      "/reliability/overview": { families: [], thresholds: {} },
    });
    await page.goto("/reliability");
    await expect(
      page.getByText("No reliability data available"),
    ).toBeVisible({ timeout: 10_000 });
  });

  test("displays family metrics cards", async ({ page }) => {
    await mockAllApi(page, {
      "/reliability/overview": {
        families: [
          {
            family_id: "FAM1",
            short_name: "TestFam",
            metrics: {
              replication_rate: {
                avg_value: 0.85,
                min_value: 0.7,
                max_value: 0.95,
                papers_passing: 8,
                total_papers: 10,
                threshold: 0.7,
              },
            },
          },
        ],
        thresholds: { replication_rate: 0.7 },
      },
    });
    await page.goto("/reliability");
    await expect(page.getByText("TestFam")).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText("Replication Rate").first()).toBeVisible();
    await expect(page.getByText("8/10 pass")).toBeVisible();
  });

  test("shows thresholds reference", async ({ page }) => {
    await mockAllApi(page, {
      "/reliability/overview": {
        families: [
          {
            family_id: "FAM1",
            short_name: "TestFam",
            metrics: {
              expert_score: {
                avg_value: 7.2,
                min_value: 5.0,
                max_value: 9.0,
                papers_passing: 6,
                total_papers: 8,
                threshold: 6.0,
              },
            },
          },
        ],
        thresholds: { expert_score: 6.0 },
      },
    });
    await page.goto("/reliability");
    await expect(page.getByText("Active Thresholds")).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText("Expert Score:")).toBeVisible();
  });
});
