import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { FunnelChart } from "../funnel-chart";

describe("FunnelChart", () => {
  const stages = {
    scouting: 12,
    design: 8,
    analysis: 5,
    drafting: 3,
    submission_ready: 1,
  };

  it("renders all stage labels", () => {
    render(<FunnelChart stages={stages} killed={2} />);
    expect(screen.getByText("Scouting")).toBeInTheDocument();
    expect(screen.getByText("Design")).toBeInTheDocument();
    expect(screen.getByText("Analysis")).toBeInTheDocument();
    expect(screen.getByText("Drafting")).toBeInTheDocument();
    expect(screen.getByText("Submission Ready")).toBeInTheDocument();
  });

  it("renders the killed row", () => {
    render(<FunnelChart stages={stages} killed={4} />);
    expect(screen.getByText("Killed")).toBeInTheDocument();
    expect(screen.getByText("4")).toBeInTheDocument();
  });

  it("renders stage counts", () => {
    render(<FunnelChart stages={stages} killed={0} />);
    expect(screen.getByText("12")).toBeInTheDocument();
    expect(screen.getByText("8")).toBeInTheDocument();
    expect(screen.getByText("5")).toBeInTheDocument();
  });

  it("has an aria-label with summary", () => {
    render(<FunnelChart stages={stages} killed={2} />);
    const chart = screen.getByRole("img");
    expect(chart).toHaveAttribute("aria-label");
    expect(chart.getAttribute("aria-label")).toContain("Scouting: 12");
    expect(chart.getAttribute("aria-label")).toContain("Killed: 2");
  });

  it("renders with empty stages", () => {
    render(<FunnelChart stages={{}} killed={0} />);
    // Should still show killed row
    expect(screen.getByText("Killed")).toBeInTheDocument();
    expect(screen.getByText("0")).toBeInTheDocument();
  });

  it("applies custom className", () => {
    const { container } = render(
      <FunnelChart stages={stages} killed={1} className="custom-class" />
    );
    expect(container.firstChild).toHaveClass("custom-class");
  });

  it("ensures bar widths are at least 2% (minimum visibility)", () => {
    const { container } = render(
      <FunnelChart stages={{ scouting: 100, drafting: 0 }} killed={0} />
    );
    // Even a 0-count stage should have a visible bar (min 2%)
    const bars = container.querySelectorAll("[style]");
    bars.forEach((bar) => {
      const width = bar.getAttribute("style");
      if (width?.includes("width")) {
        const pct = parseFloat(width.replace(/.*width:\s*/, "").replace(/%.*/, ""));
        expect(pct).toBeGreaterThanOrEqual(2);
      }
    });
  });
});
