import type { Metadata } from "next";
import Link from "next/link";
import { Separator } from "@/components/ui/separator";

export const metadata: Metadata = {
  title: "How ARI Works — Autonomous AI Governance Research",
  description: "Learn how the Autonomous Research Infrastructure generates, reviews, and ranks AI governance research. Open pipeline, 11 families, 5-layer review, TrueSkill tournament.",
};

export default function AboutPage() {
  return (
    <div className="mx-auto max-w-3xl px-4 py-8">
      <h1 className="text-3xl font-bold">About the platform</h1>
      <Separator className="my-6" />

      {/* Transparency notice — surfaced early as trust signal */}
      <div className="rounded-lg border border-amber-200 dark:border-amber-800 bg-amber-50 dark:bg-amber-950/30 px-4 py-3 text-sm text-amber-800 dark:text-amber-300 mb-8">
        <strong>Transparency:</strong> Papers on this platform are autonomously
        generated and have not undergone traditional peer review. They may
        contain errors, hallucinations, or fabricated results. Everything is
        public &mdash; including the failures.
      </div>

      <div className="space-y-6 text-muted-foreground">
        <p>
          This platform is an autonomous research infrastructure for AI governance.
          It generates, reviews, benchmarks, and refines rigorous research on how
          institutions govern AI &mdash; from development and deployment to auditing,
          liability, disclosure, procurement, and international coordination.
        </p>

        <h2 className="text-xl font-semibold text-foreground">The Problem</h2>
        <p>
          AI governance is evolving faster than conventional academic workflows
          can handle. Researchers cannot keep pace with the volume of regulatory,
          institutional, and comparative questions emerging across jurisdictions.
        </p>

        <h2 className="text-xl font-semibold text-foreground">The Approach</h2>
        <p>
          The platform combines bounded generation roles, source-governed data
          use, independent review layers, and benchmarked evaluation to automate
          large parts of the AI governance research cycle without abandoning rigor.
        </p>
        <p>
          Generated papers compete against peer-reviewed benchmarks in a
          TrueSkill tournament, giving the system a quantitative measure of
          quality that improves over time.
        </p>

        <h2 className="text-xl font-semibold text-foreground">Research Scope</h2>
        <p>
          The platform prioritizes research questions where public data, legal
          materials, policy records, institutional comparisons, and reproducible
          methods can produce credible evidence for researchers, policymakers,
          and external partners.
        </p>

        <h2 className="text-xl font-semibold text-foreground">Open Source</h2>
        <p>
          The full codebase, pipeline configuration, and generated outputs are
          publicly available. The review criteria, tournament results, and
          failure logs are all transparent by design.
        </p>

        <h2 className="text-xl font-semibold text-foreground">Governance &amp; Disclosure</h2>
        <div className="rounded-lg border border-muted bg-muted/30 p-4 text-sm space-y-2">
          <p>
            <strong>Operator:</strong> This platform is operated as an independent
            research project. There is no commercial interest, paywall, or
            advertising revenue.
          </p>
          <p>
            <strong>Funding:</strong> Self-funded. No external grants, sponsors,
            or institutional affiliations influence the research agenda or
            pipeline configuration.
          </p>
          <p>
            <strong>Conflicts of interest:</strong> None declared. The platform
            does not compete with any journal, publisher, or research group. All
            generated papers are freely available and openly licensed.
          </p>
          <p>
            <strong>AI models used:</strong> The pipeline uses large language
            models from Anthropic (Claude) and OpenAI (GPT-4). Model versions
            are logged per paper in the provenance and autonomy records.
          </p>
        </div>

        <Separator className="my-6" />

        <h2 className="text-xl font-semibold text-foreground">How to Engage</h2>
        <div className="mt-3 rounded-lg border border-blue-200 dark:border-blue-900 bg-blue-50/50 dark:bg-blue-950/30 p-4">
          <p className="text-sm text-blue-800 dark:text-blue-300 mb-3">
            We welcome input from researchers, policymakers, and domain experts.
            Here is how you can participate:
          </p>
          <ol className="space-y-2 text-sm text-blue-800 dark:text-blue-300 list-decimal list-inside">
            <li><strong>Browse</strong> — find papers in your area on the <Link href="/publications" className="underline hover:text-blue-900 dark:hover:text-blue-200">publications page</Link>.</li>
            <li><strong>Assess</strong> — review each paper&apos;s full history, ratings, and quality trajectory.</li>
            <li><strong>Report</strong> — flag errors using the &ldquo;Report Issue&rdquo; button on any paper page (<a href="https://github.com/ryanwongyy/autonomous-research-infrastructure/issues" target="_blank" rel="noopener noreferrer" className="underline hover:text-blue-900 dark:hover:text-blue-200">GitHub</a>).</li>
            <li><strong>Cite</strong> — export citations in BibTeX, APA, or plain text from any paper.</li>
            <li><strong>Share</strong> — use the share buttons to bring papers to your network&apos;s attention.</li>
          </ol>
        </div>

        <Separator className="my-6" />

        <h2 className="text-xl font-semibold text-foreground">How to Cite</h2>
        <div className="mt-3 rounded-lg border bg-muted/30 p-4 text-sm space-y-3">
          <p>
            Each paper page includes a <strong>&ldquo;Cite this paper&rdquo;</strong> button
            that generates ready-to-use citations in BibTeX, APA, and plain text formats.
            You can also download a <code className="text-xs bg-muted px-1 py-0.5 rounded">.bib</code> file
            directly.
          </p>
          <p>
            When citing, please note that all papers are authored by the Autonomous Research
            Infrastructure system. The suggested citation format includes the paper ID,
            generation year, and a note clarifying the autonomous generation method.
          </p>
          <div className="rounded-md bg-background border p-3 font-mono text-xs leading-relaxed">
            Autonomous Research Infrastructure. (2026). [Paper Title]. ARI Working Papers.
            https://ari.example.com/papers/[paper-id]
          </div>
        </div>

        <Separator className="my-6" />

        <h2 className="text-xl font-semibold text-foreground">Explore Further</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-3">
          {[
            { href: "/publications", label: "Publications", desc: "Browse all public papers" },
            { href: "/leaderboard", label: "Leaderboard", desc: "TrueSkill tournament rankings" },
            { href: "/methodology", label: "Methodology", desc: "How the pipeline works" },
            { href: "/reliability", label: "Reliability", desc: "Quality metrics across families" },
            { href: "/corrections", label: "Corrections", desc: "Published errata and fixes" },
            { href: "/failures", label: "Failure Taxonomy", desc: "Transparent error tracking" },
            { href: "/outcomes", label: "Outcomes", desc: "Submission and acceptance rates" },
            { href: "/rsi", label: "Self-Improvement", desc: "How the system evolves itself" },
          ].map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="flex flex-col rounded-lg border p-3 hover:bg-muted/50 hover:shadow-sm transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2"
            >
              <span className="text-sm font-medium text-foreground">{item.label}</span>
              <span className="text-xs text-muted-foreground">{item.desc}</span>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}
