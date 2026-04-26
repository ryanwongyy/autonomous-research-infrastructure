"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useSearchParams, useRouter } from "next/navigation";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { getFamilies, getLeaderboard } from "@/lib/api";
import type { PaperFamily, LeaderboardEntry } from "@/lib/types";

export default function LeaderboardPage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const [families, setFamilies] = useState<PaperFamily[]>([]);
  const [selectedFamily, setSelectedFamily] = useState<string>(
    searchParams.get("family") ?? ""
  );
  const [entries, setEntries] = useState<LeaderboardEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [familiesLoading, setFamiliesLoading] = useState(true);
  const resultsRef = useRef<HTMLDivElement>(null);

  const handleFamilyChange = useCallback(
    (familyId: string) => {
      setSelectedFamily(familyId);
      const params = new URLSearchParams(searchParams.toString());
      if (familyId) {
        params.set("family", familyId);
      } else {
        params.delete("family");
      }
      router.replace(`/leaderboard?${params.toString()}`, { scroll: false });
    },
    [searchParams, router]
  );
  const [error, setError] = useState<string | null>(null);

  // Load families on mount
  useEffect(() => {
    async function loadFamilies() {
      try {
        const res = await getFamilies();
        setFamilies(res.families);
      } catch {
        setError("Failed to load families. Ensure the backend API is running.");
      } finally {
        setFamiliesLoading(false);
      }
    }
    loadFamilies();
  }, []);

  // Load leaderboard when family changes
  useEffect(() => {
    if (!selectedFamily) {
      setEntries([]);
      setTotal(0);
      return;
    }

    async function loadLeaderboard() {
      setLoading(true);
      setError(null);
      try {
        const res = await getLeaderboard({
          family_id: selectedFamily,
          per_page: 100,
        });
        setEntries(res.entries);
        setTotal(res.total);
      } catch {
        setEntries([]);
        setTotal(0);
        setError("Failed to load leaderboard data. Please try again.");
      } finally {
        setLoading(false);
        // Move focus to results for screen readers after load
        requestAnimationFrame(() => resultsRef.current?.focus());
      }
    }
    loadLeaderboard();
  }, [selectedFamily]);

  const selectedFamilyData = useMemo(
    () => families.find((f) => f.id === selectedFamily),
    [families, selectedFamily]
  );

  type SortKey = "rank" | "mu" | "sigma" | "conservative_rating" | "elo" | "matches_played";
  type SortDir = "asc" | "desc";
  const [sortKey, setSortKey] = useState<SortKey>("rank");
  const [sortDir, setSortDir] = useState<SortDir>("asc");

  const sortedEntries = useMemo(() => {
    const sorted = [...entries].sort((a, b) => {
      const av = a[sortKey] ?? 0;
      const bv = b[sortKey] ?? 0;
      return sortDir === "asc" ? (av as number) - (bv as number) : (bv as number) - (av as number);
    });
    return sorted;
  }, [entries, sortKey, sortDir]);

  function handleSort(key: SortKey) {
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir(key === "rank" ? "asc" : "desc");
    }
  }

  function sortIndicator(key: SortKey) {
    if (sortKey !== key) return null;
    return <span className="ml-0.5">{sortDir === "asc" ? "▲" : "▼"}</span>;
  }

  return (
    <div className="mx-auto max-w-7xl px-4 py-8">
      <div className="mb-6">
        <h1 className="text-3xl font-bold">Leaderboard</h1>
        <p className="mt-1 text-muted-foreground">
          Papers ranked by estimated quality and reliability, using a Bayesian rating system
          that rewards consistency. Select a family to see its rankings.
        </p>
        <details className="mt-3">
          <summary className="text-xs text-muted-foreground cursor-pointer hover:text-foreground inline-flex items-center gap-1">
            <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/></svg>
            What do these columns mean?
          </summary>
          <div className="mt-2 rounded-lg border bg-muted/30 p-3 text-xs text-muted-foreground space-y-1.5">
            <p><strong className="text-foreground">μ (Mu)</strong> — Mean skill rating from the TrueSkill algorithm. Higher = stronger paper.</p>
            <p><strong className="text-foreground">σ (Sigma)</strong> — Uncertainty in the rating. Lower = more confident. Decreases with more matches. Papers with many matches earn tighter bounds, making their ranking more reliable.</p>
            <p><strong className="text-foreground">Cons.</strong> — Conservative rating (μ − 3σ). The primary ranking metric — a &quot;worst-case&quot; estimate that rewards both skill and consistency. This is why a paper with many matches often ranks higher than one with a better μ but fewer matches.</p>
            <p><strong className="text-foreground">Elo</strong> — Traditional Elo rating for reference. Less accurate than TrueSkill for this use case.</p>
            <p><strong className="text-foreground">MP</strong> — Matches played. More matches = more reliable rating.</p>
            <p><strong className="text-foreground">48h</strong> — Rank change in the last 48 hours. Green ▲ = improved, Red ▼ = declined.</p>
          </div>
        </details>
      </div>

      {/* Family Selector */}
      <div className="mb-6">
        <label
          htmlFor="family-select"
          className="block text-sm font-medium mb-2"
        >
          Paper Family
        </label>
        {familiesLoading ? (
          <div className="h-10 w-64 animate-pulse bg-muted rounded" />
        ) : families.length === 0 ? (
          <Card>
            <CardContent className="py-8 text-center text-muted-foreground">
              <p>No families available. Ensure the backend API is running.</p>
              <Link
                href="/families"
                className="mt-2 inline-block text-primary hover:underline text-sm"
              >
                Go to Families
              </Link>
            </CardContent>
          </Card>
        ) : (
          <select
            id="family-select"
            aria-label="Select paper family"
            aria-describedby={error ? "family-select-error" : undefined}
            value={selectedFamily}
            onChange={(e) => handleFamilyChange(e.target.value)}
            className="rounded-lg border border-border bg-background px-3 py-2 text-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20 w-full max-w-sm"
          >
            <option value="">-- Select a family --</option>
            {families.map((f) => (
              <option key={f.id} value={f.id}>
                {f.short_name} ({f.paper_count} papers)
              </option>
            ))}
          </select>
        )}
      </div>

      {/* Selected family info */}
      {selectedFamilyData && (
        <div className="mb-4 flex items-center gap-3 text-sm text-muted-foreground">
          <span className="font-medium text-foreground">
            {selectedFamilyData.name}
          </span>
          <Badge variant="secondary" className="text-[11px]">
            {selectedFamilyData.lock_protocol_type.replace(/-/g, " ")}
          </Badge>
          <span>{total} papers total</span>
          <Link
            href={`/families/${selectedFamily}`}
            className="text-primary hover:underline ml-auto"
          >
            View family detail
          </Link>
        </div>
      )}

      {/* Error state — linked to select via aria-describedby */}
      {error && (
        <Card id="family-select-error" role="alert" className="mb-4 border-amber-200 dark:border-amber-900">
          <CardContent className="py-4 text-center text-sm text-amber-700 dark:text-amber-400">
            {error}
          </CardContent>
        </Card>
      )}

      {/* Screen-reader live region: announces loading state transitions */}
      <div className="sr-only" aria-live="polite" aria-atomic="true">
        {loading
          ? "Loading leaderboard data…"
          : selectedFamily && entries.length > 0
          ? `Leaderboard loaded. ${entries.length} papers ranked.`
          : selectedFamily && entries.length === 0 && !error
          ? "Leaderboard loaded. No papers ranked yet."
          : null}
      </div>

      {/* No family selected */}
      {!selectedFamily && families.length > 0 && (
        <Card>
          <CardContent className="py-12 text-center">
            <p className="text-lg font-medium mb-2">Select a family to view its rankings</p>
            <p className="text-sm text-muted-foreground max-w-md mx-auto">
              Each family ranks papers using TrueSkill tournament evaluation.
              Click a family below to see how generated papers compare against benchmarks.
            </p>
            <div className="mt-6 grid grid-cols-2 sm:grid-cols-3 gap-2 max-w-lg mx-auto">
              {families.map((f) => (
                <button
                  key={f.id}
                  type="button"
                  className="rounded-lg border border-border bg-muted/30 px-3 py-2 text-sm hover:bg-muted hover:border-primary/40 hover:ring-2 hover:ring-primary/20 focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none transition-all text-left"
                  onClick={() => handleFamilyChange(f.id)}
                >
                  <span className="font-medium text-foreground block truncate">{f.short_name}</span>
                  <span className="text-xs text-muted-foreground">{f.paper_count} papers</span>
                </button>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Loading */}
      {loading && (
        <div className="space-y-2" aria-live="polite" aria-label="Loading leaderboard data">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="h-12 animate-pulse bg-muted rounded" />
          ))}
        </div>
      )}

      {/* Leaderboard Table */}
      {!loading && selectedFamily && (
        <div ref={resultsRef} tabIndex={-1} className="relative rounded-md border outline-none">
          {/* Scroll hint shadow on right edge */}
          <div className="pointer-events-none absolute right-0 top-0 bottom-0 w-8 bg-gradient-to-l from-background to-transparent z-10 md:hidden" aria-hidden="true" />
          <Table>
            <TableCaption>
              Ranked papers for {selectedFamilyData?.name ?? "selected"} family
            </TableCaption>
            <TableHeader>
              <TableRow>
                <TableHead scope="col" className="w-14 cursor-pointer select-none hover:text-foreground" onClick={() => handleSort("rank")}>Rank{sortIndicator("rank")}</TableHead>
                <TableHead scope="col" className="w-14"><abbr title="Rank change in last 48 hours">48h</abbr></TableHead>
                <TableHead scope="col">Paper</TableHead>
                <TableHead scope="col" className="w-20">Source</TableHead>
                <TableHead scope="col" className="w-16 text-right cursor-pointer select-none hover:text-foreground" onClick={() => handleSort("mu")}><abbr title="TrueSkill mean skill rating">&mu;</abbr>{sortIndicator("mu")}</TableHead>
                <TableHead scope="col" className="w-16 text-right cursor-pointer select-none hover:text-foreground" onClick={() => handleSort("sigma")}><abbr title="TrueSkill uncertainty">&sigma;</abbr>{sortIndicator("sigma")}</TableHead>
                <TableHead scope="col" className="w-20 text-right cursor-pointer select-none hover:text-foreground" onClick={() => handleSort("conservative_rating")}><abbr title="Conservative rating (mu minus 3 sigma)">Cons.</abbr>{sortIndicator("conservative_rating")}</TableHead>
                <TableHead scope="col" className="w-16 text-right hidden md:table-cell cursor-pointer select-none hover:text-foreground" onClick={() => handleSort("elo")}><abbr title="Elo rating">Elo</abbr>{sortIndicator("elo")}</TableHead>
                <TableHead scope="col" className="w-12 text-right hidden md:table-cell cursor-pointer select-none hover:text-foreground" onClick={() => handleSort("matches_played")}><abbr title="Matches played">MP</abbr>{sortIndicator("matches_played")}</TableHead>
                <TableHead scope="col" className="w-24">Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {sortedEntries.map((entry) => (
                <TableRow key={entry.paper_id}>
                  <TableCell className="font-medium">
                    {entry.rank ?? "--"}
                  </TableCell>
                  <TableCell>
                    <span
                      className={
                        entry.rank_change_48h > 0
                          ? "text-emerald-600 dark:text-emerald-400"
                          : entry.rank_change_48h < 0
                          ? "text-red-600 dark:text-red-400"
                          : "text-muted-foreground"
                      }
                      aria-label={
                        entry.rank_change_48h > 0
                          ? `Up ${entry.rank_change_48h} ranks`
                          : entry.rank_change_48h < 0
                          ? `Down ${Math.abs(entry.rank_change_48h)} ranks`
                          : "No change"
                      }
                    >
                      {entry.rank_change_48h > 0
                        ? `\u25B2 +${entry.rank_change_48h}`
                        : entry.rank_change_48h < 0
                        ? `\u25BC ${entry.rank_change_48h}`
                        : "--"}
                    </span>
                  </TableCell>
                  <TableCell className="max-w-xs truncate font-medium">
                    <Link href={`/papers/${entry.paper_id}`} className="hover:text-primary hover:underline transition-colors">
                      {entry.title}
                    </Link>
                  </TableCell>
                  <TableCell>
                    <Badge
                      variant={entry.source === "ape" ? "secondary" : "default"}
                    >
                      {entry.source.toUpperCase()}
                    </Badge>
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
                  <TableCell className="text-right font-mono text-sm hidden md:table-cell">
                    {entry.elo.toFixed(0)}
                  </TableCell>
                  <TableCell className="text-right font-mono text-sm hidden md:table-cell">
                    {entry.matches_played}
                  </TableCell>
                  <TableCell>
                    <Badge variant="secondary" className="text-[11px]">
                      {entry.review_status}
                    </Badge>
                  </TableCell>
                </TableRow>
              ))}
              {entries.length === 0 && (
                <TableRow>
                  <TableCell
                    colSpan={10}
                    className="h-32 text-center text-muted-foreground"
                  >
                    <div className="space-y-2">
                      <p>Papers in this family are still being ranked. Check back as new papers enter the tournament.</p>
                      <p className="text-xs">
                        <Link href="/methodology#tournament" className="text-primary hover:underline">
                          Learn how the tournament works
                        </Link>
                        {" · "}
                        <Link href="/glossary#term-trueskill" className="text-primary hover:underline">
                          What is TrueSkill?
                        </Link>
                      </p>
                    </div>
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}
