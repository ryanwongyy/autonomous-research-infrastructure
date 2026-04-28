import type { Metadata } from "next";
import Link from "next/link";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { serverFetch } from "@/lib/api";

export const metadata: Metadata = {
  title: "Corrections & Errata — Self-Correction Transparency",
  description: "Every error the system catches and fixes, published openly. Transparent correction tracking across 11 research families — proving autonomous research quality.",
};

interface CorrectionsDashboard {
  families: Array<{
    family_id: string;
    short_name: string;
    total_public_papers: number;
    total_corrections: number;
    correction_rate: number;
  }>;
}

export default async function CorrectionsPage() {
  let dashboard: CorrectionsDashboard | null = null;
  let apiError = false;

  try {
    dashboard = await serverFetch<CorrectionsDashboard>("/corrections/dashboard");
  } catch {
    apiError = true;
  }

  const totalPapers = dashboard?.families.reduce((sum, f) => sum + f.total_public_papers, 0) ?? 0;
  const totalCorrections = dashboard?.families.reduce((sum, f) => sum + f.total_corrections, 0) ?? 0;
  const overallRate = totalPapers > 0 ? totalCorrections / totalPapers : 0;

  if (!dashboard) {
    return (
      <div className="mx-auto max-w-5xl px-4 py-8">
        <h1 className="text-3xl font-bold">Corrections &amp; Errata</h1>
        <Separator className="my-6" />
        <Card className={apiError ? "border-amber-200 dark:border-amber-900" : ""}>
          <CardContent className="py-12 text-center text-muted-foreground">
            {apiError
              ? "Unable to connect to the API. Please try again later."
              : "No correction data available yet."}
            <div className="mt-4">
              <Link href="/" className="text-primary hover:underline text-sm">
                Back to Home
              </Link>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-5xl px-4 py-8">
      <h1 className="text-3xl font-bold">Corrections &amp; Errata</h1>
      <p className="mt-1 text-muted-foreground">
        Transparent tracking of self-corrections across all paper families. Every error the system catches and fixes is recorded here.
      </p>
      <Separator className="my-6" />

      {/* Transparency notice */}
      <div className="rounded-lg border border-amber-200 dark:border-amber-800 bg-amber-50 dark:bg-amber-950/30 px-4 py-3 text-sm text-amber-800 dark:text-amber-300 mb-8">
        <strong>Why we publish corrections:</strong> Autonomous systems make mistakes. Publishing every correction — not just successes — is how we build trust and improve. Corrections are a feature, not a bug.
      </div>

      {/* Expert engagement callout */}
      <div className="flex items-start gap-3 rounded-lg border border-blue-200 dark:border-blue-900 bg-blue-50/40 dark:bg-blue-950/20 px-4 py-3 mb-8">
        <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className="text-blue-600 dark:text-blue-400 shrink-0 mt-0.5"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
        <div>
          <p className="text-sm font-medium text-blue-800 dark:text-blue-300">For domain experts</p>
          <p className="text-xs text-blue-700/80 dark:text-blue-400/80 mt-0.5">
            Spotted an error we missed, or disagree with a correction? Your expert feedback directly improves our pipeline.{" "}
            <a
              href="https://github.com/ryanwongyy/autonomous-research-infrastructure/issues/new?title=Corrections+Feedback&labels=expert-review&body=Describe+the+issue+or+disagreement%3A%0A%0APaper+or+family+affected%3A%0A"
              target="_blank"
              rel="noopener noreferrer"
              className="underline hover:text-blue-900 dark:hover:text-blue-200 font-medium"
            >
              Report an issue
            </a>
          </p>
        </div>
      </div>

      {/* Summary stats */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3 mb-8">
        <Card>
          <CardContent className="py-4 text-center">
            <div className="text-2xl font-bold font-mono">{totalPapers}</div>
            <div className="text-[11px] text-muted-foreground mt-1">Public Papers</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="py-4 text-center">
            <div className="text-2xl font-bold font-mono text-amber-600 dark:text-amber-400">{totalCorrections}</div>
            <div className="text-[11px] text-muted-foreground mt-1">Total Corrections</div>
          </CardContent>
        </Card>
        <Card className="border-l-4 border-l-amber-500 dark:border-l-amber-400">
          <CardContent className="py-4 text-center">
            <div className="text-2xl font-bold font-mono text-amber-600 dark:text-amber-400">
              {(overallRate * 100).toFixed(1)}%
            </div>
            <div className="text-[11px] text-muted-foreground mt-1">Overall Correction Rate</div>
          </CardContent>
        </Card>
      </div>

      {/* Per-family breakdown */}
      <h2 className="text-xl font-semibold mb-4">By Paper Family</h2>
      {dashboard.families.length === 0 ? (
        <p className="text-sm text-muted-foreground py-8 text-center">No family-level correction data available.</p>
      ) : (
        <div className="rounded-md border overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead scope="col">Family</TableHead>
                <TableHead scope="col" className="w-28 text-right">Public Papers</TableHead>
                <TableHead scope="col" className="w-24 text-right">Corrections</TableHead>
                <TableHead scope="col" className="w-28 text-right">Correction Rate</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {dashboard.families.map((fam) => (
                <TableRow key={fam.family_id}>
                  <TableCell>
                    <Link href={`/families/${fam.family_id}`} className="font-medium hover:text-primary hover:underline transition-colors">
                      {fam.short_name}
                    </Link>
                  </TableCell>
                  <TableCell className="text-right font-mono text-sm">{fam.total_public_papers}</TableCell>
                  <TableCell className="text-right font-mono text-sm text-amber-600 dark:text-amber-400">
                    {fam.total_corrections}
                  </TableCell>
                  <TableCell className="text-right">
                    <Badge
                      variant="secondary"
                      className={
                        fam.correction_rate === 0
                          ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300"
                          : fam.correction_rate <= 0.1
                          ? "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300"
                          : "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300"
                      }
                    >
                      {(fam.correction_rate * 100).toFixed(1)}%
                    </Badge>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {/* Navigation */}
      <Separator className="my-8" />
      <div className="flex flex-wrap gap-4 text-sm">
        <Link href="/outcomes" className="text-primary hover:underline">
          View submission outcomes
        </Link>
        <Link href="/reliability" className="text-primary hover:underline">
          View reliability reports
        </Link>
        <Link href="/failures" className="text-primary hover:underline">
          View failure taxonomy
        </Link>
      </div>
    </div>
  );
}
