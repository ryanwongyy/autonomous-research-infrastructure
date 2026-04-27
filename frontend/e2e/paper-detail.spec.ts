import { test, expect } from "@playwright/test";
import { mockPaperDetailApi } from "./helpers";

const TEST_PAPER_ID = "test-paper-001";

test.describe("Paper detail page", () => {
  test("renders paper title and badges", async ({ page }) => {
    await mockPaperDetailApi(page, TEST_PAPER_ID);
    await page.goto(`/papers/${TEST_PAPER_ID}`);
    await expect(
      page.getByRole("heading", { level: 1, name: "Mock Paper Title" }),
    ).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText("APE", { exact: true })).toBeVisible();
    await expect(page.getByText("ai_governance", { exact: true })).toBeVisible();
    await expect(page.getByText("qualitative", { exact: true })).toBeVisible();
  });

  test("shows transparency banner", async ({ page }) => {
    await mockPaperDetailApi(page, TEST_PAPER_ID);
    await page.goto(`/papers/${TEST_PAPER_ID}`);
    await expect(
      page.getByText("This paper was autonomously generated and may contain errors or fabricated results."),
    ).toBeVisible({ timeout: 10_000 });
  });

  test("renders ratings section (collapsed summary shows key numbers)", async ({ page }) => {
    await mockPaperDetailApi(page, TEST_PAPER_ID);
    await page.goto(`/papers/${TEST_PAPER_ID}`);
    // Ratings is now a collapsed <details> with summary showing conservative + elo
    await expect(page.locator("summary").filter({ hasText: "TrueSkill Ratings" })).toBeVisible({ timeout: 10_000 });
    // Summary line shows Conservative: 12.4 and Elo: 1650 in the inline text
    await expect(page.locator("summary").filter({ hasText: "12.4" })).toBeVisible();
  });

  test("renders reviews section with review cards", async ({ page }) => {
    await mockPaperDetailApi(page, TEST_PAPER_ID, {
      [`/papers/${TEST_PAPER_ID}/reviews`]: [
        {
          id: 1,
          stage: "l1_screen",
          model_used: "gpt-4o",
          verdict: "pass",
          content: "This paper meets the screening criteria for methodological rigor.",
          iteration: 1,
          created_at: "2025-01-16T00:00:00Z",
          policy_scores_json: null,
        },
      ],
    });
    await page.goto(`/papers/${TEST_PAPER_ID}`);
    await expect(page.getByText("Reviews").first()).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText("l1 screen Review")).toBeVisible();
    await expect(page.getByText("pass").first()).toBeVisible();
    await expect(
      page.getByText("This paper meets the screening criteria for methodological rigor."),
    ).toBeVisible();
  });

  test("handles missing optional data gracefully", async ({ page }) => {
    await mockPaperDetailApi(page, TEST_PAPER_ID, {
      [`/papers/${TEST_PAPER_ID}`]: {
        id: TEST_PAPER_ID,
        title: "Minimal Paper",
        abstract: null,
        source: "ape",
        category: null,
        country: null,
        method: null,
        status: "public",
        review_status: "unreviewed",
        mu: null,
        sigma: null,
        conservative_rating: null,
        elo: null,
        matches_played: null,
        rank: null,
        created_at: "2025-01-15T00:00:00Z",
      },
    });
    await page.goto(`/papers/${TEST_PAPER_ID}`);
    await expect(
      page.getByRole("heading", { level: 1, name: "Minimal Paper" }),
    ).toBeVisible({ timeout: 10_000 });
    // Ratings section should not appear when mu is null
    await expect(page.locator("summary").filter({ hasText: "TrueSkill Ratings" })).not.toBeVisible();
  });

  test("shows not-found state for invalid paper ID", async ({ page }) => {
    await mockPaperDetailApi(page, "nonexistent-id", {
      ["/papers/nonexistent-id"]: { status: 404, json: { detail: "Not found" } },
    });
    await page.goto("/papers/nonexistent-id");
    await expect(
      page.getByRole("heading", { level: 1, name: "Paper not found" }),
    ).toBeVisible({ timeout: 10_000 });
    await expect(
      page.getByText(/does not exist/),
    ).toBeVisible();
  });

  test("renders cite and share buttons", async ({ page }) => {
    await mockPaperDetailApi(page, TEST_PAPER_ID);
    await page.goto(`/papers/${TEST_PAPER_ID}`);
    await expect(page.getByText("Report Issue")).toBeVisible({ timeout: 10_000 });
    // Cite button should use primary styling with full label
    await expect(page.getByText("Cite this paper")).toBeVisible();
    // The page renders CitationExport and ShareButtons components in the actions bar
    await expect(page.locator(".border-y")).toBeVisible();
  });

  test("shows release status badge", async ({ page }) => {
    await mockPaperDetailApi(page, TEST_PAPER_ID);
    await page.goto(`/papers/${TEST_PAPER_ID}`);
    // release_status: "public" should render as "Public" badge
    await expect(page.getByText("Public", { exact: true })).toBeVisible({ timeout: 10_000 });
  });

  test("shows quality summary card when ratings exist", async ({ page }) => {
    await mockPaperDetailApi(page, TEST_PAPER_ID);
    await page.goto(`/papers/${TEST_PAPER_ID}`);
    await expect(page.getByText("Quality at a Glance")).toBeVisible({ timeout: 10_000 });
  });

  test("shows expert review invitation when no expert reviews", async ({ page }) => {
    await mockPaperDetailApi(page, TEST_PAPER_ID);
    await page.goto(`/papers/${TEST_PAPER_ID}`);
    await expect(page.getByText("Expert review invited")).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText("Submit a review")).toBeVisible();
  });

  test("hides expert review invitation when expert reviews exist", async ({ page }) => {
    await mockPaperDetailApi(page, TEST_PAPER_ID, {
      [`/papers/${TEST_PAPER_ID}/expert-reviews`]: [
        {
          id: 1,
          expert_name: "Dr. Smith",
          affiliation: "MIT",
          review_date: "2025-02-01",
          overall_score: 8.5,
          methodology_score: 9.0,
          contribution_score: 7.5,
          notes: "Strong methodology.",
          is_pre_submission: false,
          created_at: "2025-02-01T00:00:00Z",
        },
      ],
    });
    await page.goto(`/papers/${TEST_PAPER_ID}`);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText("Expert review invited")).not.toBeVisible();
  });

  test("shows review pipeline dots when reviews exist", async ({ page }) => {
    await mockPaperDetailApi(page, TEST_PAPER_ID, {
      [`/papers/${TEST_PAPER_ID}/reviews`]: [
        { id: 1, stage: "l1_structure", model_used: "gpt-4o", verdict: "pass", content: "OK", iteration: 1, created_at: "2025-01-16T00:00:00Z", policy_scores_json: null },
        { id: 2, stage: "l2_provenance", model_used: "gpt-4o", verdict: "pass", content: "OK", iteration: 1, created_at: "2025-01-17T00:00:00Z", policy_scores_json: null },
        { id: 3, stage: "l3_method", model_used: "claude-3", verdict: "fail", content: "Issues found.", iteration: 1, created_at: "2025-01-18T00:00:00Z", policy_scores_json: null },
      ],
    });
    await page.goto(`/papers/${TEST_PAPER_ID}`);
    await expect(page.getByText("2 of 3 layers passed")).toBeVisible({ timeout: 10_000 });
  });

  test("shows corrections positive signal when none filed", async ({ page }) => {
    await mockPaperDetailApi(page, TEST_PAPER_ID);
    await page.goto(`/papers/${TEST_PAPER_ID}`);
    await expect(page.getByText("No corrections recorded")).toBeVisible({ timeout: 10_000 });
  });
});
