import type { Metadata } from "next";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { serverFetch } from "@/lib/api";
import type { ReliabilityOverview } from "@/lib/types";

export const metadata: Metadata = {
  title: "Reliability",
  description: "Reliability metrics across paper families — replication rates, fidelity scores, and quality thresholds.",
};

const METRIC_LABELS: Record<string, string> = {
  replication_rate: "Replication Rate",
  manifest_fidelity: "Manifest Fidelity",
  expert_score: "Expert Score",
  benchmark_percentile: "Benchmark Percentile",
  correction_rate: "Correction Rate",
};

function statusColor(passes: number, total: number): string {
  if (total === 0) return "bg-muted text-muted-foreground";
  const ratio = passes / total;
  if (ratio >= 0.9) return "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300";
  if (ratio >= 0.7) return "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300";
  return "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300";
}

export default async function ReliabilityPage() {
  let data: ReliabilityOverview | null = null;
  let apiError = false;

  try {
    data = await serverFetch<ReliabilityOverview>("/reliability/overview");
  } catch {
    apiError = true;
  }

  return (
    <div className="mx-auto max-w-7xl px-4 py-8">
      <div className="mb-6">
        <h1 className="text-3xl font-bold">Reliability Dashboard</h1>
        <p className="mt-1 text-muted-foreground">
          Tracked quality thresholds across paper families. Green = meets
          threshold, amber = borderline, red = below threshold.
        </p>
      </div>

      {apiError && (
        <Card className="mb-6 border-amber-200 dark:border-amber-900">
          <CardContent className="py-4 text-center text-sm text-amber-700 dark:text-amber-400">
            Unable to connect to the API. Reliability data may be unavailable.
          </CardContent>
        </Card>
      )}

      {!data || data.families.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center text-muted-foreground">
            <p>No reliability data available. Ensure the backend API is running and papers have been reviewed.</p>
          </CardContent>
        </Card>
      ) : (
        <>
          {/* Thresholds reference */}
          <Card className="mb-6">
            <CardHeader>
              <CardTitle className="text-base">Active Thresholds</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex flex-wrap gap-4">
                {Object.entries(data.thresholds).map(([key, val]) => (
                  <div key={key} className="text-sm">
                    <span className="font-medium">{METRIC_LABELS[key] ?? key}:</span>{" "}
                    <span className="font-mono">{val}</span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          <Separator className="my-6" />

          {/* Per-family breakdown */}
          <div className="space-y-6">
            {data.families.map((family) => (
              <Card key={family.family_id}>
                <CardHeader>
                  <CardTitle className="text-base">
                    {family.short_name}{" "}
                    <span className="text-muted-foreground font-normal text-sm">
                      ({family.family_id})
                    </span>
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="grid gap-3 md:grid-cols-5">
                    {Object.entries(family.metrics).map(([metricType, m]) => (
                      <div key={metricType} className="space-y-1">
                        <div className="text-xs font-medium text-muted-foreground">
                          {METRIC_LABELS[metricType] ?? metricType}
                        </div>
                        <div className="text-lg font-mono font-bold">
                          {m.avg_value.toFixed(2)}
                        </div>
                        <Badge
                          className={`text-[10px] ${statusColor(m.papers_passing, m.total_papers)}`}
                        >
                          {m.papers_passing}/{m.total_papers} pass
                        </Badge>
                        <div className="text-[10px] text-muted-foreground">
                          range: {m.min_value.toFixed(2)} - {m.max_value.toFixed(2)}
                        </div>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
