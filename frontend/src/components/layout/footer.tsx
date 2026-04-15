import Link from "next/link";

const footerLinks = {
  Research: [
    { href: "/publications", label: "Publications" },
    { href: "/families", label: "Paper Families" },
    { href: "/leaderboard", label: "Leaderboard" },
    { href: "/throughput", label: "Pipeline" },
  ],
  System: [
    { href: "/sources", label: "Sources" },
    { href: "/reliability", label: "Reliability" },
    { href: "/failures", label: "Failures" },
    { href: "/rsi", label: "RSI" },
  ],
  About: [
    { href: "/methodology", label: "Methodology" },
    { href: "/about", label: "About" },
    { href: "/api/v1/papers/feed.json", label: "JSON Feed" },
    { href: "https://github.com/ryanwongyy/autonomous-research-infrastructure", label: "GitHub" },
  ],
};

export function Footer() {
  return (
    <footer className="mt-auto border-t bg-muted/30">
      <div className="mx-auto max-w-7xl px-4 py-8">
        <div className="grid grid-cols-2 gap-8 sm:grid-cols-4">
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
              <ul className="mt-2 space-y-1.5">
                {links.map((link) => (
                  <li key={link.href}>
                    <Link
                      href={link.href}
                      className="text-sm text-muted-foreground hover:text-foreground transition-colors"
                    >
                      {link.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div className="mt-8 border-t pt-4 text-center text-xs text-muted-foreground">
          Built with Next.js, FastAPI, and TrueSkill
        </div>
      </div>
    </footer>
  );
}
