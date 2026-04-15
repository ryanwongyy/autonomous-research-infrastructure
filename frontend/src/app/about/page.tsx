import type { Metadata } from "next";
import { Separator } from "@/components/ui/separator";

export const metadata: Metadata = {
  title: "About",
  description: "Learn about the autonomous research infrastructure for AI governance — architecture, methodology, and operating model.",
};

export default function AboutPage() {
  return (
    <div className="mx-auto max-w-3xl px-4 py-8">
      <h1 className="text-3xl font-bold">About the platform</h1>
      <Separator className="my-6" />

      {/* Transparency notice — surfaced early as trust signal */}
      <div className="rounded-lg border border-amber-200 dark:border-amber-800 bg-amber-50/50 dark:bg-amber-950/20 px-4 py-3 text-sm text-amber-800 dark:text-amber-300 mb-8">
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
      </div>
    </div>
  );
}
