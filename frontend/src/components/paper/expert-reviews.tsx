import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { ScoreBar } from "@/components/paper/score-bar";
import type { ExpertReview } from "@/lib/types";

export function ExpertReviewsSection({ reviews }: { reviews: ExpertReview[] }) {
  if (reviews.length === 0) return null;

  return (
    <>
      <Separator className="my-6" />
      <h2 className="text-xl font-semibold mb-4">Expert Reviews</h2>
      <div className="space-y-4">
        {reviews.map((review) => (
          <Card key={review.id}>
            <CardHeader className="pb-2">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <CardTitle className="text-base">{review.expert_name}</CardTitle>
                  <div className="flex items-center gap-2 mt-1">
                    {review.affiliation && (
                      <span className="text-xs text-muted-foreground">{review.affiliation}</span>
                    )}
                    {review.review_date && (
                      <span className="text-xs text-muted-foreground">
                        {new Date(review.review_date).toLocaleDateString()}
                      </span>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Badge variant={review.is_pre_submission ? "outline" : "secondary"} className="text-[11px]">
                    {review.is_pre_submission ? "Pre-submission" : "Post-submission"}
                  </Badge>
                  <div className="text-right">
                    <div className="text-2xl font-bold font-mono">{review.overall_score.toFixed(1)}</div>
                    <div className="text-[11px] text-muted-foreground">Overall</div>
                  </div>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="space-y-2">
                {review.methodology_score != null && (
                  <ScoreBar
                    label="Methodology"
                    score={review.methodology_score}
                    max={5}
                    color="bg-blue-500 dark:bg-blue-400"
                  />
                )}
                {review.contribution_score != null && (
                  <ScoreBar
                    label="Contribution"
                    score={review.contribution_score}
                    max={5}
                    color="bg-emerald-500 dark:bg-emerald-400"
                  />
                )}
              </div>
              {review.notes && (
                review.notes.length > 300 ? (
                  <details className="border-t pt-3">
                    <summary className="text-sm text-primary cursor-pointer hover:underline">
                      Review notes ({review.notes.length} characters)
                    </summary>
                    <p className="text-sm text-muted-foreground leading-relaxed mt-2">
                      {review.notes}
                    </p>
                  </details>
                ) : (
                  <p className="text-sm text-muted-foreground leading-relaxed border-t pt-3">
                    {review.notes}
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
