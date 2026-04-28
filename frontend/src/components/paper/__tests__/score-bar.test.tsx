import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ScoreBar } from "../score-bar";

describe("ScoreBar", () => {
  it("renders the label text", () => {
    render(<ScoreBar score={3} max={5} label="Methodology" />);
    expect(screen.getByText("Methodology")).toBeInTheDocument();
  });

  it("has ARIA meter role with correct attributes", () => {
    render(<ScoreBar score={3.5} max={5} label="Contribution" />);
    const meter = screen.getByRole("meter", { name: "Contribution" });
    expect(meter).toHaveAttribute("aria-valuenow", "3.5");
    expect(meter).toHaveAttribute("aria-valuemin", "0");
    expect(meter).toHaveAttribute("aria-valuemax", "5");
  });

  it("clamps percentage at 100 when score exceeds max", () => {
    const { container } = render(<ScoreBar score={12} max={10} label="Test" />);
    const bar = container.querySelector("[style]");
    expect(bar?.getAttribute("style")).toContain("width: 100%");
  });

  it("shows 0% width when max is 0", () => {
    const { container } = render(<ScoreBar score={5} max={0} label="Zero Max" />);
    const bar = container.querySelector("[style]");
    expect(bar?.getAttribute("style")).toContain("width: 0%");
  });

  it("displays score value formatted to 1 decimal", () => {
    render(<ScoreBar score={3.456} max={5} label="Test" />);
    expect(screen.getByText("3.5")).toBeInTheDocument();
  });

  it("hides value when showValue is false", () => {
    render(<ScoreBar score={3} max={5} label="Hidden" showValue={false} />);
    expect(screen.queryByText("3.0")).not.toBeInTheDocument();
  });

  it("applies custom color class", () => {
    const { container } = render(
      <ScoreBar score={3} max={5} label="Custom" color="bg-red-500" />
    );
    const innerBar = container.querySelector(".bg-red-500");
    expect(innerBar).toBeInTheDocument();
  });
});
