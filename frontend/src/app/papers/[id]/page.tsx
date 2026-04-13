import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { ReviewStatusBadge } from "@/components/leaderboard/review-status-badge";
import type { Metadata } from "next";
import { serverFetch } from "@/lib/api";
import type { CollegialSession, CollegialExchangeItem, AcknowledgmentItem, QualityAssessment } from "@/lib/types";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ id: string }>;
}): Promise<Metadata> {
  const { id } = await params;
  try {
    const paper = await serverFetch<{ title: string; abstract?: string | null }>(`/papers/${id}`);
    return { title: paper.title, description: paper.abstract?.slice(0, 160) ?? "Paper detail page." };
  } catch { /* fallback */ }
  return { title: `Paper ${id}` };
}

interface PaperDetail {
  id: string;
  title: string;
  abstract: string | null;
  source: string;
  category: string | null;
  country: string | null;
  method: string | null;
  status: string;
  review_status: string;
  mu: number | null;
  sigma: number | null;
  conservative_rating: number | null;
  elo: number | null;
  matches_played: number | null;
  rank: number | null;
  created_at: string;
}

interface ReviewItem {
  id: number;
  stage: string;
  model_used: string;
  verdict: string;
  content: string;
  iteration: number;
  created_at: string;
  policy_scores_json?: string | null;
}

