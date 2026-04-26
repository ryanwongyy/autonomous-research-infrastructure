"use client";

import { memo } from "react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { RankChange } from "./rank-change";
import { ReviewStatusBadge } from "./review-status-badge";
import type { LeaderboardEntry } from "@/lib/types";

interface LeaderboardTableProps {
  entries: LeaderboardEntry[];
}

export const LeaderboardTable = memo(function LeaderboardTable({ entries }: LeaderboardTableProps) {
  return (
    <div className="rounded-md border overflow-x-auto">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead scope="col" className="w-16">Rank</TableHead>
            <TableHead scope="col" className="w-16">48h</TableHead>
            <TableHead scope="col">Paper</TableHead>
            <TableHead scope="col" className="w-20">Source</TableHead>
            <TableHead scope="col" className="w-16 text-right">&mu;</TableHead>
            <TableHead scope="col" className="w-16 text-right">&sigma;</TableHead>
            <TableHead scope="col" className="w-20 text-right">Cons.</TableHead>
            <TableHead scope="col" className="w-16 text-right">Elo</TableHead>
            <TableHead scope="col" className="w-12 text-right">MP</TableHead>
            <TableHead scope="col" className="w-28">Status</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {entries.map((entry) => (
            <TableRow key={entry.paper_id}>
              <TableCell className="font-medium">
                {entry.rank ?? "—"}
              </TableCell>
              <TableCell>
                <RankChange change={entry.rank_change_48h} />
              </TableCell>
              <TableCell className="max-w-xs truncate font-medium">
                {entry.title}
              </TableCell>
              <TableCell>
                <Badge variant={entry.source === "ape" ? "secondary" : "default"}>
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
                <ReviewStatusBadge status={entry.review_status} />
              </TableCell>
            </TableRow>
          ))}
          {entries.length === 0 && (
            <TableRow>
              <TableCell colSpan={10} className="h-24 text-center text-muted-foreground">
                No papers in the leaderboard yet. Import benchmark papers or generate AI papers to get started.
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
    </div>
  );
});
