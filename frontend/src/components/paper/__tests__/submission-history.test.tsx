import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { SubmissionHistorySection } from "../submission-history";
import type { SubmissionOutcome } from "@/lib/types";

function makeOutcome(overrides: Partial<SubmissionOutcome> = {}): SubmissionOutcome {
  return {
    id: 1,
    venue_name: "Nature Machine Intelligence",
    submitted_date: "2026-01-15T00:00:00Z",
    decision: "accepted",
    decision_date: "2026-03-01T00:00:00Z",
    revision_rounds: 0,
    reviewer_feedback_summary: "Strong methodology and clear contribution.",
    created_at: "2026-01-15T10:00:00Z",
    ...overrides,
  };
}

describe("SubmissionHistorySection", () => {
  it("returns null when outcomes is empty", () => {
    const { container } = render(<SubmissionHistorySection outcomes={[]} />);
    expect(container.innerHTML).toBe("");
  });

  it("renders the Submission History heading", () => {
    render(<SubmissionHistorySection outcomes={[makeOutcome()]} />);
    expect(screen.getByText("Submission History")).toBeInTheDocument();
  });

  it("renders the venue name", () => {
    render(<SubmissionHistorySection outcomes={[makeOutcome()]} />);
    expect(screen.getByText("Nature Machine Intelligence")).toBeInTheDocument();
  });

  it("renders accepted decision badge with emerald color", () => {
    render(<SubmissionHistorySection outcomes={[makeOutcome({ decision: "accepted" })]} />);
    const badge = screen.getByText("accepted");
    expect(badge.className).toContain("emerald");
  });

  it("renders rejected decision badge with red color", () => {
    render(<SubmissionHistorySection outcomes={[makeOutcome({ decision: "rejected" })]} />);
    const badge = screen.getByText("rejected");
    expect(badge.className).toContain("red");
  });

  it("renders revision rounds when > 0", () => {
    render(<SubmissionHistorySection outcomes={[makeOutcome({ revision_rounds: 2 })]} />);
    expect(screen.getByText("2 revision rounds")).toBeInTheDocument();
  });

  it("renders expandable feedback for long text", () => {
    const longFeedback = "A".repeat(250);
    render(<SubmissionHistorySection outcomes={[makeOutcome({ reviewer_feedback_summary: longFeedback })]} />);
    expect(screen.getByText("Reviewer feedback summary")).toBeInTheDocument();
  });
});
