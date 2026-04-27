import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ReviewStatusBadge } from "../review-status-badge";

describe("ReviewStatusBadge", () => {
  it("renders 'Peer Reviewed' for peer_reviewed status", () => {
    render(<ReviewStatusBadge status="peer_reviewed" />);
    expect(screen.getByText("Peer Reviewed")).toBeInTheDocument();
  });

  it("renders 'Awaiting Review' for awaiting status", () => {
    render(<ReviewStatusBadge status="awaiting" />);
    expect(screen.getByText("Awaiting Review")).toBeInTheDocument();
  });

  it("renders 'Issues Flagged' for issues status", () => {
    render(<ReviewStatusBadge status="issues" />);
    expect(screen.getByText("Issues Flagged")).toBeInTheDocument();
  });

  it("renders 'Critical Errors' for errors status", () => {
    render(<ReviewStatusBadge status="errors" />);
    expect(screen.getByText("Critical Errors")).toBeInTheDocument();
  });

  it("falls back to raw status string for unknown status", () => {
    render(<ReviewStatusBadge status="custom_status" />);
    expect(screen.getByText("custom_status")).toBeInTheDocument();
  });
});
