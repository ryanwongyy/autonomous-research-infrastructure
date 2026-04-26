import { test, expect } from "@playwright/test";
import { mockAllApi } from "./helpers";

test.describe("Category detail page", () => {
  test("renders category name as heading", async ({ page }) => {
    await mockAllApi(page, {
      "/categories/ai_governance": {
        slug: "ai_governance",
        entries: [],
        total: 0,
      },
    });
    await page.goto("/categories/ai_governance");
    await expect(
      page.getByRole("heading", { level: 1, name: /ai governance/i }),
    ).toBeVisible({ timeout: 10_000 });
  });

  test("shows breadcrumb navigation", async ({ page }) => {
    await mockAllApi(page, {
      "/categories/climate_policy": {
        slug: "climate_policy",
        entries: [],
        total: 0,
      },
    });
    await page.goto("/categories/climate_policy");
    await expect(
      page.getByRole("link", { name: "Categories" }),
    ).toBeVisible({ timeout: 10_000 });
    // Breadcrumb shows the category name in addition to the heading
    await expect(page.getByText("climate policy").first()).toBeVisible();
  });

  test("displays papers in category", async ({ page }) => {
    await mockAllApi(page, {
      "/categories/ai_governance": {
        slug: "ai_governance",
        entries: [
          {
            paper_id: "P1",
            title: "Governing AI Systems",
            mu: 28.0,
            sigma: 3.5,
            conservative_rating: 17.5,
            elo: 1720,
            rank: 1,
            rank_change_48h: 0,
            source: "ape",
            matches_played: 12,
            review_status: "peer_reviewed",
          },
        ],
        total: 1,
      },
    });
    await page.goto("/categories/ai_governance");
    await expect(page.getByText("1 papers in this category")).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText("Governing AI Systems")).toBeVisible();
  });
});
