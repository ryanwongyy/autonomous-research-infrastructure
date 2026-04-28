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
  title: "Submission Outcomes — Venue Decisions & Acceptance Rates",
  description: "Track AI governance paper submissions: acceptance rates by venue, rejection analysis, and publishing success across all paper families.",
};

interface OutcomesDashboard {
  overall: {
    total: number;
    accepted: number;
    rejected: number;
    desk_reject: number;
    r_and_r: number;
    pending: number;
    acceptance_rate: number;
  };
  per_family: Array<{
    family_id: string;
    short_name: string;
    total: number;
    accepted: number;
    rejected: number;
    acceptance_rate: number;
  }>;
}

const decisionColors: Record<string, string> = {
  accepted: "text-emerald-600 dark:text-emerald-400",
  rejected: "text-red-600 dark:text-red-400",
  pending: "text-blue-600 dark:text-blue-400",
};

export default async function OutcomesPage() {
  let dashboard: OutcomesDashboard | null = null;
  let apiError = false;

  try {
    dashboard = await serverFetch<OutcomesDashboard>("/outcomes/dashboard");
  } catch {
    apiError = true;
  }

  if (!dashboard) {
    return (
      <div className="mx-auto max-w-5xl px-4 py-8">
        <h1 className="text-3xl font-bold">Submission Outcomes</h1>
        <Separator className="my-6" />
        <Card className={apiError ? "border-amber-200 dark:border-amber-900" : ""}>
          <CardContent className="py-12 text-center text-muted-foreground">
            {apiError
              ? "Unable to connect to the API. Please try again later."
              : "No submission outcome data available yet."}
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

  const { overall, per_family } = dashboard;

  return (
    <div className="mx-auto max-w-5xl px-4 py-8">
      <h1 className="text-3xl font-bold">Submission Outcomes</h1>
      <p className="mt-1 text-muted-foreground">
        Transparent reporting of venue submission decisions across all paper families.
      </p>
      <Separator className="my-6" />

      {/* Overall stats */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-6 mb-8">
        {[
          { label: "Total Submitted", value: overall.total, color: "text-foreground" },
          { label: "Accepted", value: overall.accepted, color: decisionColors.accepted },
          { label: "Rejected", value: overall.rejected, color: decisionColors.rejected },
          { label: "Desk Reject", value: overall.desk_reject, color: "text-red-500 dark:text-red-400" },
          { label: "R&R", value: overall.r_and_r, color: "text-amber-600 dark:text-amber-400" },
          { label: "Pending", value: overall.pending, color: decisionColors.pending },
        ].map((stat) => (
          <Card key={stat.label}>
            <CardContent className="py-4 text-center">
              <div className={`text-2xl font-bold font-mono ${stat.color}`}>{stat.value}</div>
              <div className="text-[11px] text-muted-foreground mt-1">{stat.label}</div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Acceptance rate highlight */}
      <Card className="mb-8 border-l-4 border-l-emerald-500 dark:border-l-emerald-400">
        <CardContent className="py-4 flex items-center justify-between">
          <span className="text-sm text-muted-foreground">Overall acceptance rate</span>
          <span className="text-3xl font-bold font-mono text-emerald-600 dark:text-emerald-400">
            {(overall.acceptance_rate * 100).toFixed(1)}%
          </span>
        </CardContent>
      </Card>

      {/* Per-family breakdown */}
      <h2 className="text-xl font-semibold mb-4">By Paper Family</h2>
      {per_family.length === 0 ? (
        <p className="text-sm text-muted-foreground py-8 text-center">No family-level data available.</p>
      ) : (
        <div className="rounded-md border overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead scope="col">Family</TableHead>
                <TableHead scope="col" className="w-20 text-right">Total</TableHead>
                <TableHead scope="col" className="w-20 text-right">Accepted</TableHead>
                <TableHead scope="col" className="w-20 text-right">Rejected</TableHead>
                <TableHead scope="col" className="w-28 text-right">Acceptance Rate</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {per_family.map((fam) => (
                <TableRow key={fam.family_id}>
                  <TableCell>
                    <Link href={`/families/${fam.family_id}`} className="font-medium hover:text-primary hover:underline transition-colors">
                      {fam.short_name}
                    </Link>
                  </TableCell>
                  <TableCell className="text-right font-mono text-sm">{fam.total}</TableCell>
                  <TableCell className="text-right font-mono text-sm text-emerald-600 dark:text-emerald-400">
                    {fam.accepted}
                  </TableCell>
                  <TableCell className="text-right font-mono text-sm text-red-600 dark:text-red-400">
                    {fam.rejected}
                  </TableCell>
                  <TableCell className="text-right">
                    <Badge
                      variant="secondary"
                      className={
                        fam.acceptance_rate >= 0.5
                          ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300"
                          : fam.acceptance_rate >= 0.2
                          ? "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300"
                          : "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300"
                      }
                    >
                      {(fam.acceptance_rate * 100).toFixed(1)}%
                    </Badge>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}
