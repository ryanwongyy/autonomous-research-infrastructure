"use client";

import { memo } from "react";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { PaperFamily } from "@/lib/types";
import { cn } from "@/lib/utils";

interface FamilyCardProps {
  family: PaperFamily;
}

const lockProtocolColors: Record<string, string> = {
  "venue-lock": "bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-300",
  "method-lock": "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300",
  open: "bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300",
};

function lockLabel(protocol: string): string {
  return protocol
    .replace(/-/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

export const FamilyCard = memo(function FamilyCard({ family }: FamilyCardProps) {
  return (
    <Link href={`/families/${family.id}`} className="block group" aria-label={`View family: ${family.name} (${family.paper_count} papers)`}>
      <Card className="h-full transition-shadow hover:shadow-md group-hover:ring-2 group-hover:ring-primary/20">
        <CardHeader className="pb-2">
          <div className="flex items-start justify-between gap-2">
            <CardTitle className="text-base leading-snug">
              {family.short_name}
            </CardTitle>
            <span
              className={cn(
                "inline-flex items-center rounded-md px-1.5 py-0.5 text-[10px] font-semibold shrink-0",
                lockProtocolColors[family.lock_protocol_type] ?? "bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300"
              )}
            >
              {lockLabel(family.lock_protocol_type)}
            </span>
          </div>
          <CardDescription className="line-clamp-2 text-xs">
            {family.description}
          </CardDescription>
        </CardHeader>
        <CardContent className="pt-0">
          <div className="flex items-center gap-3 text-xs text-muted-foreground">
            <span className="font-semibold text-foreground text-sm">
              {family.paper_count}
            </span>
            <span>papers</span>
          </div>
          {family.elite_ceiling && (
            <p className="mt-1.5 text-[11px] text-muted-foreground truncate">
              Ceiling: {family.elite_ceiling}
            </p>
          )}
          {family.venue_ladder && (
            <div className="mt-2 flex flex-wrap gap-1">
              {family.venue_ladder.flagship.slice(0, 2).map((v) => (
                <Badge key={v} variant="secondary" className="text-[10px] px-1.5 py-0">
                  {v}
                </Badge>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </Link>
  );
});
