"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { FamilyCard } from "@/components/family/family-card";
import { FunnelChart } from "@/components/throughput/funnel-chart";
import { getFamilies, getFunnel, getProjections, getReleaseStatus } from "@/lib/api";
import type { PaperFamily, FunnelSnapshot, Projection, ReleasePipelineStatus } from "@/lib/types";

export default function HomePage() {
  const [families, setFamilies] = useState<PaperFamily[]>([]);
  const [funnel, setFunnel] = useState<FunnelSnapshot | null>(null);
  const [projections, setProjections] = useState<Projection | null>(null);
  const [release, setRelease] = useState<ReleasePipelineStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [apiError, setApiError] = useState(false);

  useEffect(() => {
    async function load() {
      const [famRes, funnelRes, projRes, relRes] = await Promise.allSettled([
        getFamilies(),
        getFunnel(),
        getProjections(),
        getReleaseStatus(),
      ]);
      if (famRes.status === "fulfilled") setFamilies(famRes.value.families);
      if (funnelRes.status === "fulfilled") setFunnel(funnelRes.value);
      if (projRes.status === "fulfilled") setProjections(projRes.value);
      if (relRes.status === "fulfilled") setRelease(relRes.value);

      const allFailed = [famRes, funnelRes, projRes, relRes].every(
        (r) => r.status === "rejected"
      );
      if (allFailed) setApiError(true);

      setLoading(false);
    }
    load();
  }, []);

  const totalPapers = funnel?.total_active ?? 0;
  const submissionReady = funnel?.total_completed ?? 0;
  const activeFamilies = families.filter((f) => f.active).length;
  const totalSources = families.reduce((sum, f) => sum + f.paper_count, 0);

  const releaseInternalCount = release?.internal?.count ?? 0;
  const releaseCandidateCount = release?.candidate?.count ?? 0;
  const releaseSubmittedCount = release?.submitted?.count ?? 0;
  const releasePublicCount = release?.public?.count ?? 0;

  return (
    <div className="mx-auto max-w-7xl px-4 py-8">
      {/* Hero Section */}
      <section className="mb-12">
        <h1 className="text-4xl font-bold tracking-tight sm:text-5xl">
          AI governance research, generated and reviewed autonomously
        </h1>
        <p className="mt-4 max-w-3xl text-lg text-muted-foreground leading-relaxed">
          This platform generates rigorous research on how institutions govern AI
          &mdash; from procurement rules to international coordination. Every paper
          is independently reviewed, ranked against peer-reviewed benchmarks, and
          published transparently.
        </p>
        <div className="mt-4 flex flex-wrap gap-x-6 gap-y-1 text-sm text-muted-foreground">
          <span>11 research families</span>
          <span>7-role generation pipeline</span>
          <span>5-layer independent review</span>
          <span>TrueSkill tournament ranking</span>
        </div>
        <div className="mt-6 flex gap-3">
          <Link
            href="/publications"
            className="inline-flex items-center rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
          >
            Browse Research
          </Link>
          <Link
            href="/methodology"
            className="inline-flex items-center rounded-lg border border-border bg-background px-4 py-2 text-sm font-medium hover:bg-muted transition-colors"
          >
            How It Works
          </Link>
        </div>
      </section>

      {apiError && (
        <Card className="mb-6 border-amber-200 dark:border-amber-900">
          <CardContent className="py-4 text-center text-sm text-amber-700 dark:text-amber-400">
            Unable to reach the backend API. Some data may be unavailable.
          </CardContent>
        </Card>
      )}

      {/* Stat Cards */}
      <section className="mb-10 grid grid-cols-1 gap-4 sm:grid-cols-2 md:grid-cols-4">
        <Link href="/throughput" className="group">
          <Card className="transition-colors group-hover:border-primary/40 group-focus-within:border-primary/40 group-focus-within:ring-2 group-focus-within:ring-primary/20">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                Total Active Papers
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold">
                {loading ? "..." : totalPapers}
              </div>
              <p className="mt-1 text-xs text-muted-foreground">
                Across all pipeline stages
              </p>
            </CardContent>
          </Card>
        </Link>

        <Link href="/publications" className="group">
          <Card className="transition-colors group-hover:border-primary/40 group-focus-within:border-primary/40 group-focus-within:ring-2 group-focus-within:ring-primary/20">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                Submission Ready
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold text-emerald-600 dark:text-emerald-400">
                {loading ? "..." : submissionReady}
              </div>
              <p className="mt-1 text-xs text-muted-foreground">
                Passed all review layers
              </p>
            </CardContent>
          </Card>
        </Link>

        <Link href="/families" className="group">
          <Card className="transition-colors group-hover:border-primary/40 group-focus-within:border-primary/40 group-focus-within:ring-2 group-focus-within:ring-primary/20">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                Families Active
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold">
                {loading ? "..." : activeFamilies}
              </div>
              <p className="mt-1 text-xs text-muted-foreground">
                Of 11 paper families
              </p>
            </CardContent>
          </Card>
        </Link>

        <Link href="/sources" className="group">
          <Card className="transition-colors group-hover:border-primary/40 group-focus-within:border-primary/40 group-focus-within:ring-2 group-focus-within:ring-primary/20">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                Source Cards
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold">
                {loading ? "..." : totalSources}
              </div>
              <p className="mt-1 text-xs text-muted-foreground">
                Registered data sources
              </p>
            </CardContent>
          </Card>
        </Link>
      </section>

      {/* Family Grid */}
      <section className="mb-12">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-2xl font-semibold">Paper Families</h2>
          <Link
            href="/families"
            className="text-sm text-primary hover:underline"
          >
            View all
          </Link>
        </div>
        {loading ? (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <Card key={i} className="h-40 animate-pulse bg-muted/50" />
            ))}
          </div>
        ) : families.length === 0 ? (
          <Card>
            <CardContent className="py-12 text-center">
              <p className="text-lg font-medium mb-2">Paper families loading soon</p>
              <p className="text-sm text-muted-foreground max-w-md mx-auto">
                Research families organize papers by methodology and target venue.
                Once the pipeline begins generating, families will appear here.
              </p>
              <Link href="/methodology" className="mt-3 inline-block text-sm text-primary hover:underline">
                Learn how the pipeline works
              </Link>
            </CardContent>
          </Card>
        ) : (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {families.map((family) => (
              <FamilyCard key={family.id} family={family} />
            ))}
          </div>
        )}
      </section>

      {/* Throughput & Release Pipeline */}
      <section className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Funnel */}
        <Card>
          <CardHeader>
            <CardTitle>Pipeline Throughput</CardTitle>
          </CardHeader>
          <CardContent>
            {funnel ? (
              <FunnelChart stages={funnel.stages} killed={funnel.killed} />
            ) : (
              <p className="text-sm text-muted-foreground py-8 text-center">
                {loading ? "Loading..." : "Funnel data unavailable"}
              </p>
            )}
          </CardContent>
        </Card>

        {/* Release Pipeline */}
        <Card>
          <CardHeader>
            <CardTitle>Release Pipeline</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {[
                { label: "Internal", count: releaseInternalCount, color: "bg-gray-400" },
                { label: "Candidate", count: releaseCandidateCount, color: "bg-blue-500" },
                { label: "Submitted", count: releaseSubmittedCount, color: "bg-amber-500" },
                { label: "Public", count: releasePublicCount, color: "bg-emerald-500" },
              ].map((item) => (
                <div key={item.label} className="flex items-center gap-3">
                  <span className="w-24 text-sm text-muted-foreground">
                    {item.label}
                  </span>
                  <div className="flex-1 h-4 bg-muted rounded overflow-hidden">
                    <div
                      className={`h-full rounded ${item.color}`}
                      style={{
                        width: `${Math.max(
                          (item.count / Math.max(releaseInternalCount + releaseCandidateCount + releaseSubmittedCount + releasePublicCount, 1)) * 100,
                          item.count > 0 ? 5 : 0
                        )}%`,
                      }}
                    />
                  </div>
                  <span className="w-8 text-right text-sm font-mono font-semibold">
                    {loading ? "..." : item.count}
                  </span>
                </div>
              ))}
            </div>

            {projections && (
              <div className="mt-6 rounded-lg bg-muted/50 p-3">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">Annual projection</span>
                  <Badge variant={projections.on_track ? "default" : "destructive"}>
                    {projections.on_track ? "On Track" : "Behind Target"}
                  </Badge>
                </div>
                {projections.gap_analysis && (
                  <p className="mt-1 text-xs text-muted-foreground">
                    {projections.gap_analysis}
                  </p>
                )}
              </div>
            )}
          </CardContent>
        </Card>
      </section>
    </div>
  );
}
