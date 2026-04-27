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

const METRICS: Record<string, { label: string; description: string }> = {
  replication_rate: {
    label: "Replication Rate",
    description: "Fraction of review layers passed on first attempt. Measures first-time-right quality.",
  },
  manifest_fidelity: {
    label: "Manifest Fidelity",
    description: "Design-artifact lock hash verification. Confirms no silent drift between pipeline stages.",
  },
  expert_score: {
    label: "Expert Score",
    description: "Average overall score from external human expert reviews (0-10 scale).",
  },
  benchmark_percentile: {
    label: "Benchmark Percentile",
    description: "Rank position relative to all papers in the family, derived from tournament results.",
  },
  correction_rate: {
    label: "Correction Rate",
    description: "Post-publication corrections per paper. Lower is better — 0 means no errata filed.",
  },
};

// Backward-compatible label lookup
const METRIC_LABELS: Record<string, string> = Object.fromEntries(
  Object.entries(METRICS).map(([k, v]) => [k, v.label])
);

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
          Five quantitative metrics are tracked per paper and aggregated per family.
          Each metric is compared against a configurable threshold — papers that fall below are flagged for investigation.
        </p>
        <div className="mt-3 flex items-center gap-4 text-xs text-muted-foreground">
          <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full bg-emerald-500" aria-hidden="true" /> &ge;90% pass = meets threshold</span>
          <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full bg-amber-500" aria-hidden="true" /> 70-89% = borderline</span>
          <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full bg-red-500" aria-hidden="true" /> &lt;70% = below threshold</span>
        </div>
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
            <p>No reliability data available yet. Metrics are computed as papers complete the review pipeline and tournament ranking.</p>
          </CardContent>
        </Card>
      ) : (
        <>
          {/* Thresholds reference */}
          <Card className="mb-6">
            <CardHeader>
              <CardTitle className="text-base">Active Thresholds</CardTitle>
              <p className="text-xs text-muted-foreground mt-1">
                Minimum acceptable values for each metric. Papers scoring below these thresholds are flagged.
              </p>
            </CardHeader>
            <CardContent>
              <div className="flex flex-wrap gap-4">
                {Object.entries(data.thresholds).map(([key, val]) => (
                  <div key={key} className="text-sm" title={METRICS[key]?.description}>
                    <span className="font-medium">{METRIC_LABELS[key] ?? key}:</span>{" "}
                    <span className="font-mono">&ge; {val}</span>
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
                        <div className="text-xs font-medium text-muted-foreground" title={METRICS[metricType]?.description}>
                          <abbr title={METRICS[metricType]?.description} className="no-underline cursor-help">
                            {METRIC_LABELS[metricType] ?? metricType}
                          </abbr>
                        </div>
                        <div className="text-lg font-mono font-bold">
                          {m.avg_value.toFixed(2)}
                        </div>
                        <Badge
                          className={`text-[11px] ${statusColor(m.papers_passing, m.total_papers)}`}
                        >
                          {m.papers_passing}/{m.total_papers} pass
                        </Badge>
                        <div className="h-1.5 w-full rounded-full bg-muted overflow-hidden mt-1">
                          <div
                            className={`h-full rounded-full transition-all ${
                              m.total_papers === 0
                                ? "bg-muted-foreground"
                                : m.papers_passing / m.total_papers >= 0.9
                                ? "bg-emerald-500 dark:bg-emerald-400"
                                : m.papers_passing / m.total_papers >= 0.7
                                ? "bg-amber-500 dark:bg-amber-400"
                                : "bg-red-500 dark:bg-red-400"
                            }`}
                            style={{ width: m.total_papers > 0 ? `${(m.papers_passing / m.total_papers) * 100}%` : "0%" }}
                          />
                        </div>
                        <div className="text-[11px] text-muted-foreground">
                          range: {m.min_value.toFixed(2)} – {m.max_value.toFixed(2)}
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
