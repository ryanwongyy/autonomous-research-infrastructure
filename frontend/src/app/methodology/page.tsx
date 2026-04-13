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

      <Separator className="my-6" />

      {/* 1. Mission */}
      <section className="mb-10">
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
      <section className="mb-10">
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
                <span className="inline-flex items-center rounded-md bg-purple-100 dark:bg-purple-900/40 px-1.5 py-0.5 text-[10px] font-semibold text-purple-700 dark:text-purple-300">
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
                <span className="inline-flex items-center rounded-md bg-blue-100 dark:bg-blue-900/40 px-1.5 py-0.5 text-[10px] font-semibold text-blue-700 dark:text-blue-300">
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
                <span className="inline-flex items-center rounded-md bg-green-100 dark:bg-green-900/40 px-1.5 py-0.5 text-[10px] font-semibold text-green-700 dark:text-green-300">
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
      <section className="mb-10">
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
      <section className="mb-10">
        <h2 className="text-2xl font-semibold mb-4">5-Layer Independent Review</h2>
        <p className="text-muted-foreground mb-4">
          Every paper passes through five independent review layers before entering the
          tournament. Each layer can kill a paper or force revision.
        </p>
        <div className="space-y-3">
          {[
            {
              layer: "Layer 1: Structural Review",
              desc: "Checks completeness, formatting, section structure, and basic academic standards. Automated gate.",
            },
            {
              layer: "Layer 2: Provenance Review",
              desc: "Verifies every data claim against source cards. Ensures no claim exceeds the source's permission profile.",
            },
            {
              layer: "Layer 3: Method / Non-Claude Review",
              desc: "Independent methodological review by a non-Claude model or human expert. Checks identification strategy validity.",
            },
            {
              layer: "Layer 4: Adversarial Review",
              desc: "Deliberately attempts to break the paper -- find fatal flaws, p-hacking, specification errors, or unsupported claims.",
            },
            {
              layer: "Layer 5: Human Escalation",
              desc: "Papers flagged by any prior layer are escalated for human review. Humans make final kill/revise/pass decisions.",
            },
          ].map((item, i) => (
            <div key={item.layer} className="flex gap-4 items-start">
              <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-secondary text-secondary-foreground text-sm font-bold">
                {i + 1}
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
      <section className="mb-10">
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
                Bayesian rating: conservative score = mu - 3*sigma.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">
                Papers must demonstrate consistent performance across multiple matches.
                High uncertainty (sigma) penalizes papers with few comparisons, preventing
                lucky single victories from dominating rankings.
              </p>
            </CardContent>
          </Card>
        </div>
      </section>

      {/* 6. Source Architecture */}
      <section className="mb-10">
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
                <span className="inline-flex items-center rounded-md bg-emerald-100 dark:bg-emerald-900/40 px-1.5 py-0.5 text-[10px] font-semibold text-emerald-700 dark:text-emerald-300">
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
                <span className="inline-flex items-center rounded-md bg-blue-100 dark:bg-blue-900/40 px-1.5 py-0.5 text-[10px] font-semibold text-blue-700 dark:text-blue-300">
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
                <span className="inline-flex items-center rounded-md bg-amber-100 dark:bg-amber-900/40 px-1.5 py-0.5 text-[10px] font-semibold text-amber-700 dark:text-amber-300">
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
      <section className="mb-10">
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
              desc: "Requires a human-authored Significance Memo with 'submit' verdict before advancing. Submitted to a target venue under embargo.",
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
      <section className="mb-10">
        <h2 className="text-2xl font-semibold mb-4">Manifest-Drift Detection</h2>
        <p className="text-muted-foreground mb-4">
          Three structural coherence gates prevent silent drift between pipeline stages.
          Each gate verifies alignment before the downstream role can proceed.
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
      <section className="mb-10">
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
      <section className="mb-10">
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
      <section className="mb-10">
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
              <p className="text-sm text-muted-foreground">
                After a paper&apos;s design is locked, a novelty check compares its research
                questions, data sources, and methods against all same-family papers using
                Jaccard similarity. Papers scoring above the derivative threshold (0.6)
                are blocked from advancing. Marginal papers (0.3-0.6) proceed with a
                warning. This ensures each paper makes a distinct contribution within
                its family.
              </p>
            </CardContent>
          </Card>
        </div>
      </section>

      {/* 12. Post-Pipeline Tracking */}
      <section className="mb-10">
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
      <section className="mb-10">
        <h2 className="text-2xl font-semibold mb-4">Governance & Disclosure</h2>
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Per-Paper Autonomy Cards</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">
                Every paper carries an autonomy card tracking which of the 7 pipeline
                roles were fully automated, supervised, or human-driven. The overall
                autonomy score (fraction of full-auto roles) is published alongside
                each paper for transparency. Family-level aggregates show automation
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
      <section className="mb-10">
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
                <span className="inline-flex items-center rounded-md bg-blue-100 dark:bg-blue-900/40 px-1.5 py-0.5 text-[10px] font-semibold text-blue-700 dark:text-blue-300">
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
                <span className="inline-flex items-center rounded-md bg-emerald-100 dark:bg-emerald-900/40 px-1.5 py-0.5 text-[10px] font-semibold text-emerald-700 dark:text-emerald-300">
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
                <span className="inline-flex items-center rounded-md bg-purple-100 dark:bg-purple-900/40 px-1.5 py-0.5 text-[10px] font-semibold text-purple-700 dark:text-purple-300">
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
              desc: "The loop exits when: the manuscript is assessed as \"ready\" (all five quality dimensions score >= 7/10), the maximum round limit is reached (default 5 rounds), or quality scores plateau across consecutive rounds.",
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
      <section className="mb-10">
        <h2 className="text-2xl font-semibold mb-4">
          Recursive Self-Improvement (RSI)
        </h2>
        <p className="text-muted-foreground mb-6">
          The factory doesn&apos;t just produce papers — it improves itself.
          Every paper&apos;s outcomes, review failures, and tournament results
          feed back into a four-tier improvement system. Each tier operates at
          a different level of ambition, from fine-tuning individual prompts to
          restructuring the pipeline architecture itself.
        </p>

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
                <span className="inline-flex items-center rounded-md bg-blue-100 dark:bg-blue-900/40 px-1.5 py-0.5 text-[10px] font-semibold text-blue-700 dark:text-blue-300">
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
                <span className="inline-flex items-center rounded-md bg-emerald-100 dark:bg-emerald-900/40 px-1.5 py-0.5 text-[10px] font-semibold text-emerald-700 dark:text-emerald-300">
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
                <span className="inline-flex items-center rounded-md bg-red-100 dark:bg-red-900/40 px-1.5 py-0.5 text-[10px] font-semibold text-red-700 dark:text-red-300">
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
