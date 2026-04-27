import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { SignificanceMemoCard } from "../significance-memo";
import type { SignificanceMemo } from "@/lib/types";

function makeMemo(overrides: Partial<SignificanceMemo> = {}): SignificanceMemo {
  return {
    id: 1,
    author: "Dr. Smith",
    memo_text: "This paper makes a significant contribution to AI governance.",
    tournament_rank_at_time: 5,
    tournament_confidence_json: null,
    editorial_verdict: "significant",
    created_at: "2026-01-15T10:00:00Z",
    ...overrides,
  };
}

describe("SignificanceMemoCard", () => {
  it("renders the Editorial Significance title", () => {
    render(<SignificanceMemoCard memo={makeMemo()} />);
    expect(screen.getByText("Editorial Significance")).toBeInTheDocument();
  });

  it("renders the editorial verdict badge", () => {
    render(<SignificanceMemoCard memo={makeMemo({ editorial_verdict: "noteworthy" })} />);
    expect(screen.getByText("noteworthy")).toBeInTheDocument();
  });

  it("renders the memo text", () => {
    render(<SignificanceMemoCard memo={makeMemo()} />);
    expect(screen.getByText(/significant contribution to AI governance/)).toBeInTheDocument();
  });

  it("renders the author name", () => {
    render(<SignificanceMemoCard memo={makeMemo({ author: "Prof. Johnson" })} />);
    expect(screen.getByText("Prof. Johnson")).toBeInTheDocument();
  });

  it("renders tournament rank when present", () => {
    render(<SignificanceMemoCard memo={makeMemo({ tournament_rank_at_time: 3 })} />);
    expect(screen.getByText("#3")).toBeInTheDocument();
  });

  it("omits rank when tournament_rank_at_time is null", () => {
    render(<SignificanceMemoCard memo={makeMemo({ tournament_rank_at_time: null })} />);
    expect(screen.queryByText(/Rank at assessment/)).not.toBeInTheDocument();
  });
});
