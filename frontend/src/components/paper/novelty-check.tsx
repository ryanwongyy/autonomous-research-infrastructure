import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { NoveltyCheck } from "@/lib/types";

const verdictColors: Record<string, string> = {
  novel: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300",
  partially_novel: "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300",
  incremental: "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300",
  derivative: "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300",
};

export function NoveltyCheckCard({ check }: { check: NoveltyCheck }) {
  const similarityPct = Math.round(check.highest_similarity_score * 100);

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between gap-2">
          <CardTitle className="text-base">Novelty Assessment</CardTitle>
          <Badge
            variant="secondary"
            className={verdictColors[check.verdict.toLowerCase()] ?? ""}
          >
            {check.verdict.replace(/_/g, " ")}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex items-center gap-4">
          {/* Similarity gauge */}
          <div className="flex-1">
            <div className="flex items-center justify-between text-xs text-muted-foreground mb-1">
              <span>Highest similarity</span>
              <span className="font-mono font-semibold text-foreground">{similarityPct}%</span>
            </div>
            <div className="h-2 bg-muted rounded-full overflow-hidden" role="meter" aria-label="Highest similarity score" aria-valuenow={similarityPct} aria-valuemin={0} aria-valuemax={100}>
              <div
                className={`h-full rounded-full transition-all ${
                  similarityPct >= 80
                    ? "bg-red-500 dark:bg-red-400"
                    : similarityPct >= 50
                    ? "bg-amber-500 dark:bg-amber-400"
                    : "bg-emerald-500 dark:bg-emerald-400"
                }`}
                style={{ width: `${similarityPct}%` }}
              />
            </div>
          </div>
          <div className="text-right">
            <div className="text-lg font-bold font-mono">{check.checked_against_count}</div>
            <div className="text-[11px] text-muted-foreground">papers checked</div>
          </div>
        </div>

        {check.similar_papers.length > 0 && (
          <div className="border-t pt-2">
            <p className="text-xs text-muted-foreground mb-1.5">
              Most similar papers (click to compare):
            </p>
            <ul className="space-y-1.5">
              {check.similar_papers.slice(0, 5).map((sp) => (
                <li key={sp.paper_id} className="flex items-center justify-between text-xs gap-2">
                  <Link
                    href={`/papers/${sp.paper_id}`}
                    className="text-primary hover:underline truncate max-w-[70%] inline-flex items-center gap-1"
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className="shrink-0"><path d="M6 2H14l6 6v12a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2z"/><path d="M14 2v6h6"/></svg>
                    {sp.paper_id}
                  </Link>
                  <div className="flex items-center gap-1.5">
                    <div className="w-12 h-1.5 bg-muted rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full ${
                          sp.similarity >= 0.8 ? "bg-red-500" : sp.similarity >= 0.5 ? "bg-amber-500" : "bg-emerald-500"
                        }`}
                        style={{ width: `${sp.similarity * 100}%` }}
                      />
                    </div>
                    <span className="font-mono text-muted-foreground w-8 text-right">{Math.round(sp.similarity * 100)}%</span>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        )}

        <p className="text-[11px] text-muted-foreground mt-2">
          Checked via {check.model_used} against {check.checked_against_count} papers using research question, data source, and method similarity.
        </p>
      </CardContent>
    </Card>
  );
}
