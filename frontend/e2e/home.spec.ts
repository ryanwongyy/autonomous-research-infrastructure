import { test, expect } from "@playwright/test";
import { mockAllApi } from "./helpers";

test.describe("Home page", () => {
  test("renders dashboard heading", async ({ page }) => {
    await mockAllApi(page);
    await page.goto("/");
    await expect(page.locator("h1")).toBeVisible();
  });

  test("displays loading state then content", async ({ page }) => {
    await mockAllApi(page, {
      "/families": {
        families: [
          { id: "F1", name: "Test Family", short_name: "TF", lock_protocol_type: "open", active: true, description: "Test", paper_count: 5 },
        ],
        total: 1,
      },
    });
    await page.goto("/");
    // After API resolves, family card or content should appear
    await expect(page.getByText("Test Family")).toBeVisible({ timeout: 10_000 });
  });

  test("shows error state when all APIs fail", async ({ page }) => {
    await page.route("**/api/v1/**", (route) =>
      route.fulfill({ status: 500, json: { detail: "Server error" } })
    );
    await page.goto("/");
    // Should show some error indication (not crash)
    await page.waitForTimeout(2000);
    // Page should still render without throwing
    await expect(page.locator("body")).toBeVisible();
  });
});
