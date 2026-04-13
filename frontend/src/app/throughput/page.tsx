"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { FunnelChart } from "@/components/throughput/funnel-chart";
import {
  getFunnel,
  getConversionRates,
  getBottlenecks,
  getProjections,
  getWorkQueue,
} from "@/lib/api";
import type {
  FunnelSnapshot,
  ConversionRate,
  Bottleneck,
  Projection,
  WorkQueueItem,
} from "@/lib/types";
import { cn } from "@/lib/utils";

const severityColors: Record<string, string> = {
  critical: "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300",
  high: "bg-orange-100 text-orange-700 dark:bg-orange-900/40 dark:text-orange-300",
  medium: "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300",
  low: "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300",
};

export default function ThroughputPage() {
  const [funnel, setFunnel] = useState<FunnelSnapshot | null>(null);
  const [conversions, setConversions] = useState<ConversionRate[]>([]);
  const [bottlenecks, setBottlenecks] = useState<Bottleneck[]>([]);
  const [projections, setProjections] = useState<Projection | null>(null);
  const [workQueue, setWorkQueue] = useState<WorkQueueItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    async function load() {
      try {
        const [fRes, cRes, bRes, pRes, wRes] = await Promise.allSettled([
          getFunnel(),
          getConversionRates(),
          getBottlenecks(),
          getProjections(),
          getWorkQueue(),
        ]);
        if (fRes.status === "fulfilled") setFunnel(fRes.value);
        if (cRes.status === "fulfilled") setConversions(cRes.value.conversions);
        if (bRes.status === "fulfilled") setBottlenecks(bRes.value.bottlenecks);
        if (pRes.status === "fulfilled") setProjections(pRes.value);
        if (wRes.status === "fulfilled") setWorkQueue(wRes.value.items);
        const allFailed = [fRes, cRes, bRes, pRes, wRes].every(
          (r) => r.status === "rejected"
        );
        if (allFailed) setError(true);
      } catch {
        setError(true);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  return (
    <div className="mx-auto max-w-7xl px-4 py-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold">Throughput Dashboard</h1>
        <p className="mt-2 text-muted-foreground max-w-2xl">
          Real-time view of the research pipeline. Track papers through funnel stages,
          identify bottlenecks, and monitor annual projection targets.
        </p>
      </div>

      {error && (
        <Card className="mb-6 border-amber-200 dark:border-amber-900">
          <CardContent className="py-4 text-center text-sm text-amber-700 dark:text-amber-400">
            Unable to connect to the API. Dashboard data may be unavailable.
          </CardContent>
        </Card>
      )}

      {/* Top stats */}
      {funnel && (
        <section className="mb-8 grid grid-cols-2 gap-4 md:grid-cols-4">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                Active Papers
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold">{funnel.total_active}</div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                Completed
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold text-emerald-600 dark:text-emerald-400">
                {funnel.total_completed}
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                Killed
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold text-red-600 dark:text-red-400">{funnel.killed}</div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                Projection Status
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-lg font-bold">
                {projections ? (
                  <Badge
                    variant={projections.on_track ? "default" : "destructive"}
                    className="text-sm"
                  >
                    {projections.on_track ? "On Track" : "Behind"}
                  </Badge>
                ) : (
                  <span className="text-muted-foreground">--</span>
                )}
              </div>
            </CardContent>
          </Card>
        </section>
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Funnel Visualization */}
        <Card>
          <CardHeader>
            <CardTitle>Pipeline Funnel</CardTitle>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="h-48 animate-pulse bg-muted rounded" />
            ) : funnel ? (
              <FunnelChart stages={funnel.stages} killed={funnel.killed} />
            ) : (
              <p className="py-8 text-center text-sm text-muted-foreground">
                Funnel data unavailable.
              </p>
            )}
          </CardContent>
        </Card>

        {/* Conversion Rates */}
        <Card>
          <CardHeader>
            <CardTitle>Conversion Rates</CardTitle>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="h-48 animate-pulse bg-muted rounded" />
            ) : conversions.length === 0 ? (
              <p className="py-8 text-center text-sm text-muted-foreground">
                No conversion data available.
              </p>
            ) : (
              <div className="rounded-md border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>From</TableHead>
                      <TableHead>To</TableHead>
                      <TableHead className="text-right">Rate</TableHead>
                      <TableHead className="text-right">Count</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {conversions.map((c, i) => (
                      <TableRow key={i}>
                        <TableCell className="text-sm">
                          {c.from.replace(/_/g, " ")}
                        </TableCell>
                        <TableCell className="text-sm">
                          {c.to.replace(/_/g, " ")}
                        </TableCell>
                        <TableCell className="text-right font-mono text-sm">
                          {(c.rate * 100).toFixed(1)}%
                        </TableCell>
                        <TableCell className="text-right font-mono text-sm">
                          {c.converted}/{c.count}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Bottleneck Alerts */}
        <Card>
          <CardHeader>
            <CardTitle>Bottleneck Alerts</CardTitle>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="h-32 animate-pulse bg-muted rounded" />
            ) : bottlenecks.length === 0 ? (
              <div className="py-8 text-center">
                <p className="text-sm text-emerald-600 dark:text-emerald-400 font-medium">No bottlenecks detected</p>
                <p className="text-xs text-muted-foreground mt-1">
                  All stages are flowing normally.
                </p>
              </div>
            ) : (
              <div className="space-y-3">
                {bottlenecks.map((b, i) => (
                  <div
                    key={i}
                    className="flex items-start gap-3 rounded-lg border p-3"
                  >
                    <span
                      className={cn(
                        "mt-0.5 inline-flex items-center rounded-md px-1.5 py-0.5 text-[10px] font-semibold shrink-0",
                        severityColors[b.severity] ?? severityColors.low
                      )}
                    >
                      {b.severity.toUpperCase()}
                    </span>
                    <div className="min-w-0">
                      <p className="text-sm font-medium">
                        {b.stage.replace(/_/g, " ")}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {b.stuck_count} papers stuck, avg {b.avg_days_in_stage.toFixed(1)} days
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Annual Projections */}
        <Card>
          <CardHeader>
            <CardTitle>Annual Projections</CardTitle>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="h-32 animate-pulse bg-muted rounded" />
            ) : !projections ? (
              <p className="py-8 text-center text-sm text-muted-foreground">
                Projection data unavailable.
              </p>
            ) : (
              <div className="space-y-4">
                <div className="flex items-center gap-2">
                  <Badge
                    variant={projections.on_track ? "default" : "destructive"}
                  >
                    {projections.on_track ? "On Track" : "Behind Target"}
                  </Badge>
                </div>

                {Object.keys(projections.projected_annual).length > 0 && (
                  <div className="rounded-md border">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Metric</TableHead>
                          <TableHead className="text-right">Projected</TableHead>
                          <TableHead className="text-right">Target</TableHead>
                          <TableHead className="text-right">Gap</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {Object.entries(projections.projected_annual).map(
                          ([metric, projected]) => {
                            const target =
                              projections.targets[metric] ?? 0;
                            const gap = projected - target;
                            return (
                              <TableRow key={metric}>
                                <TableCell className="text-sm">
                                  {metric.replace(/_/g, " ")}
                                </TableCell>
                                <TableCell className="text-right font-mono text-sm">
                                  {projected}
                                </TableCell>
                                <TableCell className="text-right font-mono text-sm">
                                  {target}
                                </TableCell>
                                <TableCell
                                  className={cn(
                                    "text-right font-mono text-sm font-semibold",
                                    gap >= 0
                                      ? "text-emerald-600 dark:text-emerald-400"
                                      : "text-red-600 dark:text-red-400"
                                  )}
                                >
                                  {gap >= 0 ? "+" : ""}
                                  {gap}
                                </TableCell>
                              </TableRow>
                            );
                          }
                        )}
                      </TableBody>
                    </Table>
                  </div>
                )}

                {projections.gap_analysis && (
                  <p className="text-xs text-muted-foreground">
                    {projections.gap_analysis}
                  </p>
                )}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Work Queue */}
      {workQueue.length > 0 && (
        <section className="mt-8">
          <Card>
            <CardHeader>
              <CardTitle>Work Queue</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="rounded-md border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-12">Priority</TableHead>
                      <TableHead>Paper</TableHead>
                      <TableHead>Family</TableHead>
                      <TableHead>Stage</TableHead>
                      <TableHead>Reason</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {workQueue.map((item) => (
                      <TableRow key={item.paper_id}>
                        <TableCell className="font-mono text-sm font-semibold">
                          {item.priority}
                        </TableCell>
                        <TableCell className="max-w-xs truncate text-sm font-medium">
                          {item.title}
                        </TableCell>
                        <TableCell>
                          <Badge variant="outline" className="text-[10px]">
                            {item.family_id}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-sm text-muted-foreground">
                          {item.funnel_stage.replace(/_/g, " ")}
                        </TableCell>
                        <TableCell className="text-sm text-muted-foreground max-w-xs truncate">
                          {item.reason}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </CardContent>
          </Card>
        </section>
      )}
    </div>
  );
}
