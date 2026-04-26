import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { CitationExport } from "../citation-export";

// Mock clipboard API
const mockWriteText = vi.fn().mockResolvedValue(undefined);
Object.defineProperty(navigator, "clipboard", {
  value: { writeText: mockWriteText },
  writable: true,
  configurable: true,
});

// Mock window.location.href
Object.defineProperty(window, "location", {
  value: { href: "https://ari.example.com/papers/test-123" },
  writable: true,
  configurable: true,
});

const defaultProps = {
  title: "AI Governance Framework for Federal Procurement",
  paperId: "test-123",
  source: "ape",
  createdAt: "2026-01-15T10:00:00Z",
  category: "regulation",
};

describe("CitationExport", () => {
  beforeEach(() => {
    mockWriteText.mockClear();
  });

  it("renders Cite button", () => {
    render(<CitationExport {...defaultProps} />);
    expect(screen.getByText("Cite this paper")).toBeInTheDocument();
  });

  it("opens dropdown on click", () => {
    render(<CitationExport {...defaultProps} />);
    fireEvent.click(screen.getByText("Cite this paper"));
    expect(screen.getByText("Export citation")).toBeInTheDocument();
  });

  it("shows three format options", () => {
    render(<CitationExport {...defaultProps} />);
    fireEvent.click(screen.getByText("Cite this paper"));
    expect(screen.getByText("BibTeX")).toBeInTheDocument();
    expect(screen.getByText("APA")).toBeInTheDocument();
    expect(screen.getByText("Plain Text")).toBeInTheDocument();
  });

  it("generates BibTeX with correct fields", () => {
    render(<CitationExport {...defaultProps} />);
    fireEvent.click(screen.getByText("Cite this paper"));
    const pres = screen.getAllByRole("generic").filter((el) => el.tagName === "PRE");
    const bibtexPre = pres.find((el) => el.textContent?.includes("@article"));
    expect(bibtexPre).toBeTruthy();
    expect(bibtexPre!.textContent).toContain("AI Governance Framework");
    expect(bibtexPre!.textContent).toContain("2026");
  });

  it("generates APA citation with year and title", () => {
    render(<CitationExport {...defaultProps} />);
    fireEvent.click(screen.getByText("Cite this paper"));
    const pres = screen.getAllByRole("generic").filter((el) => el.tagName === "PRE");
    const apaPre = pres.find(
      (el) => el.textContent?.includes("Autonomous Research Infrastructure. (2026)")
    );
    expect(apaPre).toBeTruthy();
  });

  it("generates plain text citation", () => {
    render(<CitationExport {...defaultProps} />);
    fireEvent.click(screen.getByText("Cite this paper"));
    const pres = screen.getAllByRole("generic").filter((el) => el.tagName === "PRE");
    const plainPre = pres.find((el) =>
      el.textContent?.includes('"AI Governance Framework')
    );
    expect(plainPre).toBeTruthy();
  });

  it("copies to clipboard on Copy button click", async () => {
    render(<CitationExport {...defaultProps} />);
    fireEvent.click(screen.getByText("Cite this paper"));
    const copyButtons = screen.getAllByText("Copy");
    fireEvent.click(copyButtons[0]);
    expect(mockWriteText).toHaveBeenCalledTimes(1);
  });

  it("shows Copied! feedback after copy", async () => {
    render(<CitationExport {...defaultProps} />);
    fireEvent.click(screen.getByText("Cite this paper"));
    const copyButtons = screen.getAllByText("Copy");
    fireEvent.click(copyButtons[0]);
    // After the async copy, "Copied!" should appear
    expect(await screen.findByText("Copied!")).toBeInTheDocument();
  });
});
