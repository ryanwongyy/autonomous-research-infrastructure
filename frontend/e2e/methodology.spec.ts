import { test, expect } from "@playwright/test";
import { mockAllApi } from "./helpers";

test.describe("Methodology page", () => {
  test("renders methodology content", async ({ page }) => {
    await mockAllApi(page);
    await page.goto("/methodology");
    await expect(page.getByRole("heading", { level: 1, name: "Methodology" })).toBeVisible();
  });

  test("page is accessible via navbar", async ({ page }) => {
    await mockAllApi(page);
    await page.goto("/");
    await page.getByRole("link", { name: "Methodology" }).first().click();
    await expect(page).toHaveURL(/\/methodology/);
  });

  test("renders table of contents with section links", async ({ page }) => {
    await mockAllApi(page);
    await page.goto("/methodology");
    // TOC should be visible
    await expect(page.getByText("On this page")).toBeVisible();
    // Key sections should be linked in TOC
    await expect(page.getByLabel("Table of contents").getByRole("link", { name: "Mission" })).toBeVisible();
    await expect(page.getByLabel("Table of contents").getByRole("link", { name: "5-Layer Review" })).toBeVisible();
    await expect(page.getByLabel("Table of contents").getByRole("link", { name: "Tournament" })).toBeVisible();
  });

  test("section anchors exist for TOC navigation", async ({ page }) => {
    await mockAllApi(page);
    await page.goto("/methodology");
    // Click a TOC link and verify it navigates to the section
    await page.getByLabel("Table of contents").getByRole("link", { name: "5-Layer Review" }).click();
    await expect(page).toHaveURL(/\/methodology#review/);
  });

  test("renders all 15 sections", async ({ page }) => {
    await mockAllApi(page);
    await page.goto("/methodology");
    await expect(page.getByRole("heading", { name: "Mission" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Paper Families" })).toBeVisible();
    await expect(page.getByRole("heading", { name: /5-Layer/i })).toBeVisible();
    await expect(page.getByRole("heading", { name: /Recursive Self-Improvement/i })).toBeVisible();
  });
});
