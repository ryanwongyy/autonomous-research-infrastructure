import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { QualitySummary } from "../quality-summary";

const defaults = {
  reviewLayersPassed: 3,
  reviewLayersTotal: 5,
  qualityScore: 7.4,
  expertScore: 8.2,
  conservativeRating: 25.3,
  rank: 5,
  noveltyVerdict: "novel" as const,
  correctionsCount: 0,
};

describe("QualitySummary", () => {
  it("renders heading", () => {
    render(<QualitySummary {...defaults} />);
    expect(screen.getByText("Quality at a Glance")).toBeInTheDocument();
  });

  it("shows review layers passed fraction", () => {
    render(<QualitySummary {...defaults} />);
    expect(screen.getByText("3/5")).toBeInTheDocument();
    expect(screen.getByText("Reviews Passed")).toBeInTheDocument();
  });

  it("shows quality score with /10 suffix", () => {
    render(<QualitySummary {...defaults} />);
    expect(screen.getByText("7.4")).toBeInTheDocument();
  });

  it("shows expert score", () => {
    render(<QualitySummary {...defaults} />);
    expect(screen.getByText("8.2")).toBeInTheDocument();
    expect(screen.getByText("Expert Score")).toBeInTheDocument();
  });

  it("shows conservative rating", () => {
    render(<QualitySummary {...defaults} />);
    expect(screen.getByText("25.3")).toBeInTheDocument();
    expect(screen.getByText("Rating")).toBeInTheDocument();
  });

  it("shows rank with # prefix", () => {
    render(<QualitySummary {...defaults} />);
    expect(screen.getByText("#5")).toBeInTheDocument();
  });

  it("shows novelty verdict capitalized", () => {
    render(<QualitySummary {...defaults} />);
    expect(screen.getByText("Novel")).toBeInTheDocument();
  });

  it("shows corrections count as 0 with green styling", () => {
    render(<QualitySummary {...defaults} />);
    const zeroEl = screen.getByText("0");
    expect(zeroEl.className).toContain("emerald");
  });

  it("shows corrections count > 0 with amber styling", () => {
    render(<QualitySummary {...defaults} correctionsCount={3} />);
    const threeEl = screen.getByText("3");
    expect(threeEl.className).toContain("amber");
  });

  it("returns null when no indicators available", () => {
    const { container } = render(
      <QualitySummary
        reviewLayersPassed={0}
        reviewLayersTotal={0}
        qualityScore={null}
        expertScore={null}
        conservativeRating={null}
        rank={null}
        noveltyVerdict={null}
        correctionsCount={0}
      />
    );
    expect(container.innerHTML).toBe("");
  });

  it("hides expert score when no expert reviews", () => {
    render(<QualitySummary {...defaults} expertScore={null} />);
    expect(screen.queryByText("Expert Score")).not.toBeInTheDocument();
  });

  it("hides rank when null", () => {
    render(<QualitySummary {...defaults} rank={null} />);
    expect(screen.queryByText("Rank")).not.toBeInTheDocument();
  });

  it("shows borderline novelty in amber", () => {
    render(<QualitySummary {...defaults} noveltyVerdict="borderline" />);
    const el = screen.getByText("Borderline");
    expect(el.className).toContain("amber");
  });
});
