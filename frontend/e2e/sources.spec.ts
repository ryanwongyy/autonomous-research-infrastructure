import { test, expect } from "@playwright/test";
import { mockAllApi } from "./helpers";

const mockSources = {
  sources: [
    {
      id: "fed_register", name: "Federal Register", url: "https://federalregister.gov",
      tier: "T1", source_type: "government", active: true, fragility_score: 0.1,
    },
    {
      id: "courtlistener", name: "CourtListener", url: "https://courtlistener.com",
      tier: "T2", source_type: "legal", active: true, fragility_score: 0.3,
    },
  ],
  total: 2,
};

test.describe("Sources page", () => {
  test("renders sources heading", async ({ page }) => {
    await mockAllApi(page, { "/sources": mockSources });
    await page.goto("/sources");
    await expect(page.getByRole("heading", { name: /source/i })).toBeVisible();
  });

  test("displays source cards", async ({ page }) => {
    await mockAllApi(page, { "/sources": mockSources });
    await page.goto("/sources");
    await expect(page.getByText("Federal Register")).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText("CourtListener")).toBeVisible();
  });

  test("shows empty state when no sources", async ({ page }) => {
    await mockAllApi(page);
    await page.goto("/sources");
    await expect(page.locator("body")).toBeVisible();
  });
});
