import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import type { Metadata } from "next";
import { serverFetch } from "@/lib/api";
import type { MetaPipelineRun } from "@/lib/types";

export const metadata: Metadata = {
  title: "Meta-Pipeline",
  description: "Meta-pipeline runs — observation, shadow testing, and promotion decisions.",
};

function statusBadgeClass(status: string): string {
  switch (status.toLowerCase()) {
    case "completed":
    case "success":
      return "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300";
    case "running":
    case "in_progress":
      return "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300";
    case "failed":
    case "error":
      return "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300";
    case "pending":
      return "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300";
    default:
      return "bg-muted text-muted-foreground";
  }
}

function decisionBadgeClass(decision: string | null): string {
  if (!decision) return "bg-muted text-muted-foreground";
  const d = decision.toLowerCase();
  if (d === "promote" || d === "promoted")
    return "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300";
  if (d === "hold" || d === "held")
    return "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300";
  if (d === "rollback" || d === "rolled_back")
    return "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300";
  return "bg-muted text-muted-foreground";
}

function summarizeObservation(obs: Record<string, unknown> | null): string {
  if (!obs) return "No observation data";
  const keys = Object.keys(obs);
  if (keys.length === 0) return "Empty observation";
  const preview = keys.slice(0, 3).map((k) => `${k}: ${JSON.stringify(obs[k])}`).join(", ");
  return keys.length > 3 ? `${preview}, ...` : preview;
}

export default async function MetaPipelinePage() {
  let runs: MetaPipelineRun[] = [];
  let apiError = false;

  try {
    const data = await serverFetch<MetaPipelineRun[] | { runs: MetaPipelineRun[] }>("/rsi/tier4c/runs");
    runs = Array.isArray(data) ? data : data.runs ?? [];
  } catch {
    apiError = true;
  }

  return (
    <div className="mx-auto max-w-7xl px-4 py-8">
      {apiError && (
        <Card className="mb-6 border-amber-200 dark:border-amber-900">
          <CardContent className="py-4 text-center text-sm text-amber-700 dark:text-amber-400">
            Unable to connect to the API. Meta-pipeline data may be unavailable.
          </CardContent>
        </Card>
      )}

      {/* Header */}
      <div className="mb-6">
        <div className="flex items-center gap-2 text-sm text-muted-foreground mb-2">
          <Link href="/rsi" className="hover:text-foreground">
            RSI
          </Link>
          <span>/</span>
          <span>Meta Pipeline</span>
        </div>
        <h1 className="text-3xl font-bold">Meta Pipeline (Tier 4c)</h1>
        <p className="mt-1 text-muted-foreground">
          The highest-order RSI loop. Observes the entire system, proposes
          structural changes, shadow-tests them, then promotes or rolls back.
        </p>
      </div>

      {runs.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center text-muted-foreground">
            <p>
              No meta-pipeline cycles have been run yet.
            </p>
          </CardContent>
        </Card>
      ) : (
        <>
          {/* Summary */}
          <div className="grid gap-4 md:grid-cols-3 mb-6">
            <Card>
              <CardHeader className="pb-1">
                <CardTitle className="text-sm text-muted-foreground">
                  Total Runs
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{runs.length}</div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-1">
                <CardTitle className="text-sm text-muted-foreground">
                  Completed
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">
                  {runs.filter((r) => r.status.toLowerCase() === "completed" || r.status.toLowerCase() === "success").length}
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-1">
                <CardTitle className="text-sm text-muted-foreground">
                  Promotions
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">
                  {runs.filter(
                    (r) =>
                      r.promotion_decision?.toLowerCase() === "promote" ||
                      r.promotion_decision?.toLowerCase() === "promoted"
                  ).length}
                </div>
              </CardContent>
            </Card>
          </div>

          <Separator className="my-6" />

          {/* Run cards */}
          <h2 className="text-xl font-semibold mb-4">Pipeline Runs</h2>
          <div className="space-y-4">
            {runs.map((run) => (
              <Card key={run.id}>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-base">
                      Run #{run.id}
                    </CardTitle>
                    <Badge className={statusBadgeClass(run.status)}>
                      {run.status}
                    </Badge>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="grid gap-4 md:grid-cols-2">
                    {/* Timing */}
                    <div className="space-y-1">
                      <div className="text-xs font-medium text-muted-foreground">
                        Started
                      </div>
                      <div className="text-sm">{run.started_at ?? "-"}</div>
                    </div>
                    <div className="space-y-1">
                      <div className="text-xs font-medium text-muted-foreground">
                        Completed
                      </div>
                      <div className="text-sm">{run.completed_at ?? "-"}</div>
                    </div>

                    {/* Observation */}
                    <div className="space-y-1 md:col-span-2">
                      <div className="text-xs font-medium text-muted-foreground">
                        Observation Summary
                      </div>
                      <div className="text-sm font-mono bg-muted/50 rounded p-2 text-xs">
                        {summarizeObservation(run.observation)}
                      </div>
                    </div>

                    {/* Proposals */}
                    <div className="space-y-1">
                      <div className="text-xs font-medium text-muted-foreground">
                        Proposals
                      </div>
                      <div className="text-sm font-bold">
                        {run.proposals ? run.proposals.length : 0}
                      </div>
                    </div>

                    {/* Promotion Decision */}
                    <div className="space-y-1">
                      <div className="text-xs font-medium text-muted-foreground">
                        Promotion Decision
                      </div>
                      {run.promotion_decision ? (
                        <Badge className={decisionBadgeClass(run.promotion_decision)}>
                          {run.promotion_decision}
                        </Badge>
                      ) : (
                        <span className="text-sm text-muted-foreground">-</span>
                      )}
                    </div>
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
