import type { Metadata } from "next";
import Link from "next/link";
import { Separator } from "@/components/ui/separator";

export const metadata: Metadata = {
  title: "Glossary — Methods, Processes & Terminology",
  description:
    "Quick reference for all methods, processes, and indicators used in the autonomous research infrastructure. TrueSkill, RSI, autonomy cards, novelty verdicts, and more.",
};

interface Entry {
  term: string;
  letter: string;
  short: string;
  long: string;
  see?: string;
  link?: { href: string; label: string };
}

const ENTRIES: Entry[] = [
  {
    term: "Autonomy card",
    letter: "A",
    short:
      "Per-paper record of which of the 7 pipeline roles ran fully automated, supervised, or human-driven.",
    long: "Every paper carries an autonomy card. The autonomy score (0-1) is the fraction of roles that ran fully automated end-to-end — e.g. 0.71 = 5 of 7 roles. Researchers should calibrate trust against this score.",
    link: { href: "/methodology#governance", label: "Methodology · Governance" },
  },
  {
    term: "Autonomy score",
    letter: "A",
    short: "Numeric (0-1) summary of an autonomy card.",
    long: "Fraction of pipeline roles that ran fully automated. 0 = entirely human, 1 = entirely AI. Reported alongside every public paper.",
    see: "Autonomy card",
  },
  {
    term: "Claim-permission profile",
    letter: "C",
    short:
      "Per-source rule set declaring which kinds of claims can be made from data of that source.",
    long: "Stored on each source card. Tier A (e.g. official government databases) has broad permissions; Tier C (e.g. web-scraped) has narrow permissions and explicit claim prohibitions. The Verifier role audits every claim against the source's profile.",
    link: { href: "/methodology#sources", label: "Methodology · Source Architecture" },
  },
  {
    term: "Collegial review",
    letter: "C",
    short:
      "Three colleague agents (Dr. Methods, Prof. Domain, Editor Chen) iteratively refine the draft until convergence.",
    long: "Distinct from the L1-L5 review pipeline. Mimics human peer review: the Drafter retains editorial control and explicitly accepts/rejects suggestions. Three exit paths: Converged (submit-ready), Plateaued (human edits required), Max Rounds (escalate to human).",
    link: { href: "/methodology#collegial", label: "Methodology · Collegial Review" },
  },
  {
    term: "Conservative rating",
    letter: "C",
    short: "TrueSkill worst-case skill estimate: μ − 3σ.",
    long: "Used for ranking. A paper with μ=20, σ=1 (conservative=17) ranks higher than one with μ=25, σ=5 (conservative=10). More matches → lower σ → higher conservative rating, all else equal.",
    see: "TrueSkill",
  },
  {
    term: "Correction",
    letter: "C",
    short: "Recorded post-publication change to a public paper.",
    long: "Three types: errata (minor data/computational error), update (changed interpretation), retraction (fundamental flaw). All transparent. A low correction rate is not necessarily good — it may indicate either high upfront quality or poor post-publication monitoring.",
    link: { href: "/corrections", label: "Corrections page" },
  },
  {
    term: "Derivative (novelty verdict)",
    letter: "D",
    short:
      "Novelty similarity ≥ 0.6 to existing same-family papers — paper is blocked from advancing.",
    long: "One of three novelty verdicts (Novel < 0.3, Marginal 0.3-0.6, Derivative ≥ 0.6). Derivative papers are killed before review.",
    see: "Novelty verdict",
  },
  {
    term: "Design lock",
    letter: "D",
    short:
      "Pre-analysis commitment to research design that cannot be silently modified.",
    long: "After the Designer role specifies the locked design (identification strategy, data sources, expected contribution), all downstream coherence is checked against it. The Manifest-Drift gates enforce the lock.",
    see: "Manifest drift",
  },
  {
    term: "Elo rating",
    letter: "E",
    short: "Classic head-to-head rating used alongside TrueSkill.",
    long: "Reported on the leaderboard for context. Elo is more familiar to many researchers but has weaker uncertainty handling than TrueSkill. The conservative TrueSkill rating is the primary ranking signal.",
  },
  {
    term: "Family",
    letter: "F",
    short:
      "A locked research method or venue grouping (e.g. QCA studies, top-tier journal candidates).",
    long: "11 paper families are defined (`backend/domain_configs/`). Each family has a fixed protocol, source-tier policy, and target venues. Tournaments are family-local — a QCA paper does not compete against an RDD paper.",
    link: { href: "/families", label: "Families page" },
  },
  {
    term: "L1-L5 (review layers)",
    letter: "L",
    short:
      "Five independent review layers every paper must pass before tournament entry.",
    long: "L1 Structural (formatting, completeness) · L2 Provenance (every claim traced to a source card) · L3 Method (non-Claude or human methodological review) · L4 Adversarial (deliberate flaw-hunting) · L5 Human (escalation when prior layers flag).",
    link: { href: "/methodology#review", label: "Methodology · Review" },
  },
  {
    term: "Manifest drift",
    letter: "M",
    short:
      "Silent deviation between a paper's locked design and what subsequent stages actually do.",
    long: "Three coherence gates prevent drift: Design-Data Coherence (pre-analysis), Analysis-Design Alignment (pre-drafting), Claims-Analysis Alignment (pre-packaging). Default drift threshold: 0.8.",
    link: { href: "/methodology#drift", label: "Methodology · Drift Detection" },
  },
  {
    term: "Marginal (novelty verdict)",
    letter: "M",
    short:
      "Novelty similarity 0.3-0.6 — paper proceeds with a warning label.",
    long: "Marginally novel papers are not blocked but are flagged so reviewers know there is significant overlap with existing work in the family.",
    see: "Novelty verdict",
  },
  {
    term: "Mu (μ)",
    letter: "M",
    short: "TrueSkill mean skill estimate.",
    long: "The most likely skill level of a paper given the matches played so far. By itself it is misleading — a paper with high μ but high σ has played few matches and may be lucky. Always read alongside σ.",
    see: "TrueSkill",
  },
  {
    term: "Novel (novelty verdict)",
    letter: "N",
    short:
      "Novelty similarity < 0.3 — paper makes a distinct contribution and proceeds freely.",
    long: "The pass case for the novelty gate.",
    see: "Novelty verdict",
  },
  {
    term: "Novelty verdict",
    letter: "N",
    short:
      "One of {Novel, Marginal, Derivative} based on Jaccard similarity to same-family papers.",
    long: "Computed after design lock, before review. Threshold 0.3 / 0.6. Prevents derivative work from entering the pipeline.",
    link: { href: "/methodology#novelty", label: "Methodology · Novelty" },
  },
  {
    term: "Pipeline (7 roles)",
    letter: "P",
    short:
      "Scout → Designer → Data Steward → Analyst → Drafter → Verifier → Packager.",
    long: "The seven role types that produce a paper. Each role's automation level is tracked on the autonomy card.",
    link: { href: "/methodology#pipeline", label: "Methodology · Pipeline" },
  },
  {
    term: "Release status",
    letter: "R",
    short:
      "Lifecycle stage of a paper: Internal → Candidate → Submitted → Public.",
    long: "Internal: in pipeline. Candidate: passed all reviews, awaiting human submission verdict. Submitted: sent to a venue. Public: openly published with full audit trail.",
  },
  {
    term: "RSI (Recursive Self-Improvement)",
    letter: "R",
    short:
      "Four-tier system that improves the factory itself, with safety guards.",
    long: "Tier 1 Prompts → Tier 2 Configs → Tier 3 Architecture → Tier 4 Meta. Each tier escalates when the lower tier plateaus. Every change is logged as an A/B experiment with auto-rollback if performance degrades > 10%.",
    link: { href: "/methodology#rsi", label: "Methodology · RSI" },
  },
  {
    term: "Sigma (σ)",
    letter: "S",
    short: "TrueSkill skill uncertainty (1 standard deviation).",
    long: "Decreases as the paper plays more matches. Used in the conservative rating (μ − 3σ) to penalize papers with sparse data.",
    see: "TrueSkill",
  },
  {
    term: "Significance memo",
    letter: "S",
    short:
      "Human verdict on whether a paper is worth submitting to a venue.",
    long: "Three verdicts: Submit (advances to venue), Hold (needs revision), Reject (kill for publication). Evaluates venue fit, policy relevance, and evidence strength. Required before release status moves to Submitted.",
  },
  {
    term: "Source card",
    letter: "S",
    short:
      "Registered metadata for every data source: tier, claim permissions, prohibitions, known traps.",
    long: "All claims must trace back to a source card. The L2 Provenance review enforces this.",
    see: "Claim-permission profile",
  },
  {
    term: "TrueSkill",
    letter: "T",
    short:
      "Bayesian skill rating system (Microsoft Research) used for the family-local tournament.",
    long: "Each paper has a Gaussian skill distribution N(μ, σ²). Matches use position-swapped LLM judging (paper A is shown first to one judge, second to another) to eliminate positional bias. The conservative rating μ − 3σ is the worst-case skill estimate at 99.7% confidence.",
    link: { href: "/methodology#tournament", label: "Methodology · Tournament" },
  },
];

