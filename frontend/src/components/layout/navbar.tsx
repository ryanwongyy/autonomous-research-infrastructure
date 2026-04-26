"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";

const navItems = [
  { href: "/", label: "Home" },
  { href: "/publications", label: "Publications" },
  { href: "/leaderboard", label: "Leaderboard" },
  { href: "/reliability", label: "Reliability" },
  { href: "/corrections", label: "Corrections" },
  { href: "/methodology", label: "Methodology" },
  { href: "/glossary", label: "Glossary" },
  { href: "/about", label: "About" },
];

const systemItems = [
  { href: "/families", label: "Families" },
  { href: "/throughput", label: "Pipeline" },
  { href: "/sources", label: "Sources" },
  { href: "/categories", label: "Categories" },
  { href: "/failures", label: "Failures" },
  { href: "/outcomes", label: "Outcomes" },
  { href: "/rsi", label: "RSI" },
];

export function Navbar() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [systemOpen, setSystemOpen] = useState(false);
  const mobileNavRef = useRef<HTMLElement>(null);
  const toggleBtnRef = useRef<HTMLButtonElement>(null);
  const systemDropdownRef = useRef<HTMLDivElement>(null);
  const pathname = usePathname();

  // Focus first link when menu opens
  useEffect(() => {
    if (mobileOpen && mobileNavRef.current) {
      const firstLink = mobileNavRef.current.querySelector("a");
      firstLink?.focus();
    }
  }, [mobileOpen]);

  // Close on Escape and restore focus to toggle button
  const closeMobile = useCallback(() => {
    setMobileOpen(false);
    // Restore focus to the toggle button after closing
    requestAnimationFrame(() => toggleBtnRef.current?.focus());
  }, []);

  // Close system dropdown when clicking outside
  useEffect(() => {
    if (!systemOpen) return;
    function handleClickOutside(e: MouseEvent) {
      if (
        systemDropdownRef.current &&
        !systemDropdownRef.current.contains(e.target as Node)
      ) {
        setSystemOpen(false);
      }
    }
    function handleEscape(e: KeyboardEvent) {
      if (e.key === "Escape") setSystemOpen(false);
    }
    document.addEventListener("mousedown", handleClickOutside);
    document.addEventListener("keydown", handleEscape);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("keydown", handleEscape);
    };
  }, [systemOpen]);

  useEffect(() => {
    if (!mobileOpen) return;
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") {
        closeMobile();
        return;
      }

      // Focus trapping: cycle Tab through mobile nav links only
      if (e.key === "Tab" && mobileNavRef.current) {
        const focusable = mobileNavRef.current.querySelectorAll<HTMLElement>("a, button");
        if (focusable.length === 0) return;

        const first = focusable[0];
        const last = focusable[focusable.length - 1];

        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    }
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [mobileOpen, closeMobile]);

  const isSystemActive = systemItems.some((item) => pathname.startsWith(item.href));

  return (
    <header className="border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="mx-auto flex h-14 max-w-7xl items-center px-4">
        <Link href="/" className="mr-8 flex flex-col justify-center font-bold leading-tight">
          <span className="hidden sm:inline text-sm sm:text-base">Autonomous research infrastructure</span>
          <span className="sm:hidden text-base font-bold">ARI</span>
          <span className="hidden text-[11px] text-muted-foreground sm:inline">
            for AI governance
          </span>
        </Link>

        {/* Desktop nav */}
        <nav aria-label="Primary navigation" className="hidden md:flex items-center gap-6 text-sm">
          {navItems.map((item) => {
            const isActive = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={isActive ? "page" : undefined}
                className={`transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 rounded-sm ${
                  isActive
                    ? "text-foreground font-medium"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                {item.label}
              </Link>
            );
          })}

          {/* System dropdown */}
          <div ref={systemDropdownRef} className="relative">
            <button
              type="button"
              onClick={() => setSystemOpen(!systemOpen)}
              aria-expanded={systemOpen}
              aria-haspopup="true"
              aria-label="System pages menu"
              className={`flex items-center gap-1 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 rounded-sm ${
                isSystemActive
                  ? "text-foreground font-medium"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              System
              <svg
                xmlns="http://www.w3.org/2000/svg"
                width="12"
                height="12"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-hidden="true"
                className={`transition-transform ${systemOpen ? "rotate-180" : ""}`}
              >
                <polyline points="6 9 12 15 18 9" />
              </svg>
            </button>

            {systemOpen && (
              <div className="absolute left-0 top-full mt-2 w-44 rounded-lg border bg-background shadow-lg py-1 z-50">
                {systemItems.map((item) => {
                  const isActive = pathname.startsWith(item.href);
                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      onClick={() => setSystemOpen(false)}
                      className={`block px-3 py-2 text-sm transition-colors hover:bg-muted ${
                        isActive ? "text-foreground font-medium" : "text-muted-foreground"
                      }`}
                    >
                      {item.label}
                    </Link>
                  );
                })}
              </div>
            )}
          </div>
        </nav>

        {/* Mobile toggle — 44px min touch target (WCAG 2.5.8) */}
        <button
          ref={toggleBtnRef}
          type="button"
          className="ml-auto md:hidden flex items-center justify-center min-w-[44px] min-h-[44px] -mr-2 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary transition-colors"
          onClick={() => setMobileOpen(!mobileOpen)}
          aria-expanded={mobileOpen}
          aria-controls="mobile-nav"
          aria-label={mobileOpen ? "Close navigation menu" : "Open navigation menu"}
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            width="20"
            height="20"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
          >
            {mobileOpen ? (
              <>
                <line x1="18" y1="6" x2="6" y2="18" />
                <line x1="6" y1="6" x2="18" y2="18" />
              </>
            ) : (
              <>
                <line x1="4" y1="6" x2="20" y2="6" />
                <line x1="4" y1="12" x2="20" y2="12" />
                <line x1="4" y1="18" x2="20" y2="18" />
              </>
            )}
          </svg>
        </button>
      </div>

      {/* Mobile nav — focus-trapped panel */}
      {mobileOpen && (
        <nav
          ref={mobileNavRef}
          id="mobile-nav"
          aria-label="Mobile navigation"
          className="md:hidden border-t bg-background px-4 py-3 space-y-1"
        >
          {navItems.map((item) => {
            const isActive = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={isActive ? "page" : undefined}
                className={`block text-sm py-2 min-h-[44px] flex items-center ${
                  isActive
                    ? "text-foreground font-medium"
                    : "text-muted-foreground hover:text-foreground"
                }`}
                onClick={closeMobile}
              >
                {item.label}
              </Link>
            );
          })}

          {/* System section divider */}
          <div className="border-t pt-2 mt-1">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground px-0">
              System
            </span>
          </div>
          {systemItems.map((item) => {
            const isActive = pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={isActive ? "page" : undefined}
                className={`block text-sm py-2 min-h-[44px] flex items-center ${
                  isActive
                    ? "text-foreground font-medium"
                    : "text-muted-foreground hover:text-foreground"
                }`}
                onClick={closeMobile}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>
      )}
    </header>
  );
}
