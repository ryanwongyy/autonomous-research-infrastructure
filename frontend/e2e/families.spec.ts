import { test, expect } from "@playwright/test";
import { mockAllApi } from "./helpers";

const mockFamilies = {
  families: [
    { id: "ai-safety", name: "AI Safety Research", short_name: "AIS", lock_protocol_type: "venue-lock", active: true, description: "Safety-focused research", paper_count: 12 },
    { id: "governance", name: "Governance Frameworks", short_name: "GOV", lock_protocol_type: "open", active: true, description: "Policy frameworks", paper_count: 8 },
  ],
  total: 2,
};

test.describe("Families page", () => {
  test("renders families list heading", async ({ page }) => {
    await mockAllApi(page, { "/families": mockFamilies });
    await page.goto("/families");
    await expect(page.getByRole("heading", { name: /paper families/i })).toBeVisible();
  });

  test("displays family cards from API", async ({ page }) => {
    await mockAllApi(page, { "/families": mockFamilies });
    await page.goto("/families");
    await expect(page.getByText("AI Safety Research")).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText("Governance Frameworks")).toBeVisible();
  });

  test("shows empty state when no families", async ({ page }) => {
    await mockAllApi(page);
    await page.goto("/families");
    // With 0 families, page should still render without crashing
    await expect(page.getByRole("heading", { name: /paper families/i })).toBeVisible();
  });
});
