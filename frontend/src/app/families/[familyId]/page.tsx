"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { FunnelChart } from "@/components/throughput/funnel-chart";
import { getFamily, getLeaderboard, getFunnel } from "@/lib/api";
import type { PaperFamilyDetail, LeaderboardEntry, FunnelSnapshot } from "@/lib/types";
import { cn } from "@/lib/utils";

const lockColors: Record<string, string> = {
  "venue-lock": "bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-300",
  "method-lock": "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300",
  open: "bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300",
};

export default function FamilyDetailPage() {
  const params = useParams();
  const familyId = params.familyId as string;

  const [family, setFamily] = useState<PaperFamilyDetail | null>(null);
  const [entries, setEntries] = useState<LeaderboardEntry[]>([]);
  const [funnel, setFunnel] = useState<FunnelSnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [apiError, setApiError] = useState(false);

  useEffect(() => {
    async function load() {
      try {
        const [famRes, lbRes, funnelRes] = await Promise.allSettled([
          getFamily(familyId),
          getLeaderboard({ family_id: familyId, per_page: 50 }),
          getFunnel(familyId),
        ]);
        if (famRes.status === "fulfilled") setFamily(famRes.value);
        if (lbRes.status === "fulfilled") setEntries(lbRes.value.entries);
        if (funnelRes.status === "fulfilled") setFunnel(funnelRes.value);
        if (famRes.status === "rejected") setApiError(true);
      } catch {
        setApiError(true);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [familyId]);

  if (loading) {
    return (
      <div className="mx-auto max-w-7xl px-4 py-8">
        <div className="animate-pulse space-y-4">
          <div className="h-8 w-64 bg-muted rounded" />
          <div className="h-4 w-96 bg-muted rounded" />
          <div className="h-64 bg-muted rounded" />
        </div>
      </div>
    );
  }

  if (!family) {
    return (
      <div className="mx-auto max-w-7xl px-4 py-8">
        <Card className={apiError ? "border-amber-200 dark:border-amber-900" : ""}>
          <CardContent className="py-16 text-center text-muted-foreground">
            {apiError
              ? "Unable to connect to the API. Please try again later."
              : "Family not found."}
            <div className="mt-4">
              <Link href="/families" className="text-primary hover:underline text-sm">
                Back to Families
              </Link>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-7xl px-4 py-8">
      {/* Breadcrumb */}
      <nav className="mb-4 text-sm text-muted-foreground">
        <Link href="/families" className="hover:text-foreground">
          Families
        </Link>
        <span className="mx-2">/</span>
        <span className="text-foreground">{family.short_name}</span>
      </nav>

      {/* Header */}
      <div className="mb-8">
        <div className="flex items-start gap-3 flex-wrap">
          <h1 className="text-3xl font-bold">{family.name}</h1>
          <span
            className={cn(
              "mt-1 inline-flex items-center rounded-md px-2 py-0.5 text-xs font-semibold",
              lockColors[family.lock_protocol_type] ?? "bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300"
            )}
          >
            {family.lock_protocol_type.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}
          </span>
        </div>
        <p className="mt-2 text-muted-foreground max-w-3xl">{family.description}</p>
        <div className="mt-3 flex items-center gap-4 text-sm text-muted-foreground">
          <span>
            <strong className="text-foreground">{family.paper_count}</strong> papers
          </span>
          {family.elite_ceiling && (
            <span>
              Ceiling: <strong className="text-foreground">{family.elite_ceiling}</strong>
            </span>
          )}
          <span>
            Portfolio cap: <strong className="text-foreground">{(family.max_portfolio_share * 100).toFixed(0)}%</strong>
          </span>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-8 lg:grid-cols-[1fr_280px]">
        {/* Main content with tabs */}
        <div>
          <Tabs defaultValue="leaderboard">
            <TabsList>
              <TabsTrigger value="leaderboard">Leaderboard</TabsTrigger>
              <TabsTrigger value="methods">Methods & Criteria</TabsTrigger>
              <TabsTrigger value="venues">Venue Ladder</TabsTrigger>
              <TabsTrigger value="funnel">Funnel</TabsTrigger>
            </TabsList>

            {/* Tab 1: Leaderboard */}
            <TabsContent value="leaderboard" className="mt-4">
              {entries.length === 0 ? (
                <Card>
                  <CardContent className="py-12 text-center text-muted-foreground">
                    No leaderboard entries for this family yet.
                  </CardContent>
                </Card>
              ) : (
                <div className="rounded-md border">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead className="w-14">Rank</TableHead>
                        <TableHead>Paper</TableHead>
                        <TableHead className="w-16 text-right">mu</TableHead>
                        <TableHead className="w-16 text-right">sigma</TableHead>
                        <TableHead className="w-20 text-right">Cons.</TableHead>
                        <TableHead className="w-14 text-right">MP</TableHead>
                        <TableHead className="w-24">Status</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {entries.map((entry) => (
                        <TableRow key={entry.paper_id}>
                          <TableCell className="font-medium">
                            {entry.rank ?? "--"}
                          </TableCell>
                          <TableCell className="max-w-xs truncate font-medium">
                            {entry.title}
                          </TableCell>
                          <TableCell className="text-right font-mono text-sm">
                            {entry.mu.toFixed(1)}
                          </TableCell>
                          <TableCell className="text-right font-mono text-sm">
                            {entry.sigma.toFixed(1)}
                          </TableCell>
                          <TableCell className="text-right font-mono text-sm font-semibold">
                            {entry.conservative_rating.toFixed(1)}
                          </TableCell>
                          <TableCell className="text-right font-mono text-sm">
                            {entry.matches_played}
                          </TableCell>
                          <TableCell>
                            <Badge variant="secondary" className="text-[10px]">
                              {entry.review_status}
                            </Badge>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              )}
            </TabsContent>

            {/* Tab 2: Methods & Criteria */}
            <TabsContent value="methods" className="mt-4 space-y-6">
              {/* Canonical Questions */}
              {family.canonical_questions && family.canonical_questions.length > 0 && (
                <Card>
                  <CardHeader>
                    <CardTitle className="text-base">Canonical Questions</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <ul className="space-y-2">
                      {family.canonical_questions.map((q, i) => (
                        <li key={i} className="flex gap-2 text-sm">
                          <span className="shrink-0 text-muted-foreground">{i + 1}.</span>
                          <span>{q}</span>
                        </li>
                      ))}
                    </ul>
                  </CardContent>
                </Card>
              )}

              {/* Accepted Methods */}
              {family.accepted_methods && family.accepted_methods.length > 0 && (
                <Card>
                  <CardHeader>
                    <CardTitle className="text-base">Accepted Methods</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="flex flex-wrap gap-2">
                      {family.accepted_methods.map((m) => (
                        <Badge key={m} variant="secondary">
                          {m}
                        </Badge>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Review Rubric */}
              {family.review_rubric && (
                <Card>
                  <CardHeader>
                    <CardTitle className="text-base">Review Rubric</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="rounded-md border">
                      <Table>
                        <TableHeader>
                          <TableRow>
                            <TableHead>Criterion</TableHead>
                            <TableHead className="w-20 text-right">Weight</TableHead>
                            <TableHead>Description</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {family.review_rubric.criteria.map((c) => (
                            <TableRow key={c.name}>
                              <TableCell className="font-medium">{c.name}</TableCell>
                              <TableCell className="text-right font-mono">
                                {(c.weight * 100).toFixed(0)}%
                              </TableCell>
                              <TableCell className="text-sm text-muted-foreground">
                                {c.description}
                              </TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </div>
                    {family.review_rubric.punished_mainly_for.length > 0 && (
                      <div className="mt-4">
                        <p className="text-sm font-medium mb-2">Punished mainly for:</p>
                        <div className="flex flex-wrap gap-2">
                          {family.review_rubric.punished_mainly_for.map((p) => (
                            <Badge key={p} variant="destructive">
                              {p}
                            </Badge>
                          ))}
                        </div>
                      </div>
                    )}
                  </CardContent>
                </Card>
              )}
            </TabsContent>

            {/* Tab 3: Venue Ladder */}
            <TabsContent value="venues" className="mt-4 space-y-4">
              {family.venue_ladder ? (
                <>
                  <Card>
                    <CardHeader>
                      <CardTitle className="text-base">Flagship Venues</CardTitle>
                    </CardHeader>
                    <CardContent>
                      {family.venue_ladder.flagship.length > 0 ? (
                        <div className="flex flex-wrap gap-2">
                          {family.venue_ladder.flagship.map((v) => (
                            <Badge key={v} variant="default">
                              {v}
                            </Badge>
                          ))}
                        </div>
                      ) : (
                        <p className="text-sm text-muted-foreground">No flagship venues configured.</p>
                      )}
                    </CardContent>
                  </Card>
                  <Card>
                    <CardHeader>
                      <CardTitle className="text-base">Elite Field Venues</CardTitle>
                    </CardHeader>
                    <CardContent>
                      {family.venue_ladder.elite_field.length > 0 ? (
                        <div className="flex flex-wrap gap-2">
                          {family.venue_ladder.elite_field.map((v) => (
                            <Badge key={v} variant="secondary">
                              {v}
                            </Badge>
                          ))}
                        </div>
                      ) : (
                        <p className="text-sm text-muted-foreground">No elite field venues configured.</p>
                      )}
                    </CardContent>
                  </Card>
                </>
              ) : (
                <Card>
                  <CardContent className="py-12 text-center text-muted-foreground">
                    No venue ladder configured for this family.
                  </CardContent>
                </Card>
              )}
            </TabsContent>

            {/* Tab 4: Funnel */}
            <TabsContent value="funnel" className="mt-4">
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Pipeline Funnel</CardTitle>
                </CardHeader>
                <CardContent>
                  {funnel ? (
                    <div>
                      <FunnelChart stages={funnel.stages} killed={funnel.killed} />
                      <Separator className="my-4" />
                      <div className="flex gap-6 text-sm">
                        <div>
                          <span className="text-muted-foreground">Active: </span>
                          <strong>{funnel.total_active}</strong>
                        </div>
                        <div>
                          <span className="text-muted-foreground">Completed: </span>
                          <strong>{funnel.total_completed}</strong>
                        </div>
                        <div>
                          <span className="text-muted-foreground">Killed: </span>
                          <strong className="text-red-600 dark:text-red-400">{funnel.killed}</strong>
                        </div>
                      </div>
                    </div>
                  ) : family.funnel_stages ? (
                    <FunnelChart stages={family.funnel_stages} killed={0} />
                  ) : (
                    <p className="text-sm text-muted-foreground py-8 text-center">
                      Funnel data unavailable for this family.
                    </p>
                  )}
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        </div>

        {/* Sidebar */}
        <aside className="space-y-4">
          {/* Fatal Failures */}
          {family.fatal_failures && family.fatal_failures.length > 0 && (
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm text-red-600 dark:text-red-400">Fatal Failures</CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="space-y-1.5">
                  {family.fatal_failures.map((ff, i) => (
                    <li key={i} className="flex items-start gap-2 text-xs">
                      <span className="mt-0.5 h-1.5 w-1.5 shrink-0 rounded-full bg-red-500 dark:bg-red-400" />
                      {ff}
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}

          {/* Mandatory Checks */}
          {family.mandatory_checks && family.mandatory_checks.length > 0 && (
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm">Mandatory Checks</CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="space-y-1.5">
                  {family.mandatory_checks.map((mc, i) => (
                    <li key={i} className="flex items-start gap-2 text-xs">
                      <span className="mt-0.5 h-1.5 w-1.5 shrink-0 rounded-full bg-amber-500 dark:bg-amber-400" />
                      {mc}
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}

          {/* Elite Ceiling */}
          {family.elite_ceiling && (
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm">Elite Ceiling</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-xs text-muted-foreground">{family.elite_ceiling}</p>
              </CardContent>
            </Card>
          )}

          {/* Data Sources */}
          {family.public_data_sources && family.public_data_sources.length > 0 && (
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm">Public Data Sources</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex flex-wrap gap-1.5">
                  {family.public_data_sources.map((ds) => (
                    <Badge key={ds} variant="outline" className="text-[10px]">
                      {ds}
                    </Badge>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </aside>
      </div>
    </div>
  );
}
