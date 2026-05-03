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
import type { Metadata } from "next";
import { serverFetch } from "@/lib/api";

export const metadata: Metadata = {
  title: "RSI Experiments",
  description: "Browse and filter RSI experiments by tier, family, and status.",
};
import type { RSIExperiment } from "@/lib/types";

const TIER_OPTIONS = [
  "1a", "1b", "1c",
  "2a", "2b", "2c",
  "3a", "3b", "3c",
  "4a", "4b", "4c",
];

const STATUS_OPTIONS = ["proposed", "active", "promoted", "rolled_back", "completed"];

function statusBadgeClass(status: string): string {
  switch (status.toLowerCase()) {
    case "active":
      return "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300";
    case "proposed":
      return "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300";
    case "promoted":
    case "completed":
      return "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300";
    case "rolled_back":
      return "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300";
    default:
      return "bg-muted text-muted-foreground";
  }
}

function truncateObj(obj: Record<string, unknown> | null, maxLen: number): string {
  if (!obj) return "-";
  const str = JSON.stringify(obj);
  return str.length > maxLen ? str.slice(0, maxLen) + "..." : str;
}

export default async function ExperimentsPage({
  searchParams,
}: {
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
}) {
  const resolvedParams = await searchParams;
  const tierFilter = typeof resolvedParams.tier === "string" ? resolvedParams.tier : undefined;
  const statusFilter = typeof resolvedParams.status === "string" ? resolvedParams.status : undefined;

  let experiments: RSIExperiment[] = [];
  let apiError = false;

  try {
    const qs = new URLSearchParams();
    if (tierFilter) qs.set("tier", tierFilter);
    if (statusFilter) qs.set("status", statusFilter);
    const qsStr = qs.toString();
    const data = await serverFetch<RSIExperiment[] | { experiments: RSIExperiment[] }>(
      `/rsi/experiments${qsStr ? `?${qsStr}` : ""}`
    );
    experiments = Array.isArray(data) ? data : data.experiments ?? [];
  } catch {
    apiError = true;
  }

  return (
    <div className="mx-auto max-w-7xl px-4 py-8">
      {apiError && (
        <Card className="mb-6 border-amber-200 dark:border-amber-900">
          <CardContent className="py-4 text-center text-sm text-amber-700 dark:text-amber-400">
            Unable to connect to the API. Experiment data may be unavailable.
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
          <span>Experiments</span>
        </div>
        <h1 className="text-3xl font-bold">RSI Experiments</h1>
        <p className="mt-1 text-muted-foreground">
          All experiments across tiers. Filter by tier or status using the links below.
        </p>
      </div>

      {/* Tier filters */}
      <div className="mb-4">
        <h3 className="text-sm font-medium text-muted-foreground mb-2">Filter by Tier</h3>
        <div className="flex flex-wrap gap-2">
          <Link
            href="/rsi/experiments"
            className={`text-xs px-2 py-1 rounded border ${
              !tierFilter
                ? "bg-primary text-primary-foreground border-primary"
                : "border-border text-muted-foreground hover:text-foreground"
            }`}
          >
            All
          </Link>
          {TIER_OPTIONS.map((t) => (
            <Link
              key={t}
              href={`/rsi/experiments?tier=${t}${statusFilter ? `&status=${statusFilter}` : ""}`}
              className={`text-xs px-2 py-1 rounded border ${
                tierFilter === t
                  ? "bg-primary text-primary-foreground border-primary"
                  : "border-border text-muted-foreground hover:text-foreground"
              }`}
            >
              {t}
            </Link>
          ))}
        </div>
      </div>

      {/* Status filters */}
      <div className="mb-6">
        <h3 className="text-sm font-medium text-muted-foreground mb-2">Filter by Status</h3>
        <div className="flex flex-wrap gap-2">
          <Link
            href={`/rsi/experiments${tierFilter ? `?tier=${tierFilter}` : ""}`}
            className={`text-xs px-2 py-1 rounded border ${
              !statusFilter
                ? "bg-primary text-primary-foreground border-primary"
                : "border-border text-muted-foreground hover:text-foreground"
            }`}
          >
            All
          </Link>
          {STATUS_OPTIONS.map((s) => (
            <Link
              key={s}
              href={`/rsi/experiments?status=${s}${tierFilter ? `&tier=${tierFilter}` : ""}`}
              className={`text-xs px-2 py-1 rounded border ${
                statusFilter === s
                  ? "bg-primary text-primary-foreground border-primary"
                  : "border-border text-muted-foreground hover:text-foreground"
              }`}
            >
              {s.replace(/_/g, " ")}
            </Link>
          ))}
        </div>
      </div>

      <Separator className="my-6" />

      {/* Experiments table */}
      {experiments.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center text-muted-foreground">
            <p>
              No experiments found
              {tierFilter ? ` for tier ${tierFilter}` : ""}
              {statusFilter ? ` with status "${statusFilter.replace(/_/g, " ")}"` : ""}
              . Ensure the backend API is running and experiments have been created.
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="rounded-md border overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead scope="col">ID</TableHead>
                <TableHead scope="col">Tier</TableHead>
                <TableHead scope="col">Name</TableHead>
                <TableHead scope="col">Status</TableHead>
                <TableHead scope="col">Family</TableHead>
                <TableHead scope="col">Created</TableHead>
                <TableHead scope="col">Activated</TableHead>
                <TableHead scope="col">Result Summary</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {experiments.map((exp) => (
                <TableRow key={exp.id}>
                  <TableCell className="font-mono">{exp.id}</TableCell>
                  <TableCell>
                    <Badge variant="outline">{exp.tier}</Badge>
                  </TableCell>
                  <TableCell className="font-medium">{exp.name}</TableCell>
                  <TableCell>
                    <Badge className={statusBadgeClass(exp.status)}>
                      {exp.status.replace(/_/g, " ")}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {exp.family_id ?? "-"}
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {exp.proposed_at ?? "-"}
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {exp.activated_at ?? "-"}
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground max-w-xs">
                    {truncateObj(exp.result_summary, 60)}
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
