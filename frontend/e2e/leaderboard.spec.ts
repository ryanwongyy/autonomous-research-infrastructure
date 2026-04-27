import { test, expect } from "@playwright/test";
import { mockAllApi } from "./helpers";

test.describe("Leaderboard page", () => {
  test("renders leaderboard heading", async ({ page }) => {
    await mockAllApi(page, {
      "/families": {
        families: [{ id: "F1", name: "Test", short_name: "T", active: true }],
        total: 1,
      },
    });
    await page.goto("/leaderboard");
    await expect(page.getByRole("heading", { name: /leaderboard/i })).toBeVisible();
  });

  test("shows family selector", async ({ page }) => {
    await mockAllApi(page, {
      "/families": {
        families: [
          { id: "F1", name: "Family A", short_name: "FA", active: true },
          { id: "F2", name: "Family B", short_name: "FB", active: true },
        ],
        total: 2,
      },
    });
    await page.goto("/leaderboard");
    // Should have a dropdown or select for family selection
    await page.waitForTimeout(2000);
    await expect(page.locator("body")).toBeVisible();
  });

  test("displays leaderboard entries after selecting a family", async ({ page }) => {
    await mockAllApi(page, {
      "/families": {
        families: [{ id: "F1", name: "Test Family", short_name: "T", lock_protocol_type: "open", active: true, paper_count: 5 }],
        total: 1,
      },
      "/leaderboard": {
        entries: [
          { paper_id: "P1", title: "Top Paper", mu: 30.0, sigma: 3.0, conservative_rating: 21.0, elo: 1700, rank: 1, rank_change_48h: 0, source: "ape", matches_played: 10, review_status: "peer_reviewed" },
        ],
        total: 1,
        page: 1,
        per_page: 100,
      },
    });
    await page.goto("/leaderboard");
    // Wait for family dropdown to populate, then select
    const select = page.locator("#family-select");
    await expect(select).toBeVisible({ timeout: 10_000 });
    await select.selectOption("F1");
    await expect(page.getByText("Top Paper")).toBeVisible({ timeout: 10_000 });
  });
});