export default async function PaperPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  let paper: PaperDetail | null = null;
  let reviews: ReviewItem[] = [];
  let collegialSession: CollegialSession | null = null;
  let apiError = false;

  try {
    const [paperResult, reviewsResult, collegialResult] = await Promise.allSettled([
      serverFetch<PaperDetail>(`/papers/${id}`),
      serverFetch<ReviewItem[]>(`/papers/${id}/reviews`),
      serverFetch<CollegialSession>(`/papers/${id}/collegial-session`),
    ]);
    if (paperResult.status === "fulfilled") paper = paperResult.value;
    if (reviewsResult.status === "fulfilled") reviews = reviewsResult.value;
    if (collegialResult.status === "fulfilled") collegialSession = collegialResult.value;
  } catch {
    apiError = true;
  }

  if (!paper) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-8 text-center">
        <h1 className="text-2xl font-bold">{apiError ? "API Unavailable" : "Paper not found"}</h1>
        <p className="text-muted-foreground mt-2">
          {apiError
            ? "Unable to connect to the backend API. Please try again later."
            : <>Paper &ldquo;{id}&rdquo; does not exist.</>}
        </p>
        <Link href="/leaderboard" className="mt-4 inline-block text-primary hover:underline text-sm">
          Back to Leaderboard
        </Link>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-4xl px-4 py-8">
      <nav className="mb-4 text-sm text-muted-foreground">
        <Link href="/leaderboard" className="hover:text-foreground">
          Leaderboard
        </Link>
        <span className="mx-2">/</span>
        <span className="text-foreground truncate">{paper.title.length > 60 ? paper.title.slice(0, 57) + "..." : paper.title}</span>
      </nav>

      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">{paper.title}</h1>
          <div className="mt-2 flex items-center gap-2">
            <Badge>{paper.source.toUpperCase()}</Badge>
            {paper.category && <Badge variant="secondary">{paper.category}</Badge>}
            {paper.method && <Badge variant="outline">{paper.method}</Badge>}
            <ReviewStatusBadge status={paper.review_status} />
          </div>
        </div>
        {paper.rank && (
          <div className="text-right">
            <div className="text-3xl font-bold">#{paper.rank}</div>
            <div className="text-sm text-muted-foreground">Global Rank</div>
          </div>
        )}
      </div>

      {paper.abstract && (
        <Card className="mt-6">
          <CardHeader>
            <CardTitle className="text-base">Abstract</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">{paper.abstract}</p>
          </CardContent>
        </Card>
      )}

      {/* Ratings */}
      {paper.mu !== null && (
        <>
          <Separator className="my-6" />
          <h2 className="text-xl font-semibold mb-4">Ratings</h2>
          <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
            <Card>
              <CardHeader className="pb-1">
                <CardDescription>&mu; (TrueSkill)</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold font-mono">
                  {paper.mu?.toFixed(1)}
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-1">
                <CardDescription>&sigma; (Uncertainty)</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold font-mono">
                  {paper.sigma?.toFixed(1)}
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-1">
                <CardDescription>Conservative</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold font-mono">
                  {paper.conservative_rating?.toFixed(1)}
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-1">
                <CardDescription>Elo</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold font-mono">
                  {paper.elo?.toFixed(0)}
                </div>
              </CardContent>
            </Card>
          </div>
        </>
      )}

      {/* Reviews */}
      {reviews.length > 0 && (
        <>
          <Separator className="my-6" />
          <h2 className="text-xl font-semibold mb-4">Reviews</h2>
          <div className="space-y-4">
            {reviews.map((review) => (
              <Card key={review.id}>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-base capitalize">
                      {review.stage} Review
                      {review.iteration > 1 && ` (Iteration ${review.iteration})`}
                    </CardTitle>
                    <Badge
                      variant={
                        review.verdict === "pass"
                          ? "default"
                          : review.verdict === "fail"
                          ? "destructive"
                          : "secondary"
                      }
                    >
                      {review.verdict}
                    </Badge>
                  </div>
                  <CardDescription>
                    Model: {review.model_used}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-muted-foreground whitespace-pre-wrap">
                    {review.content.slice(0, 500)}
                    {review.content.length > 500 && "..."}
                  </p>
                </CardContent>
              </Card>
            ))}
          </div>
        </>
      )}

      {/* Collegial Review — Convergence Loop */}
      {collegialSession && (
        <>
          <Separator className="my-6" />
          <h2 className="text-xl font-semibold mb-4">Collegial Review</h2>

          {/* Session overview card */}
          <Card className="border-l-4 border-l-indigo-500">
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="text-base">
                  Review Session
                  {collegialSession.target_venue && (
                    <span className="ml-2 text-sm font-normal text-muted-foreground">
                      Target: {collegialSession.target_venue}
                    </span>
                  )}
                </CardTitle>
                <div className="flex items-center gap-2">
                  {collegialSession.current_round > 0 && (
                    <Badge variant="outline" className="text-[10px]">
                      Round {collegialSession.current_round}/{collegialSession.max_rounds}
                    </Badge>
                  )}
                  <Badge
                    variant={
                      collegialSession.status === "converged"
                        ? "default"
                        : collegialSession.status === "in_progress"
                        ? "secondary"
                        : collegialSession.status === "plateaued"
                        ? "outline"
                        : "outline"
                    }
                    className={
                      collegialSession.status === "converged"
                        ? "bg-emerald-600 hover:bg-emerald-700"
                        : ""
                    }
                  >
                    {collegialSession.status === "converged"
                      ? "Ready for Submission"
                      : collegialSession.status === "max_rounds_reached"
                      ? "Max Rounds Reached"
                      : collegialSession.status === "plateaued"
                      ? "Plateaued"
                      : collegialSession.status}
                  </Badge>
                </div>
              </div>
              {collegialSession.session_summary && (
                <CardDescription className="mt-2 leading-relaxed">
                  {collegialSession.session_summary}
                </CardDescription>
              )}
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
                {collegialSession.final_quality_score != null && (
                  <div className="rounded-md bg-indigo-50 dark:bg-indigo-950/30 p-3 text-center">
                    <div className="text-2xl font-bold font-mono text-indigo-700 dark:text-indigo-400">
                      {collegialSession.final_quality_score.toFixed(1)}
                    </div>
                    <div className="text-xs text-muted-foreground">Quality Score</div>
                  </div>
                )}
                <div className="rounded-md bg-muted/50 p-3 text-center">
                  <div className="text-2xl font-bold font-mono">{collegialSession.total_exchanges}</div>
                  <div className="text-xs text-muted-foreground">Exchanges</div>
                </div>
                <div className="rounded-md bg-emerald-50 dark:bg-emerald-950/30 p-3 text-center">
                  <div className="text-2xl font-bold font-mono text-emerald-700 dark:text-emerald-400">
                    {collegialSession.suggestions_accepted}
                  </div>
                  <div className="text-xs text-muted-foreground">Accepted</div>
                </div>
                <div className="rounded-md bg-red-50 dark:bg-red-950/30 p-3 text-center">
                  <div className="text-2xl font-bold font-mono text-red-700 dark:text-red-400">
                    {collegialSession.suggestions_rejected}
                  </div>
                  <div className="text-xs text-muted-foreground">Rejected</div>
                </div>
                <div className="rounded-md bg-amber-50 dark:bg-amber-950/30 p-3 text-center">
                  <div className="text-2xl font-bold font-mono text-amber-700 dark:text-amber-400">
                    {collegialSession.suggestions_partially_incorporated}
                  </div>
                  <div className="text-xs text-muted-foreground">Partial</div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Quality Trajectory — shows improvement across rounds */}
          {collegialSession.quality_trajectory && collegialSession.quality_trajectory.length > 0 && (
            <div className="mt-4">
              <h3 className="text-base font-semibold mb-3">Quality Trajectory</h3>
              <div className="space-y-3">
                {collegialSession.quality_trajectory.map((qa: QualityAssessment) => (
                  <Card key={qa.round} className={
                    qa.verdict === "ready"
                      ? "border-l-4 border-l-emerald-500"
                      : qa.verdict === "minor_revision"
                      ? "border-l-4 border-l-amber-500"
                      : "border-l-4 border-l-red-400"
                  }>
                    <CardHeader className="pb-2">
                      <div className="flex items-center justify-between">
                        <CardTitle className="text-sm">
                          Round {qa.round}
                        </CardTitle>
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-mono font-bold">
                            {qa.overall_score?.toFixed(1)}/10
                          </span>
                          <Badge
                            variant={qa.verdict === "ready" ? "default" : "outline"}
                            className={
                              qa.verdict === "ready"
                                ? "bg-emerald-600 text-[10px]"
                                : "text-[10px]"
                            }
                          >
                            {qa.verdict === "ready"
                              ? "Ready"
                              : qa.verdict === "minor_revision"
                              ? "Minor Revision"
                              : "Major Revision"}
                          </Badge>
                        </div>
                      </div>
                    </CardHeader>
                    <CardContent>
                      {/* Dimension scores as bars */}
                      {qa.dimensions && (
                        <div className="space-y-1.5 mb-3">
                          {Object.entries(qa.dimensions).map(([dim, score]) => (
                            <div key={dim} className="flex items-center gap-2">
                              <span className="text-[10px] text-muted-foreground w-32 truncate">
                                {dim.replace(/_/g, " ")}
                              </span>
                              <div className="flex-1 h-2 rounded-full bg-muted overflow-hidden">
                                <div
                                  className={`h-full rounded-full transition-all ${
                                    (score as number) >= 7
                                      ? "bg-emerald-500"
                                      : (score as number) >= 5
                                      ? "bg-amber-500"
                                      : "bg-red-500"
                                  }`}
                                  style={{ width: `${((score as number) / 10) * 100}%` }}
                                />
                              </div>
                              <span className="text-[10px] font-mono w-6 text-right">
                                {score as number}
                              </span>
                            </div>
                          ))}
                        </div>
                      )}
                      {/* Remaining gaps */}
                      {qa.remaining_gaps && qa.remaining_gaps.length > 0 && (
                        <div className="mt-2">
                          <span className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wide">
                            Remaining gaps
                          </span>
                          <div className="mt-1 space-y-1">
                            {qa.remaining_gaps.map((gap, i) => (
                              <div key={i} className="flex items-start gap-1.5 text-xs text-muted-foreground">
                                <Badge variant="outline" className="text-[9px] px-1 py-0 shrink-0">
                                  {gap.priority}
                                </Badge>
                                <span>{gap.gap}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                      {/* Assessor note */}
                      {qa.assessor_note && (
                        <p className="mt-2 text-xs italic text-muted-foreground">
                          {qa.assessor_note}
                        </p>
                      )}
                    </CardContent>
                  </Card>
                ))}
              </div>
            </div>
          )}

          {/* Dialogue thread — grouped by round */}
          {collegialSession.exchanges.length > 0 && (
            <div className="mt-4">
              <h3 className="text-base font-semibold mb-3">Dialogue</h3>
              <div className="space-y-3">
                {collegialSession.exchanges
                  .filter((e: CollegialExchangeItem) => e.exchange_type !== "quality_assessment")
                  .map((exchange: CollegialExchangeItem) => {
                  const isColleague = exchange.speaker_role === "colleague";
                  const isDrafter = exchange.speaker_role === "drafter";
                  const colleagueColors = [
                    "border-l-blue-500",
                    "border-l-violet-500",
                    "border-l-teal-500",
                    "border-l-rose-500",
                    "border-l-orange-500",
                  ] as const;
                  const colorClass = isColleague
                    ? colleagueColors[(exchange.colleague_id ?? 0) % colleagueColors.length]
                    : "";

                  return (
                    <div
                      key={exchange.id}
                      className={
                        isColleague
                          ? `rounded-lg border-l-4 ${colorClass} bg-card p-4 shadow-sm`
                          : isDrafter
                          ? "ml-8 rounded-lg border border-dashed border-muted-foreground/25 bg-muted/40 p-4"
                          : "ml-4 rounded-lg border border-indigo-200 dark:border-indigo-800 bg-indigo-50/50 dark:bg-indigo-950/20 p-4"
                      }
                    >
                      <div className="flex items-center gap-2 mb-1.5">
                        <span className="text-sm font-semibold">
                          {isColleague
                            ? `Colleague #${exchange.colleague_id ?? "?"}`
                            : isDrafter
                            ? "Drafter"
                            : "Quality Assessor"}
                        </span>
                        <Badge variant="outline" className="text-[10px] px-1.5 py-0">
                          {exchange.exchange_type.replace(/_/g, " ")}
                        </Badge>
                        {exchange.target_section && (
                          <Badge variant="secondary" className="text-[10px] px-1.5 py-0">
                            {exchange.target_section}
                          </Badge>
                        )}
                        <span className="ml-auto text-[10px] text-muted-foreground tabular-nums">
                          R{exchange.round_number} &middot; T{exchange.turn_number}
                        </span>
                      </div>
                      {exchange.content && (
                        <p className="text-sm text-muted-foreground whitespace-pre-wrap leading-relaxed">
                          {exchange.content.length > 600
                            ? exchange.content.slice(0, 600) + "..."
                            : exchange.content}
                        </p>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Acknowledgments */}
          {collegialSession.acknowledgments.length > 0 && (
            <div className="mt-6">
              <h3 className="text-base font-semibold mb-3">Acknowledgments</h3>
              <div className="space-y-3">
                {collegialSession.acknowledgments.map((ack: AcknowledgmentItem, idx: number) => (
                  <Card key={idx} className="border-l-4 border-l-amber-400">
                    <CardContent className="pt-4">
                      <div className="flex items-center gap-2 mb-2">
                        <span className="text-sm font-semibold">
                          Colleague #{ack.colleague_id}
                        </span>
                        <Badge variant="outline" className="text-[10px] px-1.5 py-0">
                          {ack.contribution_type}
                        </Badge>
                        <span className="ml-auto text-xs text-muted-foreground">
                          {ack.exchanges_count} exchanges &middot; {ack.accepted_suggestions} accepted
                        </span>
                      </div>
                      <p className="text-sm mb-1.5">{ack.contribution_summary}</p>
                      <p className="text-sm italic text-muted-foreground leading-relaxed">
                        {ack.acknowledgment_text}
                      </p>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </div>
          )}
        </>
      )}

      {/* Policy Usefulness Scores (from L3 Method Review) */}
      {(() => {
        const l3Review = reviews.find(
          (r) => r.stage === "l3_method" && r.policy_scores_json
        );
        if (!l3Review?.policy_scores_json) return null;
        let parsed: Record<string, number> | null = null;
        try {
          parsed = JSON.parse(l3Review.policy_scores_json);
        } catch {
          return (
            <>
              <Separator className="my-6" />
              <Card className="border-amber-200 dark:border-amber-900">
                <CardContent className="py-4 text-sm text-amber-700 dark:text-amber-400">
                  Policy usefulness scores are unavailable (invalid data format).
                </CardContent>
              </Card>
            </>
          );
        }
        if (!parsed || typeof parsed !== "object") return null;
        const scores = parsed;
        const dimensions = [
          { key: "actionability", label: "Actionability", color: "bg-blue-500" },
          { key: "specificity", label: "Specificity", color: "bg-purple-500" },
          { key: "evidence_strength", label: "Evidence Strength", color: "bg-emerald-500" },
          { key: "stakeholder_relevance", label: "Stakeholder Relevance", color: "bg-amber-500" },
          { key: "implementation_feasibility", label: "Implementation Feasibility", color: "bg-rose-500" },
        ] as const;
        return (
          <>
            <Separator className="my-6" />
            <h2 className="text-xl font-semibold mb-4">Policy Usefulness</h2>
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Policy-Usefulness Assessment</CardTitle>
                <CardDescription>
                  Scored during L3 Method Review (1-5 scale per dimension)
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {dimensions.map((dim) => {
                    const score = scores[dim.key] ?? 0;
                    return (
                      <div key={dim.key} className="flex items-center gap-3">
                        <span className="w-48 text-sm font-medium shrink-0">
                          {dim.label}
                        </span>
                        <div className="flex-1 h-4 bg-muted rounded-full overflow-hidden">
                          <div
                            className={`h-full rounded-full ${dim.color}`}
                            style={{ width: `${(score / 5) * 100}%` }}
                          />
                        </div>
                        <span className="w-8 text-sm font-mono text-right">
                          {score}/5
                        </span>
                      </div>
                    );
                  })}
                </div>
              </CardContent>
            </Card>
          </>
        );
      })()}
    </div>
  );
}
