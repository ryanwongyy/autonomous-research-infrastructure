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

      <div className="space-y-6 text-muted-foreground">
        <p>
          This platform is an autonomous research infrastructure for AI governance.
          It is designed to generate, review, benchmark, and refine rigorous
          research on how institutions govern AI development, deployment, auditing,
          liability, disclosure, procurement, and international coordination.
        </p>

        <h2 className="text-xl font-semibold text-foreground">The Problem</h2>
        <p>
          AI governance is moving faster than conventional academic workflows can
          handle. Human researchers cannot keep pace with the volume of regulatory,
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
          quality that can improve over time.
        </p>

        <h2 className="text-xl font-semibold text-foreground">Transparency</h2>
        <p>
          Everything is public: the papers, the code, the data, the failures.
          Generated papers may contain errors, hallucinations, or fabricated
          results. They have not undergone traditional peer review.
        </p>

        <h2 className="text-xl font-semibold text-foreground">Research scope</h2>
        <p>
          The current implementation is focused on AI governance. It prioritizes
          research questions where public data, legal materials, policy records,
          institutional comparisons, and reproducible methods can generate credible
          evidence for researchers, policymakers, and external partners.
        </p>
      </div>
    </div>
  );
}
