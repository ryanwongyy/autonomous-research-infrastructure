"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";

const navItems = [
  { href: "/", label: "Home" },
  { href: "/publications", label: "Publications" },
  { href: "/families", label: "Families" },
  { href: "/leaderboard", label: "Leaderboard" },
  { href: "/throughput", label: "Pipeline" },
  { href: "/methodology", label: "Methodology" },
  { href: "/about", label: "About" },
];

export function Navbar() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const mobileNavRef = useRef<HTMLElement>(null);
  const pathname = usePathname();

  useEffect(() => {
    if (mobileOpen && mobileNavRef.current) {
      const firstLink = mobileNavRef.current.querySelector("a");
      firstLink?.focus();
    }
  }, [mobileOpen]);

  useEffect(() => {
    if (!mobileOpen) return;
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") setMobileOpen(false);
    }
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [mobileOpen]);

  return (
    <header className="border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="mx-auto flex h-14 max-w-7xl items-center px-4">
        <Link href="/" className="mr-8 flex flex-col justify-center font-bold leading-tight">
          <span className="text-sm sm:text-base">Autonomous research infrastructure</span>
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
        </nav>

        {/* Mobile toggle */}
        <button
          type="button"
          className="ml-auto md:hidden text-muted-foreground hover:text-foreground"
          onClick={() => setMobileOpen(!mobileOpen)}
          aria-expanded={mobileOpen}
          aria-label="Toggle navigation"
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

      {/* Mobile nav */}
      {mobileOpen && (
        <nav ref={mobileNavRef} aria-label="Mobile navigation" className="md:hidden border-t bg-background px-4 py-3 space-y-2">
          {navItems.map((item) => {
            const isActive = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={isActive ? "page" : undefined}
                className={`block text-sm py-1 ${
                  isActive
                    ? "text-foreground font-medium"
                    : "text-muted-foreground hover:text-foreground"
                }`}
                onClick={() => setMobileOpen(false)}
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
