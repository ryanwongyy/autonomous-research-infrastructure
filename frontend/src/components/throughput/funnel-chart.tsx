"use client";

import { memo } from "react";
import { cn } from "@/lib/utils";

interface FunnelChartProps {
  stages: Record<string, number>;
  killed: number;
  className?: string;
}

const stageColors: Record<string, string> = {
  scouting: "bg-violet-500 dark:bg-violet-400",
  design: "bg-blue-500 dark:bg-blue-400",
  data_collection: "bg-cyan-500 dark:bg-cyan-400",
  analysis: "bg-teal-500 dark:bg-teal-400",
  drafting: "bg-green-500 dark:bg-green-400",
  verification: "bg-yellow-500 dark:bg-yellow-400",
  packaging: "bg-orange-500 dark:bg-orange-400",
  submission_ready: "bg-emerald-600 dark:bg-emerald-400",
};

function stageLabel(key: string): string {
  return key
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

export const FunnelChart = memo(function FunnelChart({ stages, killed, className }: FunnelChartProps) {
  const entries = Object.entries(stages);
  const maxValue = Math.max(...entries.map(([, v]) => v), killed, 1);

  const summaryLabel = entries.map(([s, c]) => `${stageLabel(s)}: ${c}`).join(", ") + `, Killed: ${killed}`;

  return (
    <div className={cn("space-y-2", className)} role="img" aria-label={`Pipeline funnel. ${summaryLabel}`}>
      {entries.map(([stage, count]) => {
        const widthPct = Math.max((count / maxValue) * 100, 2);
        const color = stageColors[stage] ?? "bg-gray-400";
        return (
          <div key={stage} className="flex items-center gap-3">
            <span className="w-20 sm:w-36 shrink-0 text-right text-xs text-muted-foreground truncate">
              {stageLabel(stage)}
            </span>
            <div className="flex-1 h-6 bg-muted rounded overflow-hidden">
              <div
                className={cn("h-full rounded transition-all", color)}
                style={{ width: `${widthPct}%` }}
              />
            </div>
            <span className="w-8 shrink-0 text-xs font-mono font-semibold text-right">
              {count}
            </span>
          </div>
        );
      })}
      {/* Killed row */}
      <div className="flex items-center gap-3">
        <span className="w-20 sm:w-36 shrink-0 text-right text-xs text-muted-foreground">
          Killed
        </span>
        <div className="flex-1 h-6 bg-muted rounded overflow-hidden">
          <div
            className="h-full rounded bg-red-500 dark:bg-red-400 transition-all"
            style={{ width: `${Math.max((killed / maxValue) * 100, 2)}%` }}
          />
        </div>
        <span className="w-8 shrink-0 text-xs font-mono font-semibold text-right">
          {killed}
        </span>
      </div>
    </div>
  );
});
