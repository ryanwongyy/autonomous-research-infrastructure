import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { FamilyCard } from "../family-card";
import type { PaperFamily } from "@/lib/types";

// Mock next/link to render a plain <a> tag
vi.mock("next/link", () => ({
  __esModule: true,
  default: ({ href, children, ...props }: { href: string; children: React.ReactNode; [key: string]: unknown }) => (
    <a href={href} {...props}>{children}</a>
  ),
}));

function makeFamily(overrides: Partial<PaperFamily> = {}): PaperFamily {
  return {
    id: "F1",
    name: "Regulatory Mapping",
    short_name: "RegMap",
    description: "Maps AI governance regulations across jurisdictions",
    lock_protocol_type: "venue-lock",
    venue_ladder: { flagship: ["Nature", "Science"], elite_field: ["PNAS"] },
    mandatory_checks: ["replication"],
    fatal_failures: ["data-fabrication"],
    elite_ceiling: "10%",
    max_portfolio_share: 0.2,
    paper_count: 14,
    active: true,
    ...overrides,
  };
}

describe("FamilyCard", () => {
  it("renders the family name", () => {
    render(<FamilyCard family={makeFamily()} />);
    expect(screen.getByText("Regulatory Mapping")).toBeInTheDocument();
  });

  it("renders the short name", () => {
    render(<FamilyCard family={makeFamily()} />);
    expect(screen.getByText("RegMap")).toBeInTheDocument();
  });

  it("renders the description", () => {
    render(<FamilyCard family={makeFamily()} />);
    expect(screen.getByText(/Maps AI governance/)).toBeInTheDocument();
  });

  it("renders the paper count", () => {
    render(<FamilyCard family={makeFamily({ paper_count: 7 })} />);
    expect(screen.getByText("7 papers")).toBeInTheDocument();
  });

  it("links to the family detail page", () => {
    render(<FamilyCard family={makeFamily({ id: "F5" })} />);
    const link = screen.getByRole("link");
    expect(link).toHaveAttribute("href", "/families/F5");
  });

  it("renders lock protocol badge with correct label", () => {
    render(<FamilyCard family={makeFamily({ lock_protocol_type: "method-lock" })} />);
    expect(screen.getByText("Method Lock")).toBeInTheDocument();
  });

  it("renders venue-lock protocol", () => {
    render(<FamilyCard family={makeFamily({ lock_protocol_type: "venue-lock" })} />);
    expect(screen.getByText("Venue Lock")).toBeInTheDocument();
  });

  it("renders open protocol", () => {
    render(<FamilyCard family={makeFamily({ lock_protocol_type: "open" })} />);
    expect(screen.getByText("Open")).toBeInTheDocument();
  });

  it("renders flagship venue badges", () => {
    render(<FamilyCard family={makeFamily()} />);
    expect(screen.getByText("Nature")).toBeInTheDocument();
    expect(screen.getByText("Science")).toBeInTheDocument();
  });

  it("handles null venue_ladder gracefully", () => {
    render(<FamilyCard family={makeFamily({ venue_ladder: null })} />);
    expect(screen.getByText("Regulatory Mapping")).toBeInTheDocument();
    // No venue badges should appear — no crash
  });

  it("includes an accessible label with name and count", () => {
    render(<FamilyCard family={makeFamily()} />);
    const link = screen.getByRole("link");
    expect(link.getAttribute("aria-label")).toContain("Regulatory Mapping");
    expect(link.getAttribute("aria-label")).toContain("14 papers");
  });
});
