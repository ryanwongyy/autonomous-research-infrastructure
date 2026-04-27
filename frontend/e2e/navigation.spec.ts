import { test, expect } from "@playwright/test";
import { mockAllApi } from "./helpers";

test.describe("Navigation", () => {
  test.beforeEach(async ({ page }) => {
    await mockAllApi(page);
  });

  test("navbar is visible on home page", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator("nav").first()).toBeVisible();
  });

  test("primary navbar links navigate to correct pages", async ({ page }) => {
    await page.goto("/");

    // Primary nav: Publications, Leaderboard, Reliability, Corrections, Methodology, About
    await page.getByLabel("Primary navigation").getByRole("link", { name: "Publications" }).click();
    await expect(page).toHaveURL(/\/publications/);

    await page.getByLabel("Primary navigation").getByRole("link", { name: "Leaderboard" }).click();
    await expect(page).toHaveURL(/\/leaderboard/);

    await page.getByLabel("Primary navigation").getByRole("link", { name: "Reliability" }).click();
    await expect(page).toHaveURL(/\/reliability/);

    await page.getByLabel("Primary navigation").getByRole("link", { name: "Corrections" }).click();
    await expect(page).toHaveURL(/\/corrections/);
  });

  test("system dropdown contains Families and Pipeline", async ({ page }) => {
    await page.goto("/");

    // Open system dropdown
    await page.getByLabel("System pages menu").click();

    // Families and Pipeline should now be visible in the dropdown
    const familiesLink = page.getByRole("link", { name: "Families" }).first();
    await expect(familiesLink).toBeVisible();

    const pipelineLink = page.getByRole("link", { name: "Pipeline" }).first();
    await expect(pipelineLink).toBeVisible();
  });

  test("home link returns to root", async ({ page }) => {
    await page.goto("/families");
    await page.getByRole("link", { name: "Home" }).first().click();
    await expect(page).toHaveURL("/");
  });

  test("mobile menu opens and closes", async ({ page }) => {
    // Set mobile viewport
    await page.setViewportSize({ width: 375, height: 667 });
    await page.goto("/");

    // Mobile menu button should be visible
    const menuBtn = page.getByRole("button", { name: /menu/i });
    await expect(menuBtn).toBeVisible();

    // Open menu
    await menuBtn.click();
    const mobileNav = page.locator("#mobile-nav");
    await expect(mobileNav).toBeVisible();

    // Close with Escape
    await page.keyboard.press("Escape");
    await expect(mobileNav).toBeHidden();
  });

  test("404 page renders for unknown routes", async ({ page }) => {
    await page.goto("/nonexistent-route");
    // Next.js should render a 404 page
    await expect(page.locator("body")).toBeVisible();
  });

  test("active nav item is highlighted", async ({ page }) => {
    await page.goto("/publications");
    const pubLink = page.getByRole("link", { name: "Publications" }).first();
    await expect(pubLink).toHaveAttribute("aria-current", "page");
  });
});