const groups: Record<string, Entry[]> = ENTRIES.reduce(
  (acc, e) => {
    (acc[e.letter] ||= []).push(e);
    return acc;
  },
  {} as Record<string, Entry[]>,
);

const letters = Object.keys(groups).sort();

export default function GlossaryPage() {
  return (
    <div className="mx-auto max-w-4xl px-4 py-8">
      <h1 className="text-3xl font-bold">Glossary</h1>
      <p className="mt-1 text-muted-foreground">
        Quick reference for the methods, processes, indicators, and abbreviations
        used across the system. For deep explanations, follow the linked
        methodology section in each entry.
      </p>

      <Separator className="my-6" />

      {/* Letter index */}
      <nav aria-label="Glossary letter index" className="mb-8">
        <ul className="flex flex-wrap gap-2 text-sm">
          {letters.map((letter) => (
            <li key={letter}>
              <a
                href={`#letter-${letter}`}
                className="inline-flex h-8 w-8 items-center justify-center rounded-md border bg-background font-mono font-semibold hover:bg-muted hover:text-primary transition-colors"
              >
                {letter}
              </a>
            </li>
          ))}
        </ul>
      </nav>

      {letters.map((letter) => (
        <section key={letter} id={`letter-${letter}`} className="mb-8 scroll-mt-20">
          <h2 className="text-2xl font-bold border-b pb-2 mb-4 font-mono text-muted-foreground">
            {letter}
          </h2>
          <dl className="space-y-5">
            {groups[letter].map((e) => (
              <div key={e.term} id={`term-${e.term.toLowerCase().replace(/\s+/g, "-")}`}>
                <dt className="font-semibold text-base scroll-mt-20">{e.term}</dt>
                <dd className="mt-1 text-sm text-muted-foreground">
                  <p>{e.short}</p>
                  <p className="mt-1.5">{e.long}</p>
                  <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs">
                    {e.link && (
                      <Link
                        href={e.link.href}
                        className="text-primary hover:underline"
                      >
                        → {e.link.label}
                      </Link>
                    )}
                    {e.see && (
                      <span className="text-muted-foreground">
                        See also:{" "}
                        <a
                          href={`#term-${e.see.toLowerCase().replace(/\s+/g, "-")}`}
                          className="text-primary hover:underline"
                        >
                          {e.see}
                        </a>
                      </span>
                    )}
                  </div>
                </dd>
              </div>
            ))}
          </dl>
        </section>
      ))}

      <Separator className="my-8" />
      <p className="text-sm text-muted-foreground">
        Missing a term? <a href="https://github.com/ryanwongyy/autonomous-research-infrastructure/issues/new?title=Glossary+addition&labels=docs" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">Open an issue</a>.
      </p>
    </div>
  );
}
