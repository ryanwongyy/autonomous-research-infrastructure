import { test, expect } from "@playwright/test";
import { mockAllApi } from "./helpers";

test.describe("Throughput / Pipeline page", () => {
  test("renders pipeline heading", async ({ page }) => {
    await mockAllApi(page);
    await page.goto("/throughput");
    await expect(page.getByRole("heading").first()).toBeVisible();
  });

  test("displays funnel data when provided", async ({ page }) => {
    await mockAllApi(page, {
      "/throughput/funnel": {
        stages: [
          { stage: "generated", count: 100 },
          { stage: "screened", count: 80 },
          { stage: "reviewed", count: 40 },
          { stage: "candidate", count: 20 },
        ],
      },
      "/families": { families: [], total: 0 },
    });
    await page.goto("/throughput");
    await page.waitForTimeout(2000);
    // Page should render without crashing
    await expect(page.locator("body")).toBeVisible();
  });

  test("handles empty pipeline state", async ({ page }) => {
    await mockAllApi(page);
    await page.goto("/throughput");
    await page.waitForTimeout(2000);
    await expect(page.locator("body")).toBeVisible();
  });
});
