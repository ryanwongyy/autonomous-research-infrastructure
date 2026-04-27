import { test, expect } from "@playwright/test";
import { mockAllApi } from "./helpers";

test.describe("Categories page", () => {
  test("renders Categories heading", async ({ page }) => {
    await mockAllApi(page);
    await page.goto("/categories");
    await expect(
      page.getByRole("heading", { level: 1, name: "Categories" }),
    ).toBeVisible({ timeout: 10_000 });
  });

  test("shows empty state when no categories", async ({ page }) => {
    await mockAllApi(page, {
      "/categories": [],
    });
    await page.goto("/categories");
    await expect(
      page.getByText("No categories configured yet"),
    ).toBeVisible({ timeout: 10_000 });
  });

  test("displays category cards with paper counts", async ({ page }) => {
    await mockAllApi(page, {
      "/categories": [
        { slug: "ai_governance", name: "AI Governance", domain_id: "D1", paper_count: 12 },
        { slug: "climate_policy", name: "Climate Policy", domain_id: "D2", paper_count: 8 },
      ],
    });
    await page.goto("/categories");
    await expect(page.getByText("AI Governance").first()).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText("Climate Policy").first()).toBeVisible();
    await expect(page.getByText("12 papers")).toBeVisible();
    await expect(page.getByText("8 papers")).toBeVisible();
  });
});
