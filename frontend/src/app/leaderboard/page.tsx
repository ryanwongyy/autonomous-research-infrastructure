"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
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
  const [families, setFamilies] = useState<PaperFamily[]>([]);
  const [selectedFamily, setSelectedFamily] = useState<string>("");
  const [entries, setEntries] = useState<LeaderboardEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [familiesLoading, setFamiliesLoading] = useState(true);
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
      }
    }
    loadLeaderboard();
  }, [selectedFamily]);

  const selectedFamilyData = families.find((f) => f.id === selectedFamily);

  return (
    <div className="mx-auto max-w-7xl px-4 py-8">
      <div className="mb-6">
        <h1 className="text-3xl font-bold">Leaderboard</h1>
        <p className="mt-1 text-muted-foreground">
          Papers ranked by conservative TrueSkill rating (mu - 3*sigma).
          Select a paper family to view its leaderboard.
        </p>
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
            onChange={(e) => setSelectedFamily(e.target.value)}
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
          <Badge variant="secondary" className="text-[10px]">
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
        <Card id="family-select-error" role="alert" className="mb-4 border-red-200 dark:border-red-900">
          <CardContent className="py-4 text-center text-sm text-red-600 dark:text-red-400">
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
            <p className="text-lg font-medium mb-2">Choose a research family</p>
            <p className="text-sm text-muted-foreground max-w-md mx-auto">
              Each family has its own leaderboard where papers compete via TrueSkill
              tournament ranking. Pick a family to see how papers compare.
            </p>
            <div className="mt-6 grid grid-cols-2 sm:grid-cols-3 gap-2 max-w-lg mx-auto">
              {families.map((f) => (
                <button
                  key={f.id}
                  type="button"
                  className="rounded-lg border border-border bg-background px-3 py-2 text-sm hover:bg-muted hover:border-primary/40 transition-colors text-left"
                  onClick={() => setSelectedFamily(f.id)}
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
        <div className="rounded-md border">
          <Table>
            <TableCaption>
              Ranked papers for {selectedFamilyData?.name ?? "selected"} family
            </TableCaption>
            <TableHeader>
              <TableRow>
                <TableHead className="w-14">Rank</TableHead>
                <TableHead className="w-14"><abbr title="Rank change in last 48 hours">48h</abbr></TableHead>
                <TableHead>Paper</TableHead>
                <TableHead className="w-20">Source</TableHead>
                <TableHead className="w-16 text-right"><abbr title="TrueSkill mean skill rating">&mu;</abbr></TableHead>
                <TableHead className="w-16 text-right"><abbr title="TrueSkill uncertainty">&sigma;</abbr></TableHead>
                <TableHead className="w-20 text-right"><abbr title="Conservative rating (mu minus 3 sigma)">Cons.</abbr></TableHead>
                <TableHead className="w-16 text-right"><abbr title="Elo rating">Elo</abbr></TableHead>
                <TableHead className="w-12 text-right"><abbr title="Matches played">MP</abbr></TableHead>
                <TableHead className="w-24">Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {entries.map((entry) => (
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
                    {entry.title}
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
                  <TableCell className="text-right font-mono text-sm">
                    {entry.elo.toFixed(0)}
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
              {entries.length === 0 && (
                <TableRow>
                  <TableCell
                    colSpan={10}
                    className="h-24 text-center text-muted-foreground"
                  >
                    No papers in this family&apos;s leaderboard yet.
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
