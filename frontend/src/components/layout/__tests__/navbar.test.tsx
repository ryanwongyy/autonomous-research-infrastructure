import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { Navbar } from "../navbar";

// Track the pathname returned by the mock
let mockPathname = "/";

vi.mock("next/link", () => ({
  __esModule: true,
  default: ({ href, children, ...props }: { href: string; children: React.ReactNode; [key: string]: unknown }) => (
    <a href={href} {...props}>{children}</a>
  ),
}));

vi.mock("next/navigation", () => ({
  usePathname: () => mockPathname,
}));

describe("Navbar", () => {
  beforeEach(() => {
    mockPathname = "/";
  });

  // ── Brand / Logo ───────────────────────────────────────────────────

  it("renders the brand link", () => {
    render(<Navbar />);
    const brandLinks = screen.getAllByRole("link").filter(
      (l) => l.getAttribute("href") === "/"
    );
    expect(brandLinks.length).toBeGreaterThanOrEqual(1);
  });

  it("renders the ARI abbreviation for mobile", () => {
    render(<Navbar />);
    expect(screen.getByText("ARI")).toBeInTheDocument();
  });

  // ── Desktop navigation items ────────────────────────────────────

  it("renders primary nav items", () => {
    render(<Navbar />);
    expect(screen.getByText("Publications")).toBeInTheDocument();
    expect(screen.getByText("Leaderboard")).toBeInTheDocument();
    expect(screen.getByText("Reliability")).toBeInTheDocument();
    expect(screen.getByText("Corrections")).toBeInTheDocument();
    expect(screen.getByText("Methodology")).toBeInTheDocument();
    expect(screen.getByText("Glossary")).toBeInTheDocument();
    expect(screen.getByText("About")).toBeInTheDocument();
  });

  it("renders Families and Pipeline in system dropdown", () => {
    render(<Navbar />);
    fireEvent.click(screen.getByLabelText("System pages menu"));
    expect(screen.getAllByText("Families").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Pipeline").length).toBeGreaterThanOrEqual(1);
  });

  // ── Active state ───────────────────────────────────────────────────

  it("marks Home as current page on / path", () => {
    mockPathname = "/";
    render(<Navbar />);
    // Home should appear with aria-current="page"
    const homeLinks = screen.getAllByText("Home");
    const hasActive = homeLinks.some(
      (el) => el.getAttribute("aria-current") === "page"
    );
    expect(hasActive).toBe(true);
  });

  it("marks Publications as current page on /publications path", () => {
    mockPathname = "/publications";
    render(<Navbar />);
    const pubLinks = screen.getAllByText("Publications");
    const hasActive = pubLinks.some(
      (el) => el.getAttribute("aria-current") === "page"
    );
    expect(hasActive).toBe(true);
  });

  // ── Mobile toggle ──────────────────────────────────────────────────

  it("has a mobile menu toggle button", () => {
    render(<Navbar />);
    const btn = screen.getByLabelText("Open navigation menu");
    expect(btn).toBeInTheDocument();
  });

  it("opens mobile nav on toggle click", () => {
    render(<Navbar />);
    const btn = screen.getByLabelText("Open navigation menu");
    fireEvent.click(btn);
    // Mobile nav should appear
    const mobileNav = document.getElementById("mobile-nav");
    expect(mobileNav).toBeInTheDocument();
  });

  it("shows close label when mobile nav is open", () => {
    render(<Navbar />);
    fireEvent.click(screen.getByLabelText("Open navigation menu"));
    expect(screen.getByLabelText("Close navigation menu")).toBeInTheDocument();
  });

  it("closes mobile nav on second toggle click", () => {
    render(<Navbar />);
    const btn = screen.getByLabelText("Open navigation menu");
    fireEvent.click(btn); // open
    fireEvent.click(screen.getByLabelText("Close navigation menu")); // close
    const mobileNav = document.getElementById("mobile-nav");
    expect(mobileNav).toBeNull();
  });

  // ── System dropdown ────────────────────────────────────────────────

  it("renders System dropdown button", () => {
    render(<Navbar />);
    const systemBtn = screen.getByLabelText("System pages menu");
    expect(systemBtn).toBeInTheDocument();
    expect(systemBtn.getAttribute("aria-expanded")).toBe("false");
  });

  it("opens system dropdown on click", () => {
    render(<Navbar />);
    const systemBtn = screen.getByLabelText("System pages menu");
    fireEvent.click(systemBtn);
    expect(systemBtn.getAttribute("aria-expanded")).toBe("true");
    expect(screen.getByText("Sources")).toBeInTheDocument();
    expect(screen.getByText("Failures")).toBeInTheDocument();
    expect(screen.getByText("Outcomes")).toBeInTheDocument();
  });

  // ── Accessibility ──────────────────────────────────────────────────

  it("has accessible nav landmarks", () => {
    render(<Navbar />);
    const navs = screen.getAllByRole("navigation");
    // At least the desktop nav should be labeled
    const labeled = navs.filter((n) => n.getAttribute("aria-label"));
    expect(labeled.length).toBeGreaterThanOrEqual(1);
  });

  it("mobile toggle meets minimum touch target (44px)", () => {
    render(<Navbar />);
    const btn = screen.getByLabelText("Open navigation menu");
    expect(btn.className).toContain("min-w-[44px]");
    expect(btn.className).toContain("min-h-[44px]");
  });

  // ── Mobile nav system section ──────────────────────────────────────

  it("shows system items in mobile nav", () => {
    render(<Navbar />);
    fireEvent.click(screen.getByLabelText("Open navigation menu"));
    // System section divider
    const mobileNav = document.getElementById("mobile-nav")!;
    expect(mobileNav).toBeInTheDocument();
    // Should contain system items like Families, Pipeline, Sources, etc.
    expect(mobileNav.textContent).toContain("Families");
    expect(mobileNav.textContent).toContain("Pipeline");
    expect(mobileNav.textContent).toContain("Sources");
  });
});
