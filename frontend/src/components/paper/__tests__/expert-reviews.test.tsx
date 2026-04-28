import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { ExpertReviewsSection } from "../expert-reviews";
import type { ExpertReview } from "@/lib/types";

// Mock ScoreBar to isolate ExpertReviewsSection
vi.mock("@/components/paper/score-bar", () => ({
  ScoreBar: ({ label, score, max }: { label: string; score: number; max: number }) => (
    <div data-testid={`score-bar-${label.toLowerCase()}`}>
      {label}: {score}/{max}
    </div>
  ),
}));

function makeReview(overrides: Partial<ExpertReview> = {}): ExpertReview {
  return {
    id: 1,
    expert_name: "Dr. Alice Chen",
    affiliation: "MIT CSAIL",
    review_date: "2026-02-15T00:00:00Z",
    overall_score: 4.2,
    methodology_score: 3.8,
    contribution_score: 4.5,
    notes: "Well-structured paper with novel approach.",
    is_pre_submission: true,
    created_at: "2026-02-15T10:00:00Z",
    ...overrides,
  };
}

describe("ExpertReviewsSection", () => {
  it("returns null when reviews array is empty", () => {
    const { container } = render(<ExpertReviewsSection reviews={[]} />);
    expect(container.innerHTML).toBe("");
  });

  it("renders Expert Reviews heading", () => {
    render(<ExpertReviewsSection reviews={[makeReview()]} />);
    expect(screen.getByText("Expert Reviews")).toBeInTheDocument();
  });

  it("renders expert name and affiliation", () => {
    render(<ExpertReviewsSection reviews={[makeReview()]} />);
    expect(screen.getByText("Dr. Alice Chen")).toBeInTheDocument();
    expect(screen.getByText("MIT CSAIL")).toBeInTheDocument();
  });

  it("renders overall score", () => {
    render(<ExpertReviewsSection reviews={[makeReview({ overall_score: 4.2 })]} />);
    expect(screen.getByText("4.2")).toBeInTheDocument();
  });

  it("renders methodology score bar when present", () => {
    render(<ExpertReviewsSection reviews={[makeReview({ methodology_score: 3.8 })]} />);
    const bar = screen.getByTestId("score-bar-methodology");
    expect(bar).toBeInTheDocument();
    expect(bar.textContent).toContain("Methodology");
  });

  it("omits methodology bar when methodology_score is null", () => {
    render(<ExpertReviewsSection reviews={[makeReview({ methodology_score: null })]} />);
    expect(screen.queryByTestId("score-bar-methodology")).not.toBeInTheDocument();
  });

  it("renders expandable notes for long text", () => {
    const longNotes = "A".repeat(350);
    render(<ExpertReviewsSection reviews={[makeReview({ notes: longNotes })]} />);
    expect(screen.getByText(/350 characters/)).toBeInTheDocument();
  });

  it("renders pre-submission badge", () => {
    render(<ExpertReviewsSection reviews={[makeReview({ is_pre_submission: true })]} />);
    expect(screen.getByText("Pre-submission")).toBeInTheDocument();
  });
});
