"use client";

import { useEffect, useMemo, useState, useCallback } from "react";
import Link from "next/link";
import { useSearchParams, useRouter, usePathname } from "next/navigation";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { getPublicPapers } from "@/lib/api";
import type { Paper } from "@/lib/types";

type DateRange = "all" | "7d" | "30d" | "90d";

function daysAgo(days: number): Date {
  const d = new Date();
  d.setDate(d.getDate() - days);
  return d;
}

export default function PublicationsPage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();

  const [papers, setPapers] = useState<Paper[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  type SortOption = "newest" | "oldest" | "rating" | "novelty" | "title";

  // Initialize state from URL params
  const [dateRange, setDateRange] = useState<DateRange>(() => {
    const v = searchParams.get("date");
    return (v === "7d" || v === "30d" || v === "90d") ? v : "all";
  });
  const [searchQuery, setSearchQuery] = useState(() => searchParams.get("q") ?? "");
  const [selectedCategories, setSelectedCategories] = useState<Set<string>>(() => {
    const v = searchParams.get("cat");
    return v ? new Set(v.split(",")) : new Set<string>();
  });
  const [selectedMethods, setSelectedMethods] = useState<Set<string>>(() => {
    const v = searchParams.get("method");
    return v ? new Set(v.split(",")) : new Set<string>();
  });
  const [sortBy, setSortBy] = useState<SortOption>(() => {
    const v = searchParams.get("sort");
    return (v === "oldest" || v === "rating" || v === "novelty" || v === "title") ? v : "newest";
  });

  // Sync filters to URL
  const syncUrl = useCallback((updates: { date?: DateRange; q?: string; cat?: Set<string>; method?: Set<string>; sort?: SortOption }) => {
    const params = new URLSearchParams();
    const d = updates.date ?? dateRange;
    const q = updates.q ?? searchQuery;
    const c = updates.cat ?? selectedCategories;
    const m = updates.method ?? selectedMethods;
    const s = updates.sort ?? sortBy;
    if (d !== "all") params.set("date", d);
    if (q.trim()) params.set("q", q.trim());
    if (c.size > 0) params.set("cat", [...c].join(","));
    if (m.size > 0) params.set("method", [...m].join(","));
    if (s !== "newest") params.set("sort", s);
    const qs = params.toString();
    router.replace(`${pathname}${qs ? `?${qs}` : ""}`, { scroll: false });
  }, [dateRange, searchQuery, selectedCategories, selectedMethods, sortBy, pathname, router]);

  useEffect(() => {
    async function load() {
      try {
        const data = await getPublicPapers();
        setPapers(data);
      } catch {
        setError("Failed to load papers");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const statusColor: Record<string, string> = {
    candidate: "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300",
    submitted: "bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300",
    public: "bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300",
  };

  const allCategories = useMemo(() => [...new Set(papers.map((p) => p.category).filter(Boolean) as string[])].sort(), [papers]);
  const allMethods = useMemo(() => [...new Set(papers.map((p) => p.method).filter(Boolean) as string[])].sort(), [papers]);

  const filteredPapers = useMemo(() => {
    let result = papers;

    // Date range filter
    if (dateRange !== "all") {
      const cutoff = dateRange === "7d" ? daysAgo(7) : dateRange === "30d" ? daysAgo(30) : daysAgo(90);
      result = result.filter((p) => p.created_at && new Date(p.created_at) >= cutoff);
    }

    // Text search
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase().trim();
      result = result.filter(
        (p) =>
          p.title.toLowerCase().includes(q) ||
          (p.abstract && p.abstract.toLowerCase().includes(q)) ||
          (p.category && p.category.toLowerCase().includes(q)) ||
          (p.method && p.method.toLowerCase().includes(q))
      );
    }

    // Category filter
    if (selectedCategories.size > 0) {
      result = result.filter((p) => p.category && selectedCategories.has(p.category));
    }

    // Method filter
    if (selectedMethods.size > 0) {
      result = result.filter((p) => p.method && selectedMethods.has(p.method));
    }

    // Sort
    result = [...result].sort((a, b) => {
      switch (sortBy) {
        case "oldest":
          return (a.created_at ?? "").localeCompare(b.created_at ?? "");
        case "rating":
          return (b.rating?.conservative_rating ?? -999) - (a.rating?.conservative_rating ?? -999);
        case "novelty":
          return (b.novelty_score ?? 0) - (a.novelty_score ?? 0);
        case "title":
          return a.title.localeCompare(b.title);
        case "newest":
        default:
          return (b.created_at ?? "").localeCompare(a.created_at ?? "");
      }
    });

    return result;
  }, [papers, dateRange, searchQuery, selectedCategories, selectedMethods, sortBy]);

  const hasActiveFilters = searchQuery.trim() || dateRange !== "all" || selectedCategories.size > 0 || selectedMethods.size > 0;

  function toggleCategory(cat: string) {
    setSelectedCategories((prev) => {
      const next = new Set(prev);
      if (next.has(cat)) next.delete(cat);
      else next.add(cat);
      syncUrl({ cat: next });
      return next;
    });
  }

  function toggleMethod(method: string) {
    setSelectedMethods((prev) => {
      const next = new Set(prev);
      if (next.has(method)) next.delete(method);
      else next.add(method);
      syncUrl({ method: next });
      return next;
    });
  }

  function clearAllFilters() {
    setSearchQuery("");
    setDateRange("all");
    setSelectedCategories(new Set());
    setSelectedMethods(new Set());
    setSortBy("newest");
    router.replace(pathname, { scroll: false });
  }

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 space-y-6">
      <div>
        <div className="flex items-baseline gap-3">
          <h1 className="text-3xl font-bold tracking-tight">Publications</h1>
          {!loading && papers.length > 0 && (
            <span className="text-sm text-muted-foreground font-mono" role="status" aria-live="polite">
              {filteredPapers.length}{hasActiveFilters ? ` of ${papers.length}` : ""} papers
            </span>
          )}
        </div>
        <p className="text-muted-foreground mt-1">
          Papers ready for publication — each has passed five independent review layers
          and been ranked against peer-reviewed benchmarks.
        </p>
      </div>

      {/* Transparency notice */}
      <div className="rounded-lg border border-amber-200 dark:border-amber-800 bg-amber-50/50 dark:bg-amber-950/30 px-4 py-2.5 text-sm text-amber-800 dark:text-amber-300 flex items-center gap-2">
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="shrink-0" aria-hidden="true"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/></svg>
        <span>All papers are AI-generated and may contain errors. We publish corrections openly. <Link href="/about" className="underline hover:text-amber-900 dark:hover:text-amber-200">Learn more</Link></span>
      </div>

      {/* Search & Filters */}
      {!loading && papers.length > 0 && (
        <div className="space-y-3">
          {/* Search bar + sort */}
          <div className="flex gap-2">
            <div className="relative flex-1">
              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" aria-hidden="true"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>
              <input
                type="text"
                placeholder="Search papers by title, abstract, category, or method..."
                value={searchQuery}
                onChange={(e) => { setSearchQuery(e.target.value); syncUrl({ q: e.target.value }); }}
                aria-label="Search papers by title, abstract, category, or method"
                className="w-full rounded-lg border border-border bg-background pl-10 pr-3 py-2 text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
              />
            </div>
            <select
              value={sortBy}
              onChange={(e) => { const v = e.target.value as SortOption; setSortBy(v); syncUrl({ sort: v }); }}
              className="rounded-lg border border-border bg-background px-3 py-2 text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
              aria-label="Sort papers"
            >
              <option value="newest">Newest first</option>
              <option value="oldest">Oldest first</option>
              <option value="rating">Highest rated</option>
              <option value="novelty">Novelty score</option>
              <option value="title">Title A-Z</option>
            </select>
          </div>

          {/* Date range */}
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs text-muted-foreground mr-1">Date:</span>
            {([["all", "All"], ["7d", "7 days"], ["30d", "30 days"], ["90d", "90 days"]] as const).map(([value, label]) => (
              <button
                key={value}
                type="button"
                onClick={() => { setDateRange(value); syncUrl({ date: value }); }}
                aria-pressed={dateRange === value}
                aria-label={`Filter by date: ${label}`}
                className={`rounded-md px-2.5 py-1 text-xs font-medium transition-colors ${
                  dateRange === value
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted text-muted-foreground hover:bg-muted/80"
                }`}
              >
                {label}
              </button>
            ))}
          </div>

          {/* Category chips */}
          {allCategories.length > 0 && (
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-xs text-muted-foreground mr-1">Category:</span>
              {allCategories.map((cat) => (
                <button
                  key={cat}
                  type="button"
                  onClick={() => toggleCategory(cat)}
                  aria-pressed={selectedCategories.has(cat)}
                  aria-label={`Filter by category: ${cat}`}
                  className={`rounded-md px-2.5 py-1 text-xs font-medium transition-colors ${
                    selectedCategories.has(cat)
                      ? "bg-primary text-primary-foreground"
                      : "bg-muted text-muted-foreground hover:bg-muted/80"
                  }`}
                >
                  {cat}
                </button>
              ))}
            </div>
          )}

          {/* Method chips */}
          {allMethods.length > 0 && (
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-xs text-muted-foreground mr-1">Method:</span>
              {allMethods.map((method) => (
                <button
                  key={method}
                  type="button"
                  onClick={() => toggleMethod(method)}
                  aria-pressed={selectedMethods.has(method)}
                  aria-label={`Filter by method: ${method}`}
                  className={`rounded-md px-2.5 py-1 text-xs font-medium transition-colors ${
                    selectedMethods.has(method)
                      ? "bg-primary text-primary-foreground"
                      : "bg-muted text-muted-foreground hover:bg-muted/80"
                  }`}
                >
                  {method}
                </button>
              ))}
            </div>
          )}

          {/* Active filter summary */}
          {hasActiveFilters && (
            <div className="flex items-center gap-2 text-xs">
              <span className="text-muted-foreground">Active filters:</span>
              {searchQuery.trim() && (
                <span className="inline-flex items-center gap-1 rounded-full bg-primary/10 px-2 py-0.5 text-primary">
                  &ldquo;{searchQuery}&rdquo;
                  <button type="button" onClick={() => { setSearchQuery(""); syncUrl({ q: "" }); }} className="hover:text-primary/70" aria-label="Clear search">&times;</button>
                </span>
              )}
              {dateRange !== "all" && (
                <span className="inline-flex items-center gap-1 rounded-full bg-primary/10 px-2 py-0.5 text-primary">
                  {dateRange}
                  <button type="button" onClick={() => { setDateRange("all"); syncUrl({ date: "all" }); }} className="hover:text-primary/70" aria-label="Clear date filter">&times;</button>
                </span>
              )}
              {[...selectedCategories].map((cat) => (
                <span key={cat} className="inline-flex items-center gap-1 rounded-full bg-primary/10 px-2 py-0.5 text-primary">
                  {cat}
                  <button type="button" onClick={() => toggleCategory(cat)} className="hover:text-primary/70" aria-label={`Remove ${cat} filter`}>&times;</button>
                </span>
              ))}
              {[...selectedMethods].map((method) => (
                <span key={method} className="inline-flex items-center gap-1 rounded-full bg-primary/10 px-2 py-0.5 text-primary">
                  {method}
                  <button type="button" onClick={() => toggleMethod(method)} className="hover:text-primary/70" aria-label={`Remove ${method} filter`}>&times;</button>
                </span>
              ))}
              <button type="button" onClick={clearAllFilters} className="text-muted-foreground hover:text-foreground underline" aria-label="Clear all active filters">
                Clear all
              </button>
            </div>
          )}
        </div>
      )}

      {loading && (
        <div className="space-y-4" role="status" aria-label="Loading publications">
          <span className="sr-only">Loading publications...</span>
          <div className="grid gap-4">
            {Array.from({ length: 3 }).map((_, i) => (
              <Card key={i} className="h-32 animate-pulse bg-muted/50" />
            ))}
          </div>
        </div>
      )}
      {error && (
        <Card className="border-amber-200 dark:border-amber-900">
          <CardContent className="py-4 text-center text-sm text-amber-700 dark:text-amber-400">
            Unable to load publications. Please check the backend API connection and try again.
          </CardContent>
        </Card>
      )}

      {!loading && papers.length === 0 && !error && (
        <Card>
          <CardContent className="py-12 text-center">
            <p className="text-lg font-medium mb-2">No published papers yet</p>
            <p className="text-sm text-muted-foreground max-w-lg mx-auto">
              Papers progress through the pipeline: generation, 5-layer review, tournament
              ranking, then release. Once papers reach candidate or public status, they
              appear here.
            </p>
            <div className="mt-4 flex items-center justify-center gap-2 text-xs text-muted-foreground" aria-label="Release pipeline">
              <span className="rounded bg-gray-100 dark:bg-gray-800 px-2 py-0.5">Internal</span>
              <span>&rarr;</span>
              <span className="rounded bg-amber-100 dark:bg-amber-900/40 px-2 py-0.5 text-amber-800 dark:text-amber-300">Candidate</span>
              <span>&rarr;</span>
              <span className="rounded bg-blue-100 dark:bg-blue-900/40 px-2 py-0.5 text-blue-800 dark:text-blue-300">Submitted</span>
              <span>&rarr;</span>
              <span className="rounded bg-green-100 dark:bg-green-900/40 px-2 py-0.5 text-green-800 dark:text-green-300">Public</span>
            </div>

            <div className="mt-6 max-w-md mx-auto rounded-lg border border-blue-200 dark:border-blue-900 bg-blue-50/40 dark:bg-blue-950/20 p-4 text-left">
              <p className="text-sm font-medium text-blue-800 dark:text-blue-300 mb-2">
                While the pipeline seeds, here&apos;s what to review:
              </p>
              <ul className="text-xs text-blue-700/90 dark:text-blue-400/90 space-y-1.5">
                <li>
                  <Link href="/methodology" className="hover:underline">
                    → <strong>Methodology</strong> — every pipeline stage, gate, and improvement loop
                  </Link>
                </li>
                <li>
                  <Link href="/glossary" className="hover:underline">
                    → <strong>Glossary</strong> — terminology reference (TrueSkill, RSI, autonomy, …)
                  </Link>
                </li>
                <li>
                  <Link href="/reliability" className="hover:underline">
                    → <strong>Reliability</strong> — five quality metrics tracked per family
                  </Link>
                </li>
                <li>
                  <Link href="/corrections" className="hover:underline">
                    → <strong>Corrections</strong> — every error the system catches, published openly
                  </Link>
                </li>
              </ul>
            </div>
          </CardContent>
        </Card>
      )}

      <div className="grid gap-4">
        {filteredPapers.length === 0 && papers.length > 0 && hasActiveFilters && (
          <div className="text-center py-8">
            <p className="text-lg font-medium mb-1">0 papers match your filters</p>
            <p className="text-sm text-muted-foreground mb-3">Try broadening your search or removing some filters.</p>
            <button type="button" onClick={clearAllFilters} className="inline-flex items-center gap-1 text-sm text-primary hover:underline font-medium">
              Clear all filters &rarr;
            </button>
          </div>
        )}
        {filteredPapers.map((paper) => (
          <Link key={paper.id} href={`/papers/${paper.id}`} className="block focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 rounded-lg">
            <Card className="hover:shadow-md transition-all cursor-pointer group-focus-within:ring-2 group-focus-within:ring-primary/20">
              <CardHeader className="pb-2">
                <div className="flex items-start justify-between gap-4">
                  <CardTitle className="text-lg leading-snug">
                    {paper.title}
                  </CardTitle>
                  <div className="flex items-center gap-1.5 shrink-0">
                    <Badge variant="outline" className="text-[11px] text-amber-700 dark:text-amber-400 border-amber-300 dark:border-amber-700">
                      AI-Generated
                    </Badge>
                    <Badge
                      variant="secondary"
                      className={
                        statusColor[paper.release_status] ?? "bg-gray-100"
                      }
                    >
                      {paper.release_status}
                    </Badge>
                  </div>
                </div>
                <CardDescription className="flex gap-2 flex-wrap mt-1">
                  {paper.family_id && (
                    <span className="text-xs font-mono">
                      {paper.family_id}
                    </span>
                  )}
                  {paper.method && (
                    <Badge variant="outline" className="text-xs">
                      {paper.method}
                    </Badge>
                  )}
                  {paper.category && (
                    <Badge variant="outline" className="text-xs">
                      {paper.category}
                    </Badge>
                  )}
                  {paper.review_status && (
                    <span className="inline-flex items-center gap-0.5 text-xs text-emerald-700 dark:text-emerald-400">
                      <svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"/></svg>
                      {paper.review_status.replace(/_/g, " ")}
                    </span>
                  )}
                  {paper.rating && (
                    <span className="text-xs font-medium text-indigo-700 dark:text-indigo-400" title={`TrueSkill conservative rating (mu - 3*sigma). Elo: ${paper.rating.elo.toFixed(0)}, ${paper.rating.matches_played} matches played.`}>
                      Rating: {paper.rating.conservative_rating.toFixed(1)}
                    </span>
                  )}
                  {paper.novelty_score != null && (
                    <span className="text-xs text-muted-foreground" title="Novelty score on a 0-10 scale (higher = more novel)">
                      Novelty: {paper.novelty_score.toFixed(1)}/10
                    </span>
                  )}
                  {paper.created_at && (
                    <span className="text-xs text-muted-foreground">
                      {new Date(paper.created_at).toLocaleDateString()}
                    </span>
                  )}
                </CardDescription>
              </CardHeader>
              {paper.abstract && (
                <CardContent>
                  <p className="text-sm text-muted-foreground line-clamp-3">
                    {paper.abstract}
                  </p>
                </CardContent>
              )}
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}
