"use client";

import { memo } from "react";
import { cn } from "@/lib/utils";

interface FunnelChartProps {
  stages: Record<string, number>;
  killed: number;
  className?: string;
}

const stageColors: Record<string, string> = {
  scouting: "bg-violet-500",
  design: "bg-blue-500",
  data_collection: "bg-cyan-500",
  analysis: "bg-teal-500",
  drafting: "bg-green-500",
  verification: "bg-yellow-500",
  packaging: "bg-orange-500",
  submission_ready: "bg-emerald-600",
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
            <span className="w-36 shrink-0 text-right text-xs text-muted-foreground">
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
        <span className="w-36 shrink-0 text-right text-xs text-muted-foreground">
          Killed
        </span>
        <div className="flex-1 h-6 bg-muted rounded overflow-hidden">
          <div
            className="h-full rounded bg-red-500 transition-all"
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
