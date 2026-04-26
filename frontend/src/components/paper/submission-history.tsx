import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import type { SubmissionOutcome } from "@/lib/types";

const decisionColors: Record<string, string> = {
  accepted: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300",
  rejected: "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300",
  "desk-reject": "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300",
  "r&r": "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300",
  "revise-and-resubmit": "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300",
  pending: "bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300",
};

export function SubmissionHistorySection({ outcomes }: { outcomes: SubmissionOutcome[] }) {
  if (outcomes.length === 0) return null;

  return (
    <>
      <Separator className="my-6" />
      <h2 className="text-xl font-semibold mb-4">Submission History</h2>
      <div className="relative space-y-3 pl-6 before:absolute before:left-[9px] before:top-2 before:bottom-2 before:w-px before:bg-border">
        {outcomes.map((outcome, idx) => (
          <Card key={outcome.id} className="relative">
            {/* Timeline dot */}
            <div className={`absolute -left-6 top-5 w-[11px] h-[11px] rounded-full border-2 border-background ${
              outcome.decision?.toLowerCase() === "accepted"
                ? "bg-emerald-500"
                : outcome.decision?.toLowerCase() === "rejected" || outcome.decision?.toLowerCase() === "desk-reject"
                ? "bg-red-500"
                : outcome.decision?.toLowerCase() === "pending"
                ? "bg-blue-500"
                : "bg-amber-500"
            }`} />
            <CardContent className="py-4">
              <div className="flex items-start justify-between gap-3">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="text-[11px] text-muted-foreground font-mono">{idx + 1}.</span>
                    <span className="font-medium text-sm">{outcome.venue_name}</span>
                    {outcome.decision && (
                      <Badge
                        variant="secondary"
                        className={decisionColors[outcome.decision.toLowerCase()] ?? ""}
                      >
                        {outcome.decision}
                      </Badge>
                    )}
                  </div>
                  <div className="flex items-center gap-3 text-xs text-muted-foreground">
                    {outcome.submitted_date && (
                      <span>Submitted: {new Date(outcome.submitted_date).toLocaleDateString()}</span>
                    )}
                    {outcome.decision_date && (
                      <span>Decision: {new Date(outcome.decision_date).toLocaleDateString()}</span>
                    )}
                    {outcome.revision_rounds > 0 && (
                      <span>{outcome.revision_rounds} revision round{outcome.revision_rounds !== 1 ? "s" : ""}</span>
                    )}
                  </div>
                </div>
              </div>
              {outcome.reviewer_feedback_summary && (
                outcome.reviewer_feedback_summary.length > 200 ? (
                  <details className="mt-2 border-t pt-2">
                    <summary className="text-xs text-primary cursor-pointer hover:underline">
                      Reviewer feedback summary
                    </summary>
                    <p className="text-xs text-muted-foreground leading-relaxed mt-1">
                      {outcome.reviewer_feedback_summary}
                    </p>
                  </details>
                ) : (
                  <p className="mt-2 text-xs text-muted-foreground leading-relaxed border-t pt-2">
                    {outcome.reviewer_feedback_summary}
                  </p>
                )
              )}
            </CardContent>
          </Card>
        ))}
      </div>
    </>
  );
}
