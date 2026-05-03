import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ReviewPipelineSummary } from "../review-pipeline-summary";

describe("ReviewPipelineSummary", () => {
  const reviews = [
    { id: 1, stage: "l1_structure", verdict: "pass" },
    { id: 2, stage: "l2_provenance", verdict: "pass" },
    { id: 3, stage: "l3_method", verdict: "fail" },
  ];

  it("renders pass count text", () => {
    render(<ReviewPipelineSummary reviews={reviews} />);
    expect(screen.getByText("2 of 3 layers passed")).toBeInTheDocument();
  });

  it("renders one dot per review", () => {
    const { container } = render(<ReviewPipelineSummary reviews={reviews} />);
    const dots = container.querySelectorAll("span.rounded-full");
    expect(dots.length).toBe(3);
  });

  it("colors pass dots green and fail dots red", () => {
    const { container } = render(<ReviewPipelineSummary reviews={reviews} />);
    const dots = container.querySelectorAll("span.rounded-full");
    expect(dots[0].className).toContain("emerald");
    expect(dots[1].className).toContain("emerald");
    expect(dots[2].className).toContain("red");
  });

  it("shows amber for non-pass/non-fail verdicts", () => {
    const { container } = render(
      <ReviewPipelineSummary reviews={[{ id: 1, stage: "l1", verdict: "revise" }]} />
    );
    const dots = container.querySelectorAll("span.rounded-full");
    expect(dots[0].className).toContain("amber");
  });

  it("returns null for empty reviews", () => {
    const { container } = render(<ReviewPipelineSummary reviews={[]} />);
    expect(container.innerHTML).toBe("");
  });

  it("has accessible group label", () => {
    render(<ReviewPipelineSummary reviews={reviews} />);
    const group = screen.getByRole("img");
    expect(group.getAttribute("aria-label")).toBe("2 of 3 review layers passed");
  });

  it("adds human-readable title to dots", () => {
    const { container } = render(
      <ReviewPipelineSummary reviews={[{ id: 1, stage: "l1_structure", verdict: "pass" }]} />
    );
    const dot = container.querySelector("span.rounded-full");
    expect(dot?.getAttribute("title")).toBe("L1 Structural — pass");
  });
});
