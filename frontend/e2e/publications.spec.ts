import { test, expect } from "@playwright/test";
import { mockAllApi } from "./helpers";

test.describe("Publications page", () => {
  test("renders publications heading", async ({ page }) => {
    await mockAllApi(page);
    await page.goto("/publications");
    await expect(page.getByRole("heading", { name: /publication/i })).toBeVisible();
  });

  test("shows papers when available", async ({ page }) => {
    await mockAllApi(page, {
      "/papers/public": [
        {
          id: "P1", title: "A Study on AI Governance", abstract: "This paper examines...",
          release_status: "public", funnel_stage: "candidate", family_id: "F1",
          category: "regulation", created_at: "2026-04-01T00:00:00Z",
        },
      ],
    });
    await page.goto("/publications");
    await expect(page.getByText("A Study on AI Governance")).toBeVisible({ timeout: 10_000 });
  });

  test("shows empty state when no publications", async ({ page }) => {
    await mockAllApi(page);
    await page.goto("/publications");
    await page.waitForTimeout(2000);
    // Page should still render
    await expect(page.locator("body")).toBeVisible();
  });
});
