import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { Footer } from "../footer";

vi.mock("next/link", () => ({
  __esModule: true,
  default: ({ href, children, ...props }: { href: string; children: React.ReactNode; [key: string]: unknown }) => (
    <a href={href} {...props}>{children}</a>
  ),
}));

describe("Footer", () => {
  it("renders the footer landmark", () => {
    render(<Footer />);
    const footer = screen.getByRole("contentinfo");
    expect(footer).toBeInTheDocument();
  });

  it("renders the ARI brand text", () => {
    render(<Footer />);
    expect(screen.getByText("ARI")).toBeInTheDocument();
  });

  it("renders the tagline about autonomous research", () => {
    render(<Footer />);
    expect(screen.getByText(/Autonomous research infrastructure/)).toBeInTheDocument();
  });

  it("renders Research section links", () => {
    render(<Footer />);
    expect(screen.getByText("Publications")).toBeInTheDocument();
    expect(screen.getByText("Leaderboard")).toBeInTheDocument();
    expect(screen.getByText("Corrections")).toBeInTheDocument();
    expect(screen.getByText("Reliability")).toBeInTheDocument();
  });

  it("renders System section links", () => {
    render(<Footer />);
    expect(screen.getByText("Paper Families")).toBeInTheDocument();
    expect(screen.getByText("Failures")).toBeInTheDocument();
    expect(screen.getByText("Sources")).toBeInTheDocument();
  });

  it("renders About section links", () => {
    render(<Footer />);
    expect(screen.getByText("Methodology")).toBeInTheDocument();
    // "About" appears as both a section heading and a link
    const aboutElements = screen.getAllByText("About");
    expect(aboutElements.length).toBeGreaterThanOrEqual(2);
  });

  it("marks external links with target=_blank", () => {
    render(<Footer />);
    const githubLink = screen.getByText("GitHub");
    expect(githubLink).toHaveAttribute("target", "_blank");
    expect(githubLink).toHaveAttribute("rel", "noopener noreferrer");
  });

  it("marks JSON Feed as external (opens in new tab)", () => {
    render(<Footer />);
    const feedLink = screen.getByText("JSON Feed");
    expect(feedLink).toHaveAttribute("target", "_blank");
  });

  it("adds accessible label for external links", () => {
    render(<Footer />);
    const githubLink = screen.getByLabelText("GitHub (opens in new tab)");
    expect(githubLink).toBeInTheDocument();
  });

  it("renders the technology credits", () => {
    render(<Footer />);
    expect(screen.getByText(/Next\.js, FastAPI, and TrueSkill/)).toBeInTheDocument();
  });

  it("renders the open access notice", () => {
    render(<Footer />);
    expect(screen.getByText(/AI-generated/)).toBeInTheDocument();
    expect(screen.getByText(/No paywall/)).toBeInTheDocument();
  });

  it("has section headings for navigation groups", () => {
    render(<Footer />);
    expect(screen.getByText("Research")).toBeInTheDocument();
    expect(screen.getByText("System")).toBeInTheDocument();
    // "About" appears both as a section header and a link
    const aboutElements = screen.getAllByText("About");
    expect(aboutElements.length).toBeGreaterThanOrEqual(2);
  });

  it("has a footer navigation landmark", () => {
    render(<Footer />);
    const navs = screen.getAllByRole("navigation");
    const footerNav = navs.find(
      (n) => n.getAttribute("aria-label") === "Footer navigation"
    );
    expect(footerNav).toBeTruthy();
  });
});
