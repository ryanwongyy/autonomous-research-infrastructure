import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { CorrectionsSection } from "../corrections";
import type { CorrectionRecord } from "@/lib/types";

function makeCorrection(overrides: Partial<CorrectionRecord> = {}): CorrectionRecord {
  return {
    id: 1,
    correction_type: "data_error",
    description: "Incorrect value in Table 3 row 7",
    affected_claims_json: null,
    corrected_at: "2026-02-01T10:00:00Z",
    published_at: null,
    created_at: "2026-01-30T10:00:00Z",
    ...overrides,
  };
}

describe("CorrectionsSection", () => {
  it("shows positive signal when corrections array is empty", () => {
    render(<CorrectionsSection corrections={[]} />);
    expect(screen.getByText(/No corrections recorded/)).toBeInTheDocument();
    expect(screen.getByText(/passed all review layers/)).toBeInTheDocument();
  });

  it("renders heading with correct count for 1 correction", () => {
    render(<CorrectionsSection corrections={[makeCorrection()]} />);
    expect(screen.getByText(/1 correction recorded/)).toBeInTheDocument();
  });

  it("renders heading with plural for multiple corrections", () => {
    render(
      <CorrectionsSection corrections={[makeCorrection({ id: 1 }), makeCorrection({ id: 2 })]} />
    );
    expect(screen.getByText(/2 corrections recorded/)).toBeInTheDocument();
  });

  it("renders the correction type badge", () => {
    render(<CorrectionsSection corrections={[makeCorrection({ correction_type: "hallucination" })]} />);
    expect(screen.getByText("hallucination")).toBeInTheDocument();
  });

  it("renders CRITICAL severity for hallucination type", () => {
    render(<CorrectionsSection corrections={[makeCorrection({ correction_type: "hallucination" })]} />);
    expect(screen.getByText("critical")).toBeInTheDocument();
  });

  it("renders MINOR severity for citation_error type", () => {
    render(<CorrectionsSection corrections={[makeCorrection({ correction_type: "citation_error" })]} />);
    expect(screen.getByText("minor")).toBeInTheDocument();
  });

  it("renders the correction description", () => {
    render(<CorrectionsSection corrections={[makeCorrection()]} />);
    expect(screen.getByText("Incorrect value in Table 3 row 7")).toBeInTheDocument();
  });
});
