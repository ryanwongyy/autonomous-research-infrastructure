import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { LeaderboardTable } from "../leaderboard-table";
import type { LeaderboardEntry } from "@/lib/types";

// Mock sub-components to isolate the table logic
vi.mock("../rank-change", () => ({
  RankChange: ({ change }: { change: number }) => (
    <span data-testid="rank-change">{change > 0 ? `+${change}` : change}</span>
  ),
}));

vi.mock("../review-status-badge", () => ({
  ReviewStatusBadge: ({ status }: { status: string }) => (
    <span data-testid="review-status">{status}</span>
  ),
}));

function makeEntry(overrides: Partial<LeaderboardEntry> = {}): LeaderboardEntry {
  return {
    rank: 1,
    rank_change_48h: 2,
    paper_id: "p-001",
    title: "AI Governance in Practice",
    source: "ape",
    category: "regulation",
    family_id: "F1",
    mu: 25.5,
    sigma: 3.2,
    conservative_rating: 15.9,
    elo: 1520,
    matches_played: 12,
    wins: 8,
    losses: 3,
    draws: 1,
    review_status: "peer_reviewed",
    ...overrides,
  };
}

describe("LeaderboardTable", () => {
  it("renders column headers", () => {
    render(<LeaderboardTable entries={[]} />);
    expect(screen.getByText("Rank")).toBeInTheDocument();
    expect(screen.getByText("Paper")).toBeInTheDocument();
    expect(screen.getByText("Source")).toBeInTheDocument();
    expect(screen.getByText("Elo")).toBeInTheDocument();
    expect(screen.getByText("MP")).toBeInTheDocument();
    expect(screen.getByText("Status")).toBeInTheDocument();
  });

  it("renders empty state message when no entries", () => {
    render(<LeaderboardTable entries={[]} />);
    expect(screen.getByText(/No papers in the leaderboard/)).toBeInTheDocument();
  });

  it("renders a row for each entry", () => {
    const entries = [
      makeEntry({ paper_id: "p-001", title: "Paper A" }),
      makeEntry({ paper_id: "p-002", title: "Paper B", rank: 2 }),
    ];
    render(<LeaderboardTable entries={entries} />);
    expect(screen.getByText("Paper A")).toBeInTheDocument();
    expect(screen.getByText("Paper B")).toBeInTheDocument();
  });

  it("displays rank value", () => {
    render(<LeaderboardTable entries={[makeEntry({ rank: 5 })]} />);
    expect(screen.getByText("5")).toBeInTheDocument();
  });

  it("displays dash for null rank", () => {
    render(<LeaderboardTable entries={[makeEntry({ rank: null })]} />);
    // Renders "—" (em-dash) for null rank
    const cells = screen.getAllByRole("cell");
    expect(cells[0].textContent).toBe("—");
  });

  it("formats mu to 1 decimal place", () => {
    render(<LeaderboardTable entries={[makeEntry({ mu: 25.567 })]} />);
    expect(screen.getByText("25.6")).toBeInTheDocument();
  });

  it("formats sigma to 1 decimal place", () => {
    render(<LeaderboardTable entries={[makeEntry({ sigma: 3.249 })]} />);
    expect(screen.getByText("3.2")).toBeInTheDocument();
  });

  it("formats conservative_rating to 1 decimal place", () => {
    render(<LeaderboardTable entries={[makeEntry({ conservative_rating: 22.37 })]} />);
    expect(screen.getByText("22.4")).toBeInTheDocument();
  });

  it("formats elo to integer", () => {
    render(<LeaderboardTable entries={[makeEntry({ elo: 1519.7 })]} />);
    expect(screen.getByText("1520")).toBeInTheDocument();
  });

  it("displays matches played", () => {
    render(<LeaderboardTable entries={[makeEntry({ matches_played: 42 })]} />);
    expect(screen.getByText("42")).toBeInTheDocument();
  });

  it("uppercases source label", () => {
    render(<LeaderboardTable entries={[makeEntry({ source: "ape" })]} />);
    expect(screen.getByText("APE")).toBeInTheDocument();
  });

  it("passes rank_change_48h to RankChange component", () => {
    render(<LeaderboardTable entries={[makeEntry({ rank_change_48h: 3 })]} />);
    const rankChange = screen.getByTestId("rank-change");
    expect(rankChange.textContent).toBe("+3");
  });

  it("passes review_status to ReviewStatusBadge", () => {
    render(<LeaderboardTable entries={[makeEntry({ review_status: "awaiting" })]} />);
    const badge = screen.getByTestId("review-status");
    expect(badge.textContent).toBe("awaiting");
  });
});
