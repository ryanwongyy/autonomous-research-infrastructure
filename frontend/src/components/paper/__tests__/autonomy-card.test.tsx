import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { AutonomyCardSection } from "../autonomy-card";
import type { AutonomyCard } from "@/lib/types";

function makeCard(overrides: Partial<AutonomyCard> = {}): AutonomyCard {
  return {
    role_autonomy: {
      scout: "full",
      designer: "high",
      analyst: "moderate",
      drafter: "full",
      reviewer: "supervised",
    },
    human_intervention_points: [
      { role: "reviewer", level: "moderate", description: "Human spot-checks L3 methodology reviews" },
    ],
    overall_autonomy_score: 0.85,
    created_at: "2026-01-15T10:00:00Z",
    updated_at: null,
    ...overrides,
  };
}

describe("AutonomyCardSection", () => {
  it("renders the Autonomy Breakdown title", () => {
    render(<AutonomyCardSection card={makeCard()} />);
    expect(screen.getByText("Autonomy Breakdown")).toBeInTheDocument();
  });

  it("renders overall score as percentage", () => {
    render(<AutonomyCardSection card={makeCard({ overall_autonomy_score: 0.85 })} />);
    expect(screen.getByText("85%")).toBeInTheDocument();
  });

  it("applies green color for high score (>=0.8)", () => {
    const { container } = render(<AutonomyCardSection card={makeCard({ overall_autonomy_score: 0.9 })} />);
    const scoreEl = screen.getByText("90%");
    expect(scoreEl.className).toContain("emerald");
  });

  it("applies red color for low score (<0.5)", () => {
    const { container } = render(<AutonomyCardSection card={makeCard({ overall_autonomy_score: 0.3 })} />);
    const scoreEl = screen.getByText("30%");
    expect(scoreEl.className).toContain("red");
  });

  it("renders role autonomy grid with all roles", () => {
    render(<AutonomyCardSection card={makeCard()} />);
    expect(screen.getByText("scout")).toBeInTheDocument();
    expect(screen.getByText("designer")).toBeInTheDocument();
    expect(screen.getByText("analyst")).toBeInTheDocument();
    // "full" appears for both scout and drafter
    expect(screen.getAllByText("full").length).toBe(2);
    expect(screen.getByText("supervised")).toBeInTheDocument();
  });

  it("renders human intervention points when present", () => {
    render(<AutonomyCardSection card={makeCard()} />);
    expect(screen.getByText("Human intervention points")).toBeInTheDocument();
    expect(screen.getByText(/Human spot-checks/)).toBeInTheDocument();
  });

  it("hides intervention section when list is empty", () => {
    render(<AutonomyCardSection card={makeCard({ human_intervention_points: [] })} />);
    expect(screen.queryByText("Human intervention points")).not.toBeInTheDocument();
  });
});
