"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { FamilyCard } from "@/components/family/family-card";
import { FunnelChart } from "@/components/throughput/funnel-chart";
import { getFamilies, getFunnel, getProjections, getReleaseStatus, getPublicPapers } from "@/lib/api";
import type { PaperFamily, FunnelSnapshot, Projection, ReleasePipelineStatus, Paper } from "@/lib/types";

export default function HomePage() {
  const [families, setFamilies] = useState<PaperFamily[]>([]);
  const [funnel, setFunnel] = useState<FunnelSnapshot | null>(null);
  const [projections, setProjections] = useState<Projection | null>(null);
  const [release, setRelease] = useState<ReleasePipelineStatus | null>(null);
  const [latestPapers, setLatestPapers] = useState<Paper[]>([]);
  const [loading, setLoading] = useState(true);
  const [apiError, setApiError] = useState(false);

  useEffect(() => {
    async function load() {
      const [famRes, funnelRes, projRes, relRes, papersRes] = await Promise.allSettled([
        getFamilies(),
        getFunnel(),
        getProjections(),
        getReleaseStatus(),
        getPublicPapers(3),
      ]);
      if (famRes.status === "fulfilled") setFamilies(famRes.value.families);
      if (funnelRes.status === "fulfilled") setFunnel(funnelRes.value);
      if (projRes.status === "fulfilled") setProjections(projRes.value);
      if (relRes.status === "fulfilled") setRelease(relRes.value);
      if (papersRes.status === "fulfilled") setLatestPapers(papersRes.value.slice(0, 3));

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

  const releaseInternalCount = release?.internal?.count ?? 0;
  const releaseCandidateCount = release?.candidate?.count ?? 0;
  const releaseSubmittedCount = release?.submitted?.count ?? 0;
  const releasePublicCount = release?.public?.count ?? 0;

  return (
    <div className="mx-auto max-w-7xl px-4 py-8">
      {/* Hero Section */}
      <section className="mb-12">
        <h1 className="text-3xl font-bold tracking-tight sm:text-4xl md:text-5xl">
          AI governance research, generated and reviewed autonomously
        </h1>
        <p className="mt-4 max-w-3xl text-lg text-muted-foreground leading-relaxed">
          This platform generates rigorous research on how institutions govern AI
          &mdash; from procurement rules to international coordination. Every paper
          is independently reviewed, ranked against peer-reviewed benchmarks, and
          published transparently. We invite researchers to review, critique, and
          build on this work.
        </p>
        <div className="mt-4 flex flex-wrap gap-x-6 gap-y-1 text-sm text-muted-foreground">
          <span>{families.length > 0 ? families.length : 11} research families</span>
          <span>7-role generation pipeline</span>
          <span>5-layer independent review</span>
          <span>TrueSkill tournament ranking</span>
          <span>Open access &middot; No paywall</span>
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
          <Link
            href="/leaderboard"
            className="inline-flex items-center rounded-lg border border-border bg-background px-4 py-2 text-sm font-medium hover:bg-muted transition-colors"
          >
            View Rankings
          </Link>
        </div>
      </section>

      {apiError && (
        <Card className="mb-6 border-amber-200 dark:border-amber-900" role="alert">
          <CardContent className="py-4 text-center text-sm text-amber-700 dark:text-amber-400">
            The research pipeline API is currently unreachable — statistics, papers, and family data may not load.
            You can still browse static pages like{" "}
            <Link href="/methodology" className="underline hover:text-amber-900 dark:hover:text-amber-200">Methodology</Link> and{" "}
            <Link href="/about" className="underline hover:text-amber-900 dark:hover:text-amber-200">About</Link>.
          </CardContent>
        </Card>
      )}

      {/* System Pulse — quick-glance summary for returning users */}
      {!loading && !apiError && (funnel || projections) && (
        <div className="mb-6 rounded-lg border bg-muted/20 px-4 py-3 flex flex-wrap items-center gap-x-6 gap-y-1 text-sm">
          <span className="font-semibold text-foreground text-xs uppercase tracking-wider">System Pulse</span>
          {funnel && (
            <>
              <span className="text-muted-foreground">
                <span className="font-mono font-semibold text-foreground">{funnel.total_active}</span> in pipeline
              </span>
              <span className="text-muted-foreground">
                <span className="font-mono font-semibold text-emerald-600 dark:text-emerald-400">{funnel.total_completed}</span> completed
              </span>
              {funnel.killed > 0 && (
                <span className="text-muted-foreground">
                  <span className="font-mono font-semibold text-red-600 dark:text-red-400">{funnel.killed}</span> killed
                </span>
              )}
            </>
          )}
          {projections && (
            <Badge variant={projections.on_track ? "default" : "destructive"} className="text-[11px]">
              {projections.on_track ? "On Track" : "Behind Target"}
            </Badge>
          )}
        </div>
      )}

      {/* Stat Cards */}
      <section className="mb-10 grid grid-cols-1 gap-4 sm:grid-cols-2 md:grid-cols-4">
        <Link href="/throughput" className="group" title="All papers currently in any pipeline stage (Scout → Designer → … → Packager). Click for funnel breakdown.">
          <Card className="transition-colors group-hover:border-primary/40 group-focus-within:border-primary/40 group-focus-within:ring-2 group-focus-within:ring-primary/20">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                Total Active Papers
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold text-blue-600 dark:text-blue-400">
                {loading ? <span className="inline-block h-8 w-12 animate-pulse rounded bg-muted" /> : totalPapers}
              </div>
              <p className="mt-1 text-xs sm:text-sm text-muted-foreground">
                In any pipeline stage (not killed)
              </p>
            </CardContent>
          </Card>
        </Link>

        <Link href="/publications" className="group" title="Papers that passed all 5 review layers (L1-L5) but have not yet received a Significance Memo verdict to advance to Submitted.">
          <Card className="transition-colors group-hover:border-primary/40 group-focus-within:border-primary/40 group-focus-within:ring-2 group-focus-within:ring-primary/20">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                Submission Ready
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold text-emerald-600 dark:text-emerald-400">
                {loading ? <span className="inline-block h-8 w-12 animate-pulse rounded bg-muted" /> : submissionReady}
              </div>
              <p className="mt-1 text-xs sm:text-sm text-muted-foreground">
                Passed L1-L5, awaiting Significance Memo
              </p>
            </CardContent>
          </Card>
        </Link>

        <Link href="/families" className="group" title="Paper families currently producing work. Each family has a locked methodology and target venues.">
          <Card className="transition-colors group-hover:border-primary/40 group-focus-within:border-primary/40 group-focus-within:ring-2 group-focus-within:ring-primary/20">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                Families Active
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold text-purple-600 dark:text-purple-400">
                {loading ? <span className="inline-block h-8 w-12 animate-pulse rounded bg-muted" /> : activeFamilies}
              </div>
              <p className="mt-1 text-xs sm:text-sm text-muted-foreground">
                Of {families.length > 0 ? families.length : 11} paper families
              </p>
            </CardContent>
          </Card>
        </Link>

        <Link href="/publications" className="group" title="Papers with release_status = Public — published or accepted, fully open to citation and review.">
          <Card className="transition-colors group-hover:border-primary/40 group-focus-within:border-primary/40 group-focus-within:ring-2 group-focus-within:ring-primary/20">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                Public Papers
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold text-cyan-600 dark:text-cyan-400">
                {loading ? <span className="inline-block h-8 w-12 animate-pulse rounded bg-muted" /> : latestPapers.length > 0 ? releasePublicCount : 0}
              </div>
              <p className="mt-1 text-xs sm:text-sm text-muted-foreground">
                Released for citation and review
              </p>
            </CardContent>
          </Card>
        </Link>
      </section>

      {/* Latest Publications */}
      {!loading && latestPapers.length > 0 && (
        <section className="mb-10">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-2xl font-semibold">Latest Publications</h2>
            <Link href="/publications" className="text-sm text-primary hover:underline">
              View all
            </Link>
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            {latestPapers.map((paper) => (
              <Link key={paper.id} href={`/papers/${paper.id}`} className="block group focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 rounded-lg">
                <Card className="h-full transition-all group-hover:shadow-md group-hover:border-primary/30">
                  <CardContent className="py-4">
                    <h3 className="text-sm font-semibold leading-snug line-clamp-2 group-hover:text-primary transition-colors">
                      {paper.title}
                    </h3>
                    <div className="mt-2 flex items-center gap-2 flex-wrap">
                      {paper.family_id && (
                        <Badge variant="outline" className="text-[11px]">{paper.family_id}</Badge>
                      )}
                      {paper.rating && (
                        <span className="text-[11px] font-medium text-indigo-700 dark:text-indigo-400">
                          Rating: {paper.rating.conservative_rating.toFixed(1)}
                        </span>
                      )}
                      {paper.created_at && (
                        <span className="text-[11px] text-muted-foreground ml-auto">
                          {new Date(paper.created_at).toLocaleDateString()}
                        </span>
                      )}
                    </div>
                  </CardContent>
                </Card>
              </Link>
            ))}
          </div>
        </section>
      )}

      {/* For Researchers — compact engagement links */}
      <section className="mb-10 rounded-lg border border-blue-200 dark:border-blue-900 bg-blue-50/30 dark:bg-blue-950/20 p-4">
        <h2 className="text-base font-semibold mb-2">For Researchers</h2>
        <p className="text-sm text-muted-foreground mb-3">
          We invite domain experts to review, critique, and build on this work.
          Every paper includes citation export (BibTeX/APA) and a one-click issue reporter.
        </p>
        <div className="flex flex-wrap gap-3 text-sm">
          <Link href="/publications" className="inline-flex items-center gap-1.5 text-primary hover:underline font-medium">
            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/></svg>
            Review a paper
          </Link>
          <Link href="/families" className="inline-flex items-center gap-1.5 text-primary hover:underline font-medium">
            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/></svg>
            Track a family
          </Link>
          <Link href="/corrections" className="inline-flex items-center gap-1.5 text-primary hover:underline font-medium">
            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>
            View corrections
          </Link>
          <a href="https://github.com/ryanwongyy/autonomous-research-infrastructure/issues" target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1.5 text-primary hover:underline font-medium">
            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/></svg>
            Report an issue
          </a>
        </div>
      </section>

      {/* Family Grid */}
      <section className="mb-12">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-2xl font-semibold">Paper Families</h2>
          <div className="flex items-center gap-4">
            <Link
              href="/categories"
              className="text-sm text-muted-foreground hover:text-foreground transition-colors"
            >
              Browse by topic
            </Link>
            <Link
              href="/families"
              className="text-sm text-primary hover:underline"
            >
              View all
            </Link>
          </div>
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
              <p className="text-lg font-medium mb-2">Families will appear as papers are generated</p>
              <p className="text-sm text-muted-foreground max-w-md mx-auto">
                Each family targets specific journals and conferences with tailored
                methodology. Papers are added as the pipeline produces them.
              </p>
              <Link href="/methodology" className="mt-3 inline-block text-sm text-primary hover:underline">
                Learn how the pipeline works
              </Link>
            </CardContent>
          </Card>
        ) : (
          <>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {families.slice(0, 6).map((family) => (
                <FamilyCard key={family.id} family={family} />
              ))}
            </div>
            {families.length > 6 && (
              <div className="mt-4 text-center">
                <Link href="/families" className="text-sm text-primary hover:underline">
                  View all {families.length} families
                </Link>
              </div>
            )}
          </>
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
            ) : loading ? (
              <div className="space-y-2 py-4">
                {Array.from({ length: 4 }).map((_, i) => (
                  <div key={i} className="h-6 animate-pulse rounded bg-muted" />
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground py-8 text-center">
                Funnel data unavailable
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
                { label: "Internal", count: releaseInternalCount, color: "bg-gray-400 dark:bg-gray-500" },
                { label: "Candidate", count: releaseCandidateCount, color: "bg-blue-500 dark:bg-blue-400" },
                { label: "Submitted", count: releaseSubmittedCount, color: "bg-amber-500 dark:bg-amber-400" },
                { label: "Public", count: releasePublicCount, color: "bg-emerald-500 dark:bg-emerald-400" },
              ].map((item) => (
                <div key={item.label} className="flex items-center gap-3">
                  <span className="w-16 sm:w-24 text-sm text-muted-foreground">
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
                    {loading ? <span className="inline-block h-4 w-6 animate-pulse rounded bg-muted" /> : item.count}
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
                  <p className="mt-1 text-xs sm:text-sm text-muted-foreground">
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
