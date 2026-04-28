import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { SignificanceMemo } from "@/lib/types";

const verdictColors: Record<string, string> = {
  significant: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300",
  noteworthy: "bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300",
  incremental: "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300",
  insufficient: "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300",
};

export function SignificanceMemoCard({ memo }: { memo: SignificanceMemo }) {
  return (
    <Card className="border-l-4 border-l-blue-500 dark:border-l-blue-400">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between gap-2">
          <CardTitle className="text-base">Editorial Significance</CardTitle>
          <Badge
            variant="secondary"
            className={verdictColors[memo.editorial_verdict.toLowerCase()] ?? ""}
          >
            {memo.editorial_verdict}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-2">
        <p className="text-sm text-muted-foreground leading-relaxed">{memo.memo_text}</p>
        <div className="flex items-center gap-4 text-xs text-muted-foreground">
          <span>
            Author: <strong className="text-foreground">{memo.author}</strong>
          </span>
          {memo.tournament_rank_at_time && (
            <span>
              Rank at assessment: <strong className="text-foreground">#{memo.tournament_rank_at_time}</strong>
            </span>
          )}
          {memo.created_at && (
            <span>{new Date(memo.created_at).toLocaleDateString()}</span>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
