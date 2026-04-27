import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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
import type { Metadata } from "next";
import { serverFetch } from "@/lib/api";
import type { RSIDashboard } from "@/lib/types";

export const metadata: Metadata = {
  title: "RSI Dashboard",
  description: "Recursive Self-Improvement dashboard — experiments by tier, status, and recent gate decisions.",
};

const TIER_INFO: Record<string, string> = {
  "1a": "Role Prompts",
  "1b": "Review Prompts",
  "1c": "Policy Calibration",
  "2a": "Family Config",
  "2b": "Drift Threshold",
  "2c": "Judge Calibration",
  "3a": "Layer Architecture",
  "3b": "Role Architecture",
  "3c": "Family Discovery",
  "4a": "Taxonomy Expansion",
  "4b": "Improvement Targeting",
  "4c": "Meta Pipeline",
};

const TIER_ORDER = [
  "1a", "1b", "1c",
  "2a", "2b", "2c",
  "3a", "3b", "3c",
  "4a", "4b", "4c",
];

function decisionBadgeClass(decision: string): string {
  const d = decision.toLowerCase();
  if (d === "promote" || d === "promoted")
    return "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300";
  if (d === "hold" || d === "held")
    return "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300";
  if (d === "rollback" || d === "rolled_back")
    return "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300";
  return "bg-muted text-muted-foreground";
}

function statusBadgeClass(count: number): string {
  if (count > 5) return "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300";
  if (count > 0) return "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300";
  return "bg-muted text-muted-foreground";
}

function truncate(text: string | null, maxLen: number): string {
  if (!text) return "-";
  return text.length > maxLen ? text.slice(0, maxLen) + "..." : text;
}

export default async function RSIPage() {
  let dashboard: RSIDashboard | null = null;
  let apiError = false;

  try {
    dashboard = await serverFetch<RSIDashboard>("/rsi/dashboard");
  } catch {
    apiError = true;
  }

  const totalExperiments = dashboard?.total_experiments ?? 0;
  const activeCount = dashboard?.by_status?.active ?? 0;
  const proposedCount = dashboard?.by_status?.proposed ?? 0;
  const rolledBackCount = dashboard?.by_status?.rolled_back ?? 0;
  const recentGates = dashboard?.recent_gates?.slice(0, 20) ?? [];
  const byTier = dashboard?.by_tier ?? {};
  const byStatus = dashboard?.by_status ?? {};

  return (
    <div className="mx-auto max-w-7xl px-4 py-8">
      {apiError && (
        <Card className="mb-6 border-amber-200 dark:border-amber-900">
          <CardContent className="py-4 text-center text-sm text-amber-700 dark:text-amber-400">
            Unable to connect to the API. RSI data may be unavailable.
          </CardContent>
        </Card>
      )}

      {/* Header */}
      <div className="mb-6">
        <h1 className="text-3xl font-bold">Recursive Self-Improvement</h1>
        <p className="mt-1 text-muted-foreground">
          The system that improves itself. Tracks prompt evolution, configuration
          optimization, architecture changes, and meta-learning cycles.
        </p>
        <div className="mt-3 flex gap-3 text-sm">
          <Link
            href="/rsi/experiments"
            className="text-primary underline underline-offset-4 hover:text-primary/80"
          >
            All Experiments
          </Link>
          <Link
            href="/rsi/meta"
            className="text-primary underline underline-offset-4 hover:text-primary/80"
          >
            Meta Pipeline
          </Link>
        </div>
      </div>

      {!dashboard ? (
        <Card>
          <CardContent className="py-12 text-center text-muted-foreground">
            <p>
              No RSI data available. Ensure the backend API is running and RSI
              experiments have been created.
            </p>
          </CardContent>
        </Card>
      ) : (
        <>
          {/* Summary cards */}
          <div className="grid gap-4 md:grid-cols-4 mb-6">
            <Card>
              <CardHeader className="pb-1">
                <CardTitle className="text-sm text-muted-foreground">
                  Total Experiments
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{totalExperiments}</div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-1">
                <CardTitle className="text-sm text-muted-foreground">
                  Active
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold text-emerald-600 dark:text-emerald-400">{activeCount}</div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-1">
                <CardTitle className="text-sm text-muted-foreground">
                  Proposed
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold text-blue-600 dark:text-blue-400">{proposedCount}</div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-1">
                <CardTitle className="text-sm text-muted-foreground">
                  Rolled Back
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold text-red-600 dark:text-red-400">{rolledBackCount}</div>
              </CardContent>
            </Card>
          </div>

          <Separator className="my-6" />

          {/* Tier Health Grid */}
          <h2 className="text-xl font-semibold mb-4">Tier Health</h2>
          <div className="grid gap-4 md:grid-cols-4 mb-6">
            {TIER_ORDER.map((tier) => {
              const count = byTier[tier] ?? 0;
              return (
                <Card key={tier}>
                  <CardHeader className="pb-1">
                    <CardTitle className="text-sm">
                      Tier {tier}
                      <span className="ml-2 font-normal text-muted-foreground">
                        {TIER_INFO[tier]}
                      </span>
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="flex items-center justify-between">
                      <span className="text-lg font-mono font-bold">
                        {count}
                      </span>
                      <Badge className={statusBadgeClass(count)}>
                        {count > 0 ? "active" : "idle"}
                      </Badge>
                    </div>
                  </CardContent>
                </Card>
              );
            })}
          </div>

          <Separator className="my-6" />

          {/* Recent Gate Decisions */}
          <h2 className="text-xl font-semibold mb-4">Recent Gate Decisions</h2>
          {recentGates.length === 0 ? (
            <Card>
              <CardContent className="py-8 text-center text-muted-foreground">
                <p>No gate decisions recorded yet.</p>
              </CardContent>
            </Card>
          ) : (
            <div className="rounded-md border mb-6">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Experiment ID</TableHead>
                    <TableHead>Gate Type</TableHead>
                    <TableHead>Decision</TableHead>
                    <TableHead>Decided At</TableHead>
                    <TableHead>Notes</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {recentGates.map((gate) => (
                    <TableRow key={gate.id}>
                      <TableCell className="font-mono">{gate.experiment_id}</TableCell>
                      <TableCell>{gate.gate_type}</TableCell>
                      <TableCell>
                        <Badge className={decisionBadgeClass(gate.decision)}>
                          {gate.decision}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {gate.decided_at ?? "-"}
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground max-w-xs">
                        {truncate(gate.notes, 80)}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}

          <Separator className="my-6" />

          {/* Experiments by Status */}
          <h2 className="text-xl font-semibold mb-4">Experiments by Status</h2>
          <div className="grid gap-4 md:grid-cols-3">
            {Object.entries(byStatus)
              .sort(([, a], [, b]) => b - a)
              .map(([status, count]) => (
                <Card key={status}>
                  <CardHeader className="pb-1">
                    <CardTitle className="text-sm capitalize">{status.replace(/_/g, " ")}</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="text-2xl font-bold">{count}</div>
                    <Link
                      href={`/rsi/experiments?status=${status}`}
                      className="text-xs text-primary underline underline-offset-2 hover:text-primary/80"
                    >
                      View experiments
                    </Link>
                  </CardContent>
                </Card>
              ))}
          </div>
        </>
      )}
    </div>
  );
}
