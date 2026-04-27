import type { Metadata } from "next";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";

export const metadata: Metadata = {
  title: "Methodology",
  description: "Research methodology for the autonomous research infrastructure for AI governance — generation pipeline, tournament system, collegial review, and RSI architecture.",
};

export default function MethodologyPage() {
  return (
    <div className="mx-auto max-w-4xl px-4 py-8">
      <h1 className="text-3xl font-bold">Methodology</h1>
      <p className="mt-2 text-muted-foreground">
        How the autonomous research infrastructure for AI governance produces submission-ready papers.
      </p>

      {/* Table of Contents */}
      <nav className="mt-4 rounded-lg border bg-muted/30 p-4" aria-label="Table of contents">
        <h2 className="text-sm font-semibold mb-2">On this page</h2>
        <ol className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-1 text-sm list-decimal list-inside">
          {[
            { id: "mission", label: "Mission" },
            { id: "families", label: "Paper Families" },
            { id: "pipeline", label: "7-Role Pipeline" },
            { id: "review", label: "5-Layer Review" },
            { id: "tournament", label: "Tournament" },
            { id: "sources", label: "Source Architecture" },
            { id: "release", label: "Public Release" },
            { id: "drift", label: "Manifest-Drift Detection" },
            { id: "reliability", label: "Reliability Framework" },
            { id: "failures", label: "Failure Taxonomy" },
            { id: "novelty", label: "Novelty Detection" },
            { id: "post-pipeline", label: "Post-Pipeline Tracking" },
            { id: "governance", label: "Governance & Disclosure" },
            { id: "collegial", label: "Collegial Review Loop" },
            { id: "rsi", label: "Self-Improvement (RSI)" },
          ].map((item) => (
            <li key={item.id}>
              <a href={`#${item.id}`} className="text-muted-foreground hover:text-foreground transition-colors">
                {item.label}
              </a>
            </li>
          ))}
        </ol>
      </nav>

      {/* Visual pipeline overview — gestalt before the deep dive */}
      <section aria-label="Pipeline overview" className="mt-6 mb-2 rounded-lg border bg-card p-4 sm:p-6">
        <h2 className="text-lg font-semibold mb-3">At a glance</h2>
        <p className="text-sm text-muted-foreground mb-4">
          A paper flows left to right through three macro-stages. The
          numbered details below explain each stage in depth.
        </p>

        {/* Stage 1: Generate */}
        <div className="space-y-3 text-sm">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="inline-flex items-center justify-center h-7 w-7 rounded-full bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300 font-bold text-xs shrink-0">1</span>
            <span className="font-semibold">Generate</span>
            <span className="text-muted-foreground text-xs">— 7-role pipeline produces a draft</span>
          </div>
          <div className="ml-9 flex flex-wrap items-center gap-1 text-xs text-muted-foreground">
            {["Scout", "Designer", "Data Steward", "Analyst", "Drafter", "Verifier", "Packager"].map((r, i, arr) => (
              <span key={r} className="contents">
                <span className="rounded bg-muted px-2 py-0.5 font-mono">{r}</span>
                {i < arr.length - 1 && <span className="text-muted-foreground/50" aria-hidden="true">→</span>}
              </span>
            ))}
          </div>

          {/* Stage 2: Review + Tournament */}
          <div className="flex items-center gap-2 flex-wrap pt-2">
            <span className="inline-flex items-center justify-center h-7 w-7 rounded-full bg-emerald-100 dark:bg-emerald-900/40 text-emerald-700 dark:text-emerald-300 font-bold text-xs shrink-0">2</span>
            <span className="font-semibold">Evaluate</span>
            <span className="text-muted-foreground text-xs">— independent review then tournament ranking</span>
          </div>
          <div className="ml-9 flex flex-wrap items-center gap-1 text-xs text-muted-foreground">
            {["L1", "L2", "L3", "L4", "L5"].map((r, i, arr) => (
              <span key={r} className="contents">
                <span className="rounded bg-emerald-100 dark:bg-emerald-900/40 text-emerald-800 dark:text-emerald-300 px-2 py-0.5 font-mono">{r}</span>
                {i < arr.length - 1 && <span className="text-muted-foreground/50" aria-hidden="true">·</span>}
              </span>
            ))}
            <span className="text-muted-foreground/60 mx-2" aria-hidden="true">→</span>
            <span className="rounded bg-purple-100 dark:bg-purple-900/40 text-purple-800 dark:text-purple-300 px-2 py-0.5 font-mono">TrueSkill tournament</span>
            <span className="text-muted-foreground/60 mx-2" aria-hidden="true">→</span>
            <span className="rounded bg-amber-100 dark:bg-amber-900/40 text-amber-800 dark:text-amber-300 px-2 py-0.5 font-mono">Collegial review</span>
          </div>

          {/* Stage 3: Release + Track */}
          <div className="flex items-center gap-2 flex-wrap pt-2">
            <span className="inline-flex items-center justify-center h-7 w-7 rounded-full bg-cyan-100 dark:bg-cyan-900/40 text-cyan-700 dark:text-cyan-300 font-bold text-xs shrink-0">3</span>
            <span className="font-semibold">Release &amp; Track</span>
            <span className="text-muted-foreground text-xs">— human verdict gates publication; outcomes feed back</span>
          </div>
          <div className="ml-9 flex flex-wrap items-center gap-1 text-xs text-muted-foreground">
            {["Internal", "Candidate", "Submitted", "Public"].map((r, i, arr) => (
              <span key={r} className="contents">
                <span className="rounded bg-muted px-2 py-0.5 font-mono">{r}</span>
                {i < arr.length - 1 && <span className="text-muted-foreground/50" aria-hidden="true">→</span>}
              </span>
            ))}
            <span className="text-muted-foreground/60 mx-2" aria-hidden="true">↻</span>
            <span className="rounded bg-rose-100 dark:bg-rose-900/40 text-rose-800 dark:text-rose-300 px-2 py-0.5 font-mono">RSI</span>
          </div>
        </div>

        <p className="mt-4 text-xs text-muted-foreground">
          Three structural-coherence gates (manifest-drift) and a Jaccard
          novelty gate run between stages. Every step is logged, audited,
          and surfaced on the paper detail page.
        </p>
      </section>

      <Separator className="my-6" />

      {/* 1. Mission */}
      <section id="mission" className="mb-10 scroll-mt-20">
        <h2 className="text-2xl font-semibold mb-4">Mission</h2>
        <Card>
          <CardContent className="py-6">
            <p className="text-muted-foreground leading-relaxed">
              The system operates as an <strong>autonomous research infrastructure for AI governance</strong>.
              It produces submission-ready academic papers across 11 paper families,
              targeting specific flagship or elite field venues. The infrastructure
              enforces bounded roles, independent multi-layer review, source-level
              claim permissions, and family-local tournament benchmarking before
              selective public release.
            </p>
          </CardContent>
        </Card>
      </section>

      {/* 2. Paper Families */}
      <section id="families" className="mb-10 scroll-mt-20">
        <h2 className="text-2xl font-semibold mb-4">Paper Families</h2>
        <p className="text-muted-foreground mb-4">
          Work is organized into 11 paper families. Each family specifies a lock protocol
          that constrains how papers are designed and targeted.
        </p>
        <div className="grid gap-4 md:grid-cols-3">
          <Card>
            <CardHeader className="pb-2">
              <div className="flex items-center gap-2">
                <CardTitle className="text-base">Venue-Lock</CardTitle>
                <span className="inline-flex items-center rounded-md bg-purple-100 dark:bg-purple-900/40 px-1.5 py-0.5 text-[11px] font-semibold text-purple-700 dark:text-purple-300">
                  Protocol
                </span>
              </div>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">
                Paper design, framing, and methods are constrained by the requirements
                of a specific target journal. The venue is fixed before drafting begins.
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <div className="flex items-center gap-2">
                <CardTitle className="text-base">Method-Lock</CardTitle>
                <span className="inline-flex items-center rounded-md bg-blue-100 dark:bg-blue-900/40 px-1.5 py-0.5 text-[11px] font-semibold text-blue-700 dark:text-blue-300">
                  Protocol
                </span>
              </div>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">
                The methodological approach is fixed (e.g., QCA, regression discontinuity).
                The target venue may vary by topic within the family.
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <div className="flex items-center gap-2">
                <CardTitle className="text-base">Open</CardTitle>
                <span className="inline-flex items-center rounded-md bg-green-100 dark:bg-green-900/40 px-1.5 py-0.5 text-[11px] font-semibold text-green-700 dark:text-green-300">
                  Protocol
                </span>
              </div>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">
                Flexible venue targeting and method selection. Suitable for exploratory
                or cross-cutting research that does not fit a single venue profile.
              </p>
            </CardContent>
          </Card>
        </div>
        <p className="mt-4 text-sm text-muted-foreground">
          Each family also defines: canonical questions, accepted methods, mandatory checks,
          fatal failure conditions, an elite ceiling, and a maximum portfolio share.
        </p>
      </section>

      {/* 3. Pipeline */}
      <section id="pipeline" className="mb-10 scroll-mt-20">
        <h2 className="text-2xl font-semibold mb-4">7-Role Bounded Pipeline</h2>
        <p className="text-muted-foreground mb-4">
          Each paper is produced through seven bounded Claude roles. Each role has a
          defined scope and cannot operate outside its boundaries.
        </p>
        <div className="space-y-3">
          {[
            {
              role: "Scout",
              desc: "Identifies research opportunities, gaps in literature, and promising data sources for each family.",
            },
            {
              role: "Designer",
              desc: "Produces a research design locked to the family protocol -- specifying identification strategy, data requirements, and expected contribution.",
            },
            {
              role: "Data Steward",
              desc: "Fetches real data from source-card approved sources. No fabrication or simulation. Enforces claim-permission profiles.",
            },
            {
              role: "Analyst",
              desc: "Implements the identification strategy in code (R or Python). Produces robustness checks and sensitivity analyses.",
            },
            {
              role: "Drafter",
              desc: "Composes the manuscript following venue-specific formatting, style, and structural requirements.",
            },
            {
              role: "Verifier",
              desc: "Runs all mandatory checks for the family. Validates provenance, reproducibility, and claim-source alignment.",
            },
            {
              role: "Packager",
              desc: "Prepares the final submission package: LaTeX compilation, supplementary materials, cover letter, and disclosure statements.",
            },
          ].map((item, i) => (
            <div key={item.role} className="flex gap-4 items-start">
              <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground text-sm font-bold">
                {i + 1}
              </span>
              <div>
                <h3 className="font-semibold">{item.role}</h3>
                <p className="text-sm text-muted-foreground">{item.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* 4. Review Architecture */}
      <section id="review" className="mb-10 scroll-mt-20">
        <h2 className="text-2xl font-semibold mb-4">5-Layer Independent Review</h2>
        <p className="text-muted-foreground mb-4">
          Every paper passes through five independent review layers before entering the
          tournament. Each layer can kill a paper or force revision.
        </p>
        <div className="space-y-3">
          {[
            {
              layer: "L1 Structural Review",
              desc: "Checks completeness, formatting, section structure, and basic academic standards. Automated gate.",
            },
            {
              layer: "L2 Provenance Review",
              desc: "Verifies every data claim against source cards. Ensures no claim exceeds the source's permission profile.",
            },
            {
              layer: "L3 Method / Non-Claude Review",
              desc: "Independent methodological review by a non-Claude model or human expert. Checks identification strategy validity.",
            },
            {
              layer: "L4 Adversarial Review",
              desc: "Deliberately attempts to break the paper — find fatal flaws, p-hacking, specification errors, or unsupported claims.",
            },
            {
              layer: "L5 Human Escalation",
              desc: "Papers flagged by any prior layer are escalated for human review. Humans make final kill/revise/pass decisions.",
            },
          ].map((item, i) => (
            <div key={item.layer} className="flex gap-4 items-start">
              <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-secondary text-secondary-foreground text-sm font-bold">
                L{i + 1}
              </span>
              <div>
                <h3 className="font-semibold">{item.layer}</h3>
                <p className="text-sm text-muted-foreground">{item.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* 5. Tournament */}
      <section id="tournament" className="mb-10 scroll-mt-20">
        <h2 className="text-2xl font-semibold mb-4">Family-Local Tournament</h2>
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Family-Scoped Benchmarking</CardTitle>
              <CardDescription>
                Papers compete only within their family against established benchmarks.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">
                Each family maintains its own leaderboard. Papers are matched against
                peer-reviewed publications from the same domain. This ensures
                family-specific quality standards are maintained.
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Position-Swapped Judging</CardTitle>
              <CardDescription>
                Each comparison runs twice with papers in reversed order.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">
                Both rounds must agree on a winner for a decisive result. If they
                disagree, the match is declared a draw. This eliminates LLM positional
                bias. The judge model is deliberately chosen from a different provider.
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">TrueSkill Rating</CardTitle>
              <CardDescription>
                Bayesian rating: conservative score = μ − 3σ.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground mb-2">
                <strong>TrueSkill</strong> is a Bayesian rating system originally developed
                by Microsoft Research. Each paper has a skill estimate as a Gaussian
                distribution: <strong>μ (mu)</strong> is the mean skill, <strong>σ (sigma)</strong>
                is the uncertainty. The <strong>conservative rating</strong>{" "}
                <code className="text-xs bg-muted px-1 py-0.5 rounded">μ − 3σ</code>{" "}
                is the worst-case skill estimate at 99.7% confidence — it rewards
                consistency over luck.
              </p>
              <p className="text-sm text-muted-foreground">
                Papers must demonstrate consistent performance across multiple matches.
                High σ (few matches) penalizes the conservative rating, preventing
                lucky single victories from dominating rankings.
              </p>
            </CardContent>
          </Card>
        </div>
      </section>

      {/* 6. Source Architecture */}
      <section id="sources" className="mb-10 scroll-mt-20">
        <h2 className="text-2xl font-semibold mb-4">Source Architecture</h2>
        <p className="text-muted-foreground mb-4">
          Every data source is registered as a source card with explicit claim-permission
          profiles.
        </p>
        <div className="grid gap-4 md:grid-cols-3">
          <Card>
            <CardHeader className="pb-2">
              <div className="flex items-center gap-2">
                <CardTitle className="text-base">Tier A</CardTitle>
                <span className="inline-flex items-center rounded-md bg-emerald-100 dark:bg-emerald-900/40 px-1.5 py-0.5 text-[11px] font-semibold text-emerald-700 dark:text-emerald-300">
                  High Trust
                </span>
              </div>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">
                Official government databases, central bank releases, and verified
                academic datasets. Broad claim permissions with few restrictions.
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <div className="flex items-center gap-2">
                <CardTitle className="text-base">Tier B</CardTitle>
                <span className="inline-flex items-center rounded-md bg-blue-100 dark:bg-blue-900/40 px-1.5 py-0.5 text-[11px] font-semibold text-blue-700 dark:text-blue-300">
                  Standard
                </span>
              </div>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">
                Reputable NGO data, industry reports, and well-maintained open datasets.
                Moderate claim permissions with specific restrictions noted.
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <div className="flex items-center gap-2">
                <CardTitle className="text-base">Tier C</CardTitle>
                <span className="inline-flex items-center rounded-md bg-amber-100 dark:bg-amber-900/40 px-1.5 py-0.5 text-[11px] font-semibold text-amber-700 dark:text-amber-300">
                  Restricted
                </span>
              </div>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">
                Web-scraped data, social media APIs, and crowd-sourced collections.
                Narrow claim permissions with extensive known traps documented.
              </p>
            </CardContent>
          </Card>
        </div>
      </section>

      {/* 7. Release Pipeline */}
      <section id="release" className="mb-10 scroll-mt-20">
        <h2 className="text-2xl font-semibold mb-4">Selective Public Release</h2>
        <p className="text-muted-foreground mb-4">
          Papers move through four release stages. Not all papers reach public status.
          Tournament rankings serve as advisory signals, not hard gates. A human
          Significance Memo is required before any paper advances to submission.
        </p>
        <div className="space-y-3">
          {[
            {
              stage: "Internal",
              desc: "Working drafts visible only within the system. Subject to revision and may be killed at any point.",
            },
            {
              stage: "Candidate",
              desc: "Passed all five review layers. Tournament benchmark is advisory (includes rank + 95% confidence interval). Ready for human editorial review.",
            },
            {
              stage: "Submitted",
              desc: "Requires a human-authored Significance Memo with one of three verdicts before advancing — Submit (paper is venue-fit, policy-relevant, evidence-strong; advances to peer review), Hold (revisions required before resubmission), or Reject (kill for publication). Once Submit is recorded, the paper is sent to a target venue under embargo.",
            },
            {
              stage: "Public",
              desc: "Published or accepted. Available for citation and public access with full provenance trail. Subject to corrections policy.",
            },
          ].map((item, i) => (
            <div key={item.stage} className="flex gap-4 items-start">
              <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground text-sm font-bold">
                {i + 1}
              </span>
              <div>
                <h3 className="font-semibold">{item.stage}</h3>
                <p className="text-sm text-muted-foreground">{item.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* 8. Manifest-Drift Detection */}
      <section id="drift" className="mb-10 scroll-mt-20">
        <h2 className="text-2xl font-semibold mb-4">Manifest-Drift Detection</h2>
        <p className="text-muted-foreground mb-4">
          <strong>Manifest drift</strong> occurs when a paper silently deviates from
          its locked design — for example, the Analyst uses different methods than the
          Designer specified, or the Drafter makes claims the analysis doesn&apos;t
          support. Drift is the autonomous research equivalent of scope creep: small
          local choices that compound into a paper that no longer matches its plan.
          Three structural coherence gates prevent this by verifying alignment before
          each downstream role can proceed.
        </p>
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Design-Data Coherence</CardTitle>
              <CardDescription>Pre-analysis gate</CardDescription>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">
                Verifies the locked design&apos;s data sources are non-empty and structurally
                valid before the Analyst role can begin. Prevents analysis on
                under-specified designs.
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Analysis-Design Alignment</CardTitle>
              <CardDescription>Pre-drafting gate</CardDescription>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">
                Confirms the design specifies expected outputs and that the paper has
                actually completed analysis before drafting begins. Blocks premature
                drafting.
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Claims-Analysis Alignment</CardTitle>
              <CardDescription>Pre-packaging gate</CardDescription>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">
                Checks that claim-map entries link to source cards or analysis results.
                If the linked ratio falls below the drift threshold (default 0.8), the
                paper is blocked from packaging. Prevents orphaned claims.
              </p>
            </CardContent>
          </Card>
        </div>
      </section>

      {/* 9. Reliability Framework */}
      <section id="reliability" className="mb-10 scroll-mt-20">
        <h2 className="text-2xl font-semibold mb-4">Reliability Framework</h2>
        <p className="text-muted-foreground mb-4">
          Five quantitative metrics are tracked per paper and aggregated per family.
          Each metric is compared against configurable thresholds.
        </p>
        <div className="grid gap-4 md:grid-cols-3">
          {[
            {
              metric: "Replication Rate",
              desc: "Fraction of review layers that passed on the first attempt. Measures first-time-right quality.",
            },
            {
              metric: "Manifest Fidelity",
              desc: "Lock hash verification. Confirms the paper's design artifact has not been tampered with since locking.",
            },
            {
              metric: "Expert Score",
              desc: "Average overall score from external expert reviews (1-5 scale). Measures domain-expert validation.",
            },
            {
              metric: "Benchmark Percentile",
              desc: "Paper's rank position relative to all papers in its family. Derived from tournament results.",
            },
            {
              metric: "Correction Rate",
              desc: "Number of post-publication corrections (errata, retractions, updates). Lower is better.",
            },
          ].map((item) => (
            <Card key={item.metric}>
              <CardHeader className="pb-2">
                <CardTitle className="text-base">{item.metric}</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground">{item.desc}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      </section>

      {/* 10. Failure Taxonomy */}
      <section id="failures" className="mb-10 scroll-mt-20">
        <h2 className="text-2xl font-semibold mb-4">Failure Taxonomy</h2>
        <p className="text-muted-foreground mb-4">
          Every review failure is auto-classified into a systematic taxonomy to enable
          institutional learning. Failures are categorized by type, severity, and
          detection stage.
        </p>
        <div className="grid gap-4 md:grid-cols-4">
          {[
            { type: "Data Error", desc: "Missing, stale, or mislinked data sources" },
            { type: "Logic Error", desc: "Flawed reasoning or identification strategy" },
            { type: "Hallucination", desc: "Claims not grounded in source material" },
            { type: "Causal Overreach", desc: "Causal language without causal protocol" },
            { type: "Source Drift", desc: "Claim exceeds source permission profile" },
            { type: "Design Violation", desc: "Output deviates from locked design" },
            { type: "Formatting", desc: "Structure, style, or venue requirement issues" },
            { type: "Other", desc: "Uncategorized failures for manual review" },
          ].map((item) => (
            <Card key={item.type}>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm">{item.type}</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-xs text-muted-foreground">{item.desc}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      </section>

      {/* 11. Novelty Detection */}
      <section id="novelty" className="mb-10 scroll-mt-20">
        <h2 className="text-2xl font-semibold mb-4">Novelty Detection</h2>
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Structural Similarity Gate</CardTitle>
              <CardDescription>
                Prevents derivative work from entering the pipeline
              </CardDescription>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground mb-3">
                After a paper&apos;s design is locked, a novelty check compares its research
                questions, data sources, and methods against all same-family papers using
                Jaccard similarity. Each paper receives one of three verdicts:
              </p>
              <ul className="text-sm text-muted-foreground space-y-1 ml-4 mb-3">
                <li>
                  <strong className="text-emerald-700 dark:text-emerald-400">Novel</strong>{" "}
                  (similarity &lt; 0.3) — distinct contribution, proceeds freely.
                </li>
                <li>
                  <strong className="text-amber-700 dark:text-amber-400">Marginal</strong>{" "}
                  (0.3–0.6) — overlapping with prior work, proceeds with a warning label.
                </li>
                <li>
                  <strong className="text-red-700 dark:text-red-400">Derivative</strong>{" "}
                  (≥ 0.6) — too similar to existing papers, blocked from advancing.
                </li>
              </ul>
              <p className="text-sm text-muted-foreground">
                This ensures each paper makes a distinct contribution within its family.
              </p>
            </CardContent>
          </Card>
        </div>
      </section>

      {/* 12. Post-Pipeline Tracking */}
      <section id="post-pipeline" className="mb-10 scroll-mt-20">
        <h2 className="text-2xl font-semibold mb-4">Post-Pipeline Tracking</h2>
        <p className="text-muted-foreground mb-4">
          The system tracks what happens after papers leave the factory, feeding
          outcomes back into reliability metrics and institutional learning.
        </p>
        <div className="grid gap-4 md:grid-cols-3">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base">Submission Outcomes</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">
                Tracks venue decisions (desk reject, R&R, accepted, rejected),
                revision rounds, and reviewer feedback. Computes acceptance rates
                per family and venue.
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base">Corrections Policy</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">
                Post-publication errata, retractions, and updates are recorded
                with affected claims. Correction rates feed into the reliability
                framework.
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base">Expert Validation</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">
                External domain experts provide scored reviews (methodology,
                contribution, overall) that feed into the reliability framework&apos;s
                expert score metric.
              </p>
            </CardContent>
          </Card>
        </div>
      </section>

      {/* 13. Governance */}
      <section id="governance" className="mb-10 scroll-mt-20">
        <h2 className="text-2xl font-semibold mb-4">Governance & Disclosure</h2>
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Per-Paper Autonomy Cards</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">
                Every paper carries an <strong>autonomy card</strong> tracking which
                of the 7 pipeline roles were <em>fully automated</em>,{" "}
                <em>supervised</em> (human in the loop), or <em>human-driven</em>{" "}
                (no AI). The <strong>autonomy score</strong> is the fraction of roles
                that ran fully automated — a score of <code className="text-xs bg-muted px-1 py-0.5 rounded">0.71</code>{" "}
                means 5 of 7 roles were AI-driven end-to-end. The score is published
                alongside each paper so reviewers can calibrate trust against the
                actual level of automation; family-level aggregates show automation
                patterns across the portfolio.
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Cohort-Adjusted Metrics</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">
                Papers are tagged with their generation cohort (quarter + model version).
                This enables cross-era comparison of quality metrics, ensuring that
                improvements in AI capabilities are tracked and that earlier papers are
                evaluated fairly against their contemporaries.
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Human-Only Authorship</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">
                All papers list human authors only. AI systems (Claude and others) are
                credited as tools in the methodology section, not as co-authors. This
                follows current journal policies and academic norms.
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle className="text-base">AI Contribution Disclosure</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">
                Every paper includes a standardized AI contribution statement specifying
                which pipeline roles were performed by AI systems, which review layers
                involved non-AI checks, and what human oversight was applied. Full
                provenance trails are maintained and available on request.
              </p>
            </CardContent>
          </Card>
        </div>
      </section>

      {/* 14. Collegial Review Loop */}
      <section id="collegial" className="mb-10 scroll-mt-20">
        <h2 className="text-2xl font-semibold mb-4">
          Collegial Review Loop (Convergence-Based)
        </h2>
        <p className="text-muted-foreground mb-6">
          Between drafting and verification sits pipeline stage 5.5: a
          convergence-based collegial review. Rather than a single review pass,
          three specialized colleague agents iterate with the Drafter until the
          manuscript reaches venue-ready quality — mirroring how human
          researchers refine papers through rounds of collegial feedback before
          submission.
        </p>

        <h3 className="text-lg font-semibold mb-3">
          Three Colleague Perspectives
        </h3>
        <div className="grid gap-4 md:grid-cols-3 mb-6">
          <Card>
            <CardHeader className="pb-2">
              <div className="flex items-center gap-2">
                <CardTitle className="text-base">Dr. Methods</CardTitle>
                <span className="inline-flex items-center rounded-md bg-blue-100 dark:bg-blue-900/40 px-1.5 py-0.5 text-[11px] font-semibold text-blue-700 dark:text-blue-300">
                  Methodology
                </span>
              </div>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">
                Evaluates identification strategy, robustness of methods,
                statistical validity, and methodological transparency. Ensures
                the paper&apos;s analytical approach meets venue standards.
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <div className="flex items-center gap-2">
                <CardTitle className="text-base">Prof. Domain</CardTitle>
                <span className="inline-flex items-center rounded-md bg-emerald-100 dark:bg-emerald-900/40 px-1.5 py-0.5 text-[11px] font-semibold text-emerald-700 dark:text-emerald-300">
                  Domain Expertise
                </span>
              </div>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">
                Assesses domain-specific contribution, literature engagement,
                theoretical grounding, and policy relevance. Ensures the paper
                advances the state of knowledge in its field.
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <div className="flex items-center gap-2">
                <CardTitle className="text-base">Editor Chen</CardTitle>
                <span className="inline-flex items-center rounded-md bg-purple-100 dark:bg-purple-900/40 px-1.5 py-0.5 text-[11px] font-semibold text-purple-700 dark:text-purple-300">
                  Venue Strategy
                </span>
              </div>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">
                Reviews framing, positioning, argument flow, and alignment with
                the target venue&apos;s editorial preferences. Ensures the paper is
                strategically crafted for its intended audience.
              </p>
            </CardContent>
          </Card>
        </div>

        <h3 className="text-lg font-semibold mb-3">Convergence Protocol</h3>
        <div className="space-y-3 mb-6">
          {[
            {
              step: "Round 1 — Full Feedback",
              desc: "All three colleagues provide comprehensive feedback across their domains. The Drafter incorporates suggestions, then a quality assessment scores the revised manuscript.",
            },
            {
              step: "Round 2+ — Targeted Feedback",
              desc: "Colleagues focus only on remaining gaps and unresolved issues from prior rounds. The Drafter incorporates targeted suggestions, then a new quality assessment is produced.",
            },
            {
              step: "Convergence Check",
              desc: "The loop exits via one of three paths, each with different downstream consequences: Converged (all five dimensions score ≥ 7/10) — paper is submission-ready and advances; Plateaued (scores stop improving across consecutive rounds) — paper requires human edits before it can advance; Max Rounds (default 5) — paper escalates to a human reviewer for an explicit submit/hold decision.",
            },
          ].map((item, i) => (
            <div key={item.step} className="flex gap-4 items-start">
              <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground text-sm font-bold">
                {i + 1}
              </span>
              <div>
                <h3 className="font-semibold">{item.step}</h3>
                <p className="text-sm text-muted-foreground">{item.desc}</p>
              </div>
            </div>
          ))}
        </div>

        <h3 className="text-lg font-semibold mb-3">
          Quality Assessment Dimensions
        </h3>
        <div className="grid gap-4 md:grid-cols-3 mb-6">
          {[
            {
              dimension: "Methodology Rigor",
              desc: "Soundness of research design, identification strategy, and analytical methods. Scored 1-10.",
            },
            {
              dimension: "Contribution Clarity",
              desc: "How clearly the paper articulates its novel contribution relative to existing literature. Scored 1-10.",
            },
            {
              dimension: "Literature Engagement",
              desc: "Depth and accuracy of engagement with relevant prior work and theoretical foundations. Scored 1-10.",
            },
            {
              dimension: "Argument Coherence",
              desc: "Logical flow from research question through evidence to conclusions, without gaps or contradictions. Scored 1-10.",
            },
            {
              dimension: "Venue Fit",
              desc: "Alignment with the target venue&apos;s scope, methods preferences, and editorial standards. Scored 1-10.",
            },
          ].map((item) => (
            <Card key={item.dimension}>
              <CardHeader className="pb-2">
                <CardTitle className="text-base">{item.dimension}</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground">{item.desc}</p>
              </CardContent>
            </Card>
          ))}
        </div>

        <Card>
          <CardContent className="py-6">
            <p className="text-muted-foreground leading-relaxed">
              <strong>Editorial Agency:</strong> The Drafter retains full
              editorial control throughout the collegial review. For each
              suggestion, the Drafter explicitly accepts, rejects, or partially
              incorporates with stated reasoning — ensuring a coherent
              authorial voice rather than design-by-committee. All colleague
              contributions are tracked and acknowledged in the final
              manuscript&apos;s acknowledgments section.
            </p>
          </CardContent>
        </Card>
      </section>

      {/* 15. Recursive Self-Improvement (RSI) */}
      <section id="rsi" className="mb-10 scroll-mt-20">
        <h2 className="text-2xl font-semibold mb-4">
          Recursive Self-Improvement (RSI)
        </h2>
        <p className="text-muted-foreground mb-4">
          The factory doesn&apos;t just produce papers — it improves itself.
          Every paper&apos;s outcomes, review failures, and tournament results
          feed back into a four-tier improvement system. The tiers are{" "}
          <strong>nested</strong>: each tier consumes signals from the tier
          below it, escalating from prompt-level fixes up to pipeline
          architecture, with safety guards at every level.
        </p>
        <ul className="text-sm text-muted-foreground space-y-1 ml-4 mb-6 list-disc">
          <li>
            <strong>Tier 1 — Prompts:</strong> tunes individual role prompts
            based on per-role failure patterns.
          </li>
          <li>
            <strong>Tier 2 — Configs:</strong> when prompt fixes plateau,
            adjusts family-level configs (thresholds, judge calibration).
          </li>
          <li>
            <strong>Tier 3 — Architecture:</strong> when config tuning is
            insufficient, restructures pipeline stages or adds new ones.
          </li>
          <li>
            <strong>Tier 4 — Meta:</strong> reflects on whether the taxonomy
            itself is fit for purpose; can propose new families or retire
            stagnant ones.
          </li>
        </ul>

        <div className="grid gap-4 md:grid-cols-2 mb-6">
          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300 text-xs font-bold">
                  1
                </span>
                <CardTitle className="text-base">Prompt Evolution</CardTitle>
              </div>
              <CardDescription>
                Fine-grained tuning of agent instructions
              </CardDescription>
            </CardHeader>
            <CardContent>
              <ul className="text-sm text-muted-foreground space-y-1 list-disc list-inside">
                <li>Role prompt optimization based on failure patterns</li>
                <li>
                  Review layer accuracy tuning (precision / recall / F1)
                </li>
                <li>Policy-usefulness dimension calibration</li>
              </ul>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-emerald-100 dark:bg-emerald-900/40 text-emerald-700 dark:text-emerald-300 text-xs font-bold">
                  2
                </span>
                <CardTitle className="text-base">
                  Configuration Evolution
                </CardTitle>
              </div>
              <CardDescription>
                System-wide parameter optimization
              </CardDescription>
            </CardHeader>
            <CardContent>
              <ul className="text-sm text-muted-foreground space-y-1 list-disc list-inside">
                <li>
                  Family config optimization (venue ladders, method promotion)
                </li>
                <li>
                  Drift-threshold auto-tuning (too strict blocks progress; too
                  lenient leaks failures)
                </li>
                <li>Tournament judge calibration</li>
              </ul>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-purple-100 dark:bg-purple-900/40 text-purple-700 dark:text-purple-300 text-xs font-bold">
                  3
                </span>
                <CardTitle className="text-base">
                  Pipeline Architecture
                </CardTitle>
              </div>
              <CardDescription>
                Structural changes to the production pipeline
              </CardDescription>
            </CardHeader>
            <CardContent>
              <ul className="text-sm text-muted-foreground space-y-1 list-disc list-inside">
                <li>
                  Review layer bypass / shadow mode (if a layer adds no signal,
                  shadow it)
                </li>
                <li>Role boundary splitting and merging</li>
                <li>Family discovery from killed idea clusters</li>
              </ul>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-amber-100 dark:bg-amber-900/40 text-amber-700 dark:text-amber-300 text-xs font-bold">
                  4
                </span>
                <CardTitle className="text-base">Meta-Learning</CardTitle>
              </div>
              <CardDescription>
                Self-reflective system-level improvement
              </CardDescription>
            </CardHeader>
            <CardContent>
              <ul className="text-sm text-muted-foreground space-y-1 list-disc list-inside">
                <li>
                  Failure taxonomy expansion (auto-cluster &quot;other&quot;
                  failures into new types)
                </li>
                <li>Cross-cohort improvement targeting</li>
                <li>
                  Meta-pipeline cycle: Observe, Propose, Shadow, Evaluate,
                  Promote, Recurse
                </li>
              </ul>
            </CardContent>
          </Card>
        </div>

        <h3 className="text-lg font-semibold mb-3">Safety Architecture</h3>
        <div className="grid gap-4 md:grid-cols-3">
          <Card>
            <CardHeader className="pb-2">
              <div className="flex items-center gap-2">
                <CardTitle className="text-base">Experiment Tracking</CardTitle>
                <span className="inline-flex items-center rounded-md bg-blue-100 dark:bg-blue-900/40 px-1.5 py-0.5 text-[11px] font-semibold text-blue-700 dark:text-blue-300">
                  Guard
                </span>
              </div>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">
                Every RSI change is logged as a formal experiment with A/B
                cohort comparison. Control and treatment cohorts run in parallel
                with identical inputs to measure true impact.
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <div className="flex items-center gap-2">
                <CardTitle className="text-base">Shadow Mode</CardTitle>
                <span className="inline-flex items-center rounded-md bg-emerald-100 dark:bg-emerald-900/40 px-1.5 py-0.5 text-[11px] font-semibold text-emerald-700 dark:text-emerald-300">
                  Guard
                </span>
              </div>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">
                All proposed changes run in shadow mode before promotion to
                production. Shadow results are compared against the current
                production baseline with no impact on live outputs.
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <div className="flex items-center gap-2">
                <CardTitle className="text-base">Auto-Rollback Gate</CardTitle>
                <span className="inline-flex items-center rounded-md bg-red-100 dark:bg-red-900/40 px-1.5 py-0.5 text-[11px] font-semibold text-red-700 dark:text-red-300">
                  Guard
                </span>
              </div>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">
                If any promoted change causes greater than 10% degradation in
                key metrics, the system automatically rolls back to the
                previous configuration. No human intervention required for
                safety-critical reversions.
              </p>
            </CardContent>
          </Card>
        </div>
      </section>
    </div>
  );
}
