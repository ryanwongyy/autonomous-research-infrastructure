import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { NoveltyCheckCard } from "../novelty-check";
import type { NoveltyCheck } from "@/lib/types";

// Mock next/link
vi.mock("next/link", () => ({
  __esModule: true,
  default: ({ href, children, ...props }: { href: string; children: React.ReactNode; [key: string]: unknown }) => (
    <a href={href} {...props}>{children}</a>
  ),
}));

function makeCheck(overrides: Partial<NoveltyCheck> = {}): NoveltyCheck {
  return {
    id: 1,
    verdict: "novel",
    highest_similarity_score: 0.32,
    checked_against_count: 150,
    similar_papers: [
      { paper_id: "p-100", similarity: 0.32 },
      { paper_id: "p-101", similarity: 0.28 },
    ],
    model_used: "claude-3.5-sonnet",
    created_at: "2026-01-20T10:00:00Z",
    ...overrides,
  };
}

describe("NoveltyCheckCard", () => {
  it("renders the Novelty Assessment title", () => {
    render(<NoveltyCheckCard check={makeCheck()} />);
    expect(screen.getByText("Novelty Assessment")).toBeInTheDocument();
  });

  it("renders verdict badge with emerald class for novel", () => {
    render(<NoveltyCheckCard check={makeCheck({ verdict: "novel" })} />);
    const badge = screen.getByText("novel");
    // The badge parent should have emerald styling
    expect(badge.className).toContain("emerald");
  });

  it("renders verdict badge with red class for derivative", () => {
    render(<NoveltyCheckCard check={makeCheck({ verdict: "derivative" })} />);
    const badge = screen.getByText("derivative");
    expect(badge.className).toContain("red");
  });

  it("renders similarity percentage", () => {
    render(<NoveltyCheckCard check={makeCheck({ highest_similarity_score: 0.45 })} />);
    expect(screen.getByText("45%")).toBeInTheDocument();
  });

  it("has ARIA meter for similarity gauge", () => {
    render(<NoveltyCheckCard check={makeCheck({ highest_similarity_score: 0.32 })} />);
    const meter = screen.getByRole("meter", { name: "Highest similarity score" });
    expect(meter).toHaveAttribute("aria-valuenow", "32");
    expect(meter).toHaveAttribute("aria-valuemax", "100");
  });

  it("renders papers-checked count", () => {
    render(<NoveltyCheckCard check={makeCheck({ checked_against_count: 250 })} />);
    expect(screen.getByText("250")).toBeInTheDocument();
    expect(screen.getByText("papers checked")).toBeInTheDocument();
  });

  it("renders similar paper links", () => {
    render(<NoveltyCheckCard check={makeCheck()} />);
    const links = screen.getAllByRole("link");
    expect(links.some((l) => l.getAttribute("href") === "/papers/p-100")).toBe(true);
    expect(links.some((l) => l.getAttribute("href") === "/papers/p-101")).toBe(true);
  });
});
