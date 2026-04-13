"use client";

import { memo } from "react";
import { cn } from "@/lib/utils";

interface SourceTierBadgeProps {
  tier: "A" | "B" | "C";
  className?: string;
}

const tierConfig: Record<
  string,
  { bg: string; text: string; label: string }
> = {
  A: { bg: "bg-emerald-100 dark:bg-emerald-900/40", text: "text-emerald-700 dark:text-emerald-300", label: "Tier A" },
  B: { bg: "bg-blue-100 dark:bg-blue-900/40", text: "text-blue-700 dark:text-blue-300", label: "Tier B" },
  C: { bg: "bg-amber-100 dark:bg-amber-900/40", text: "text-amber-700 dark:text-amber-300", label: "Tier C" },
};

export const SourceTierBadge = memo(function SourceTierBadge({ tier, className }: SourceTierBadgeProps) {
  const config = tierConfig[tier] ?? tierConfig.C;
  return (
    <span
      className={cn(
        "inline-flex items-center justify-center rounded-md px-2 py-0.5 text-xs font-semibold",
        config.bg,
        config.text,
        className
      )}
    >
      {config.label}
    </span>
  );
});
