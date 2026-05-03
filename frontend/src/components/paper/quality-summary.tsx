import { Card, CardContent } from "@/components/ui/card";

interface QualitySummaryProps {
  /** Number of review layers that passed */
  reviewLayersPassed: number;
  /** Total review layers attempted */
  reviewLayersTotal: number;
  /** Collegial review final quality score (0-10) */
  qualityScore: number | null;
  /** Average expert review score (0-10) */
  expertScore: number | null;
  /** TrueSkill conservative rating */
  conservativeRating: number | null;
  /** Global rank */
  rank: number | null;
  /** Novelty verdict string */
  noveltyVerdict: string | null;
  /** Number of corrections filed */
  correctionsCount: number;
}

function Indicator({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-1 px-3 py-2 min-w-[80px]">
      <div className="text-lg font-bold font-mono leading-none">{children}</div>
      <div className="text-[11px] text-muted-foreground text-center leading-tight">{label}</div>
    </div>
  );
}

function scoreColor(score: number, max: number): string {
  const pct = score / max;
  if (pct >= 0.7) return "text-emerald-600 dark:text-emerald-400";
  if (pct >= 0.5) return "text-amber-600 dark:text-amber-400";
  return "text-red-600 dark:text-red-400";
}

export function QualitySummary(props: QualitySummaryProps) {
  const {
    reviewLayersPassed,
    reviewLayersTotal,
    qualityScore,
    expertScore,
    conservativeRating,
    rank,
    noveltyVerdict,
    correctionsCount,
  } = props;

  // Only show if there's at least one meaningful indicator
  const hasAny =
    reviewLayersTotal > 0 ||
    qualityScore !== null ||
    expertScore !== null ||
    conservativeRating !== null;

  if (!hasAny) return null;

  return (
    <Card className="mt-6 border-indigo-200 dark:border-indigo-900 bg-indigo-50/30 dark:bg-indigo-950/20">
      <CardContent className="py-4">
        <div className="flex items-center gap-2 mb-3">
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className="text-indigo-600 dark:text-indigo-400 shrink-0"><path d="M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10z"/><path d="m9 12 2 2 4-4"/></svg>
          <span className="text-sm font-semibold text-indigo-700 dark:text-indigo-300">Quality at a Glance</span>
        </div>
        <div className="flex flex-wrap items-stretch justify-start gap-0 divide-x divide-border">
          {/* Review pipeline */}
          {reviewLayersTotal > 0 && (
            <Indicator label="Reviews Passed">
              <span className={scoreColor(reviewLayersPassed, reviewLayersTotal)}>
                {reviewLayersPassed}/{reviewLayersTotal}
              </span>
            </Indicator>
          )}

          {/* Collegial quality score */}
          {qualityScore !== null && (
            <Indicator label="Quality Score">
              <span className={scoreColor(qualityScore, 10)}>
                {qualityScore.toFixed(1)}
              </span>
              <span className="text-xs text-muted-foreground font-normal">/10</span>
            </Indicator>
          )}

          {/* Expert score */}
          {expertScore !== null && (
            <Indicator label="Expert Score">
              <span className={scoreColor(expertScore, 10)}>
                {expertScore.toFixed(1)}
              </span>
              <span className="text-xs text-muted-foreground font-normal">/10</span>
            </Indicator>
          )}

          {/* Conservative rating */}
          {conservativeRating !== null && (
            <Indicator label="Rating">
              <span className="text-foreground">{conservativeRating.toFixed(1)}</span>
            </Indicator>
          )}

          {/* Rank */}
          {rank !== null && (
            <Indicator label="Rank">
              <span className="text-foreground">#{rank}</span>
            </Indicator>
          )}

          {/* Novelty */}
          {noveltyVerdict !== null && (
            <Indicator label="Novelty">
              <span className={
                noveltyVerdict === "novel"
                  ? "text-emerald-600 dark:text-emerald-400 text-sm"
                  : noveltyVerdict === "borderline"
                  ? "text-amber-600 dark:text-amber-400 text-sm"
                  : "text-red-600 dark:text-red-400 text-sm"
              }>
                {noveltyVerdict.charAt(0).toUpperCase() + noveltyVerdict.slice(1)}
              </span>
            </Indicator>
          )}

          {/* Corrections */}
          <Indicator label="Corrections">
            <span className={correctionsCount === 0
              ? "text-emerald-600 dark:text-emerald-400"
              : "text-amber-600 dark:text-amber-400"
            }>
              {correctionsCount}
            </span>
          </Indicator>
        </div>
      </CardContent>
    </Card>
  );
}
