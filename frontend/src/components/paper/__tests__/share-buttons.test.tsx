import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ShareButtons } from "../share-buttons";

// Mock clipboard
const mockWriteText = vi.fn().mockResolvedValue(undefined);
Object.defineProperty(navigator, "clipboard", {
  value: { writeText: mockWriteText },
  writable: true,
  configurable: true,
});

// Mock window.location and window.open
Object.defineProperty(window, "location", {
  value: { href: "https://ari.example.com/papers/p-001" },
  writable: true,
  configurable: true,
});
window.open = vi.fn();

const defaultProps = {
  title: "AI Governance Framework",
  paperId: "p-001",
};

describe("ShareButtons", () => {
  beforeEach(() => {
    mockWriteText.mockClear();
    (window.open as ReturnType<typeof vi.fn>).mockClear();
  });

  it("renders copy link button", () => {
    render(<ShareButtons {...defaultProps} />);
    expect(screen.getByLabelText("Copy permanent link for citation")).toBeInTheDocument();
  });

  it("renders Twitter/X button", () => {
    render(<ShareButtons {...defaultProps} />);
    expect(screen.getByLabelText("Share on Twitter/X")).toBeInTheDocument();
  });

  it("renders LinkedIn button", () => {
    render(<ShareButtons {...defaultProps} />);
    expect(screen.getByLabelText("Share on LinkedIn")).toBeInTheDocument();
  });

  it("renders WhatsApp link", () => {
    render(<ShareButtons {...defaultProps} />);
    expect(screen.getByLabelText("Share via WhatsApp")).toBeInTheDocument();
  });

  it("renders email link", () => {
    render(<ShareButtons {...defaultProps} />);
    expect(screen.getByLabelText("Share via email")).toBeInTheDocument();
  });

  it("copies URL to clipboard on link button click", () => {
    render(<ShareButtons {...defaultProps} />);
    fireEvent.click(screen.getByLabelText("Copy permanent link for citation"));
    expect(mockWriteText).toHaveBeenCalledWith("https://ari.example.com/papers/p-001");
  });
});
