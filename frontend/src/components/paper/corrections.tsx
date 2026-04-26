import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import type { CorrectionRecord } from "@/lib/types";

const severityByType: Record<string, "critical" | "major" | "minor"> = {
  hallucination: "critical",
  fabricated_result: "critical",
  data_error: "major",
  logic_error: "major",
  methodology_error: "major",
  citation_error: "minor",
  formatting_error: "minor",
  typo: "minor",
};

const severityColors = {
  critical: "border-l-red-500 dark:border-l-red-400",
  major: "border-l-amber-500 dark:border-l-amber-400",
  minor: "border-l-blue-500 dark:border-l-blue-400",
};

const severityBadgeColors = {
  critical: "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300",
  major: "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300",
  minor: "bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300",
};

export function CorrectionsSection({ corrections }: { corrections: CorrectionRecord[] }) {
  return (
    <>
      <Separator className="my-6" />
      <h2 className="text-xl font-semibold mb-4">Corrections &amp; Errata</h2>
      {corrections.length === 0 ? (
        <div className="flex items-center gap-2 rounded-lg border border-emerald-200 dark:border-emerald-900 bg-emerald-50/50 dark:bg-emerald-950/20 px-4 py-3 text-sm text-emerald-700 dark:text-emerald-400">
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>
          No corrections recorded. This paper has passed all review layers without published errata.
        </div>
      ) : (
        <>
      <p className="text-xs text-muted-foreground mb-3">
        {corrections.length} correction{corrections.length !== 1 ? "s" : ""} recorded. The system publishes every error it catches.
      </p>
      <div className="space-y-3">
        {corrections.map((correction) => {
          const severity = severityByType[correction.correction_type] ?? "major";
          return (
            <Card
              key={correction.id}
              className={`border-l-4 ${severityColors[severity]} border-amber-200 dark:border-amber-900`}
            >
              <CardContent className="py-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <Badge variant="secondary" className={`text-[11px] ${severityBadgeColors[severity]}`}>
                        {correction.correction_type.replace(/_/g, " ")}
                      </Badge>
                      <span className="text-[11px] font-medium text-muted-foreground uppercase">{severity}</span>
                      {correction.corrected_at && (
                        <span className="text-xs text-muted-foreground">
                          Corrected: {new Date(correction.corrected_at).toLocaleDateString()}
                        </span>
                      )}
                    </div>
                    <p className="text-sm text-muted-foreground leading-relaxed">
                      {correction.description}
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>
        </>
      )}
    </>
  );
}
