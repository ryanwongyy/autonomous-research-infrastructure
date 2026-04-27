import type { Metadata } from "next";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";

export const metadata: Metadata = {
  title: "Failure Analysis",
  description: "Failure distribution, severity trends, and root-cause analysis across the paper pipeline.",
};
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

import { serverFetch } from "@/lib/api";

interface FailureDashboard {
  distribution: {
    total: number;
    by_type: Record<string, number>;
    by_severity: Record<string, number>;
    by_stage: Record<string, number>;
  };
  trends: Array<{ date: string; total: number; [key: string]: string | number }>;
}

const TYPE_LABELS: Record<string, string> = {
  data_error: "Data Error",
  logic_error: "Logic Error",
  hallucination: "Hallucination",
  causal_overreach: "Causal Overreach",
  source_drift: "Source Drift",
  design_violation: "Design Violation",
  formatting: "Formatting",
  other: "Other",
};

export default async function FailuresPage() {
  let data: FailureDashboard | null = null;
  let apiError = false;

  try {
    data = await serverFetch<FailureDashboard>("/failures/dashboard?days=90");
  } catch {
    apiError = true;
  }

  return (
    <div className="mx-auto max-w-7xl px-4 py-8">
      {apiError && (
        <Card className="mb-6 border-amber-200 dark:border-amber-900">
          <CardContent className="py-4 text-center text-sm text-amber-700 dark:text-amber-400">
            Unable to connect to the API. Failure data may be unavailable.
          </CardContent>
        </Card>
      )}

      <div className="mb-6">
        <h1 className="text-3xl font-bold">Failure Taxonomy</h1>
        <p className="mt-1 text-muted-foreground">
          Systematic classification of pipeline failures. Tracks error types,
          severity, and detection stages to enable institutional learning.
        </p>
      </div>

      {!data || data.distribution.total === 0 ? (
        <Card>
          <CardContent className="py-12 text-center text-muted-foreground">
            <p>No failures recorded yet. Failures are auto-classified when review layers detect issues.</p>
          </CardContent>
        </Card>
      ) : (
        <>
          {/* Summary stats */}
          <div className="grid gap-4 md:grid-cols-4 mb-6">
            <Card>
              <CardHeader className="pb-1">
                <CardTitle className="text-sm text-muted-foreground">Total Failures</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{data.distribution.total}</div>
              </CardContent>
            </Card>
            {Object.entries(data.distribution.by_severity)
              .sort(([a], [b]) => {
                const order = ["critical", "high", "medium", "low"];
                return order.indexOf(a) - order.indexOf(b);
              })
              .slice(0, 3)
              .map(([sev, count]) => (
                <Card key={sev}>
                  <CardHeader className="pb-1">
                    <CardTitle className="text-sm text-muted-foreground capitalize">{sev}</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className={`text-2xl font-bold ${
                      sev === "critical"
                        ? "text-red-600 dark:text-red-400"
                        : sev === "high"
                        ? "text-orange-600 dark:text-orange-400"
                        : sev === "medium"
                        ? "text-amber-600 dark:text-amber-400"
                        : "text-foreground"
                    }`}>{count}</div>
                  </CardContent>
                </Card>
              ))}
          </div>

          <Separator className="my-6" />

          <div className="grid gap-6 md:grid-cols-2">
            {/* By Type */}
            <Card>
              <CardHeader>
                <CardTitle className="text-base">By Failure Type</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2.5">
                  {Object.entries(data.distribution.by_type)
                    .sort(([, a], [, b]) => b - a)
                    .map(([type, count]) => {
                      const maxCount = Math.max(...Object.values(data!.distribution.by_type));
                      return (
                        <div key={type}>
                          <div className="flex items-center justify-between mb-0.5">
                            <span className="text-sm">{TYPE_LABELS[type] ?? type}</span>
                            <span className="text-xs font-mono font-semibold">{count}</span>
                          </div>
                          <div className="h-1.5 w-full rounded-full bg-muted overflow-hidden">
                            <div
                              className="h-full rounded-full bg-red-500/70 dark:bg-red-400/70 transition-all"
                              style={{ width: `${maxCount > 0 ? (count / maxCount) * 100 : 0}%` }}
                            />
                          </div>
                        </div>
                      );
                    })}
                </div>
              </CardContent>
            </Card>

            {/* By Stage */}
            <Card>
              <CardHeader>
                <CardTitle className="text-base">By Detection Stage</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2.5">
                  {Object.entries(data.distribution.by_stage)
                    .sort(([, a], [, b]) => b - a)
                    .map(([stage, count]) => {
                      const maxCount = Math.max(...Object.values(data!.distribution.by_stage));
                      return (
                        <div key={stage}>
                          <div className="flex items-center justify-between mb-0.5">
                            <span className="text-sm">{stage.replace(/_/g, " ")}</span>
                            <span className="text-xs font-mono font-semibold">{count}</span>
                          </div>
                          <div className="h-1.5 w-full rounded-full bg-muted overflow-hidden">
                            <div
                              className="h-full rounded-full bg-amber-500/70 dark:bg-amber-400/70 transition-all"
                              style={{ width: `${maxCount > 0 ? (count / maxCount) * 100 : 0}%` }}
                            />
                          </div>
                        </div>
                      );
                    })}
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Trends table */}
          {data.trends.length > 0 && (
            <>
              <Separator className="my-6" />
              <h2 className="text-xl font-semibold mb-4">Recent Trends (90 days)</h2>
              <div className="rounded-md border overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead scope="col">Date</TableHead>
                      <TableHead scope="col" className="text-right">Total</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {data.trends.map((t) => (
                      <TableRow key={t.date}>
                        <TableCell className="font-medium">{t.date}</TableCell>
                        <TableCell className="text-right font-mono">{t.total}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </>
          )}
        </>
      )}
    </div>
  );
}
