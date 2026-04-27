import Link from "next/link";

const footerLinks = {
  Research: [
    { href: "/publications", label: "Publications" },
    { href: "/leaderboard", label: "Leaderboard" },
    { href: "/corrections", label: "Corrections" },
    { href: "/reliability", label: "Reliability" },
    { href: "/categories", label: "Categories" },
  ],
  System: [
    { href: "/families", label: "Paper Families" },
    { href: "/throughput", label: "Pipeline" },
    { href: "/outcomes", label: "Outcomes" },
    { href: "/failures", label: "Failures" },
    { href: "/sources", label: "Sources" },
    { href: "/rsi", label: "RSI" },
  ],
  About: [
    { href: "/methodology", label: "Methodology" },
    { href: "/glossary", label: "Glossary" },
    { href: "/about", label: "About" },
    { href: "/api/v1/papers/feed.atom", label: "Atom Feed" },
    { href: "/api/v1/papers/feed.json", label: "JSON Feed" },
    { href: "https://github.com/ryanwongyy/autonomous-research-infrastructure", label: "GitHub" },
  ],
};

export function Footer() {
  return (
    <footer className="mt-auto border-t bg-muted/30" aria-label="Site footer">
      <div className="mx-auto max-w-7xl px-4 py-8">
        <nav className="grid grid-cols-2 gap-8 sm:grid-cols-4" aria-label="Footer navigation">
          {/* Brand */}
          <div className="col-span-2 sm:col-span-1">
            <p className="font-semibold text-sm">ARI</p>
            <p className="mt-1 text-xs text-muted-foreground leading-relaxed">
              Autonomous research infrastructure for AI governance.
              11 families, 7-role pipeline, 5-layer review.
            </p>
          </div>

          {Object.entries(footerLinks).map(([section, links]) => (
            <div key={section}>
              <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                {section}
              </p>
              <ul className="mt-2 space-y-2.5 sm:space-y-1.5">
                {links.map((link) => {
                  const isExternal = link.href.startsWith("http") || link.href.startsWith("/api/");
                  return (
                    <li key={link.href}>
                      <Link
                        href={link.href}
                        {...(isExternal ? { target: "_blank", rel: "noopener noreferrer" } : {})}
                        aria-label={isExternal ? `${link.label} (opens in new tab)` : undefined}
                        className="text-sm text-muted-foreground hover:text-foreground dark:hover:text-foreground transition-colors inline-flex items-center gap-1 focus-visible:outline-none focus-visible:text-foreground"
                      >
                        {link.label}
                        {isExternal && (
                          <svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className="opacity-50 dark:opacity-60">
                            <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
                            <polyline points="15 3 21 3 21 9" />
                            <line x1="10" y1="14" x2="21" y2="3" />
                          </svg>
                        )}
                      </Link>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </nav>

        <div className="mt-8 border-t pt-4 flex flex-col sm:flex-row items-center justify-between gap-2 text-xs text-muted-foreground">
          <span>Built with Next.js, FastAPI, and TrueSkill</span>
          <span>All papers are AI-generated &middot; Open access &middot; No paywall</span>
        </div>
      </div>
    </footer>
  );
}
