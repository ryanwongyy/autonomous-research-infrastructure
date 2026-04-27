import { test, expect } from "@playwright/test";
import { mockAllApi } from "./helpers";

test.describe("About page", () => {
  test("renders about content", async ({ page }) => {
    await mockAllApi(page);
    await page.goto("/about");
    await expect(page.getByRole("heading").first()).toBeVisible();
  });

  test("page is accessible via navbar", async ({ page }) => {
    await mockAllApi(page);
    await page.goto("/");
    await page.getByRole("link", { name: "About" }).first().click();
    await expect(page).toHaveURL(/\/about/);
  });
});
