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
import type { CollegialSession, CollegialExchangeItem, AcknowledgmentItem, QualityAssessment, SignificanceMemo, ExpertReview, SubmissionOutcome, NoveltyCheck, AutonomyCard, CorrectionRecord, ColleagueProfile } from "@/lib/types";
import { SignificanceMemoCard } from "@/components/paper/significance-memo";
import { ExpertReviewsSection } from "@/components/paper/expert-reviews";
import { SubmissionHistorySection } from "@/components/paper/submission-history";
import { NoveltyCheckCard } from "@/components/paper/novelty-check";
import { AutonomyCardSection } from "@/components/paper/autonomy-card";
import { CorrectionsSection } from "@/components/paper/corrections";
import { CitationExport } from "@/components/paper/citation-export";
import { ShareButtons } from "@/components/paper/share-buttons";
import { QualitySummary } from "@/components/paper/quality-summary";
import { ReviewPipelineSummary } from "@/components/paper/review-pipeline-summary";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ id: string }>;
}): Promise<Metadata> {
  const { id } = await params;
  try {
    const paper = await serverFetch<{ title: string; abstract?: string | null; created_at?: string }>(`/papers/${id}`);
    const description = paper.abstract?.slice(0, 200) ?? "Paper detail page.";
    const siteUrl = process.env.NEXT_PUBLIC_SITE_URL || "https://ari.example.com";
    return {
      title: paper.title,
      description,
      alternates: {
        canonical: `${siteUrl}/papers/${id}`,
      },
      openGraph: {
        title: paper.title,
        description,
        type: "article",
        url: `${siteUrl}/papers/${id}`,
        ...(paper.created_at ? { publishedTime: paper.created_at } : {}),
        siteName: "Autonomous Research Infrastructure",
      },
      twitter: {
        card: "summary",
        title: paper.title,
        description,
      },
    };
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
  release_status: string;
  funnel_stage: string;
  mu: number | null;
  sigma: number | null;
  conservative_rating: number | null;
  elo: number | null;
  matches_played: number | null;
  rank: number | null;
  created_at: string;
}

const releaseStatusLabels: Record<string, { label: string; className: string }> = {
  internal: { label: "Internal", className: "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300" },
  candidate: { label: "Candidate", className: "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300" },
  submitted: { label: "Submitted", className: "bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300" },
  public: { label: "Public", className: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300" },
};

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

const reviewStageLabels: Record<string, string> = {
  l1_structure: "L1 Structural",
  l2_provenance: "L2 Provenance",
  l3_method: "L3 Method",
  l4_adversarial: "L4 Adversarial",
  l5_human: "L5 Human",
};

export default async function PaperPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  let paper: PaperDetail | null = null;
  let reviews: ReviewItem[] = [];
  let collegialSession: CollegialSession | null = null;
  let significanceMemo: SignificanceMemo | null = null;
  let expertReviews: ExpertReview[] = [];
  let submissionOutcomes: SubmissionOutcome[] = [];
  let noveltyCheck: NoveltyCheck | null = null;
  let autonomyCard: AutonomyCard | null = null;
  let corrections: CorrectionRecord[] = [];
  let colleagueProfiles: ColleagueProfile[] = [];
  let apiError = false;

  try {
    const [paperResult, reviewsResult, collegialResult, memoResult, expertResult, outcomesResult, noveltyResult, autonomyResult, correctionsResult, profilesResult] = await Promise.allSettled([
      serverFetch<PaperDetail>(`/papers/${id}`),
      serverFetch<ReviewItem[]>(`/papers/${id}/reviews`),
      serverFetch<CollegialSession>(`/papers/${id}/collegial-session`),
      serverFetch<SignificanceMemo>(`/papers/${id}/significance-memo`),
      serverFetch<ExpertReview[]>(`/papers/${id}/expert-reviews`),
      serverFetch<SubmissionOutcome[]>(`/papers/${id}/outcomes`),
      serverFetch<NoveltyCheck>(`/papers/${id}/novelty-check`),
      serverFetch<AutonomyCard>(`/papers/${id}/autonomy-card`),
      serverFetch<CorrectionRecord[]>(`/papers/${id}/corrections`),
      serverFetch<{ profiles: ColleagueProfile[] }>(`/collegial/profiles`),
    ]);
    if (paperResult.status === "fulfilled") paper = paperResult.value;
    if (reviewsResult.status === "fulfilled") reviews = reviewsResult.value;
    if (collegialResult.status === "fulfilled") collegialSession = collegialResult.value;
    if (memoResult.status === "fulfilled") significanceMemo = memoResult.value;
    if (expertResult.status === "fulfilled") expertReviews = expertResult.value;
    if (outcomesResult.status === "fulfilled") submissionOutcomes = outcomesResult.value;
    if (noveltyResult.status === "fulfilled") noveltyCheck = noveltyResult.value;
    if (autonomyResult.status === "fulfilled") autonomyCard = autonomyResult.value;
    if (correctionsResult.status === "fulfilled") corrections = correctionsResult.value;
    if (profilesResult.status === "fulfilled") colleagueProfiles = profilesResult.value.profiles;
  } catch {
    apiError = true;
  }

  if (!paper) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-8 text-center" role="alert">
        <h1 className="text-2xl font-bold">{apiError ? "API Unavailable" : "Paper not found"}</h1>
        <p className="text-muted-foreground mt-2">
          {apiError
            ? "Unable to connect to the backend API. Please try again later."
            : <>Paper &ldquo;{id}&rdquo; does not exist.</>}
        </p>
        <Link href="/publications" className="mt-4 inline-block text-primary hover:underline text-sm">
          Back to Publications
        </Link>
      </div>
    );
  }

  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "ScholarlyArticle",
    name: paper.title,
    ...(paper.abstract ? { abstract: paper.abstract } : {}),
    datePublished: paper.created_at,
    author: { "@type": "Organization", name: "Autonomous Research Infrastructure" },
    publisher: { "@type": "Organization", name: "ARI" },
    ...(paper.category ? { about: paper.category } : {}),
    isAccessibleForFree: true,
    keywords: [paper.category, paper.method, "AI governance"].filter(Boolean),
    creativeWorkStatus: paper.review_status,
    identifier: id,
  };

  return (
    <div className="mx-auto max-w-4xl px-4 py-8">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />
      <nav className="mb-4 text-sm text-muted-foreground" aria-label="Breadcrumb">
        <Link href="/publications" className="hover:text-foreground">
          Publications
        </Link>
        <span className="mx-2" aria-hidden="true">/</span>
        <span className="text-foreground truncate" title={paper.title} aria-current="page">{paper.title.length > 60 ? paper.title.slice(0, 57) + "..." : paper.title}</span>
      </nav>

      {/* Transparency banner */}
      <div className="rounded-md border border-amber-200 dark:border-amber-800 bg-amber-50/50 dark:bg-amber-950/30 px-3 py-2 text-xs text-amber-700 dark:text-amber-300 mb-4">
        This paper was autonomously generated and may contain errors or fabricated results.{" "}
        <Link href="/about" className="underline hover:text-amber-900 dark:hover:text-amber-200">Learn more</Link>
      </div>

      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">{paper.title}</h1>
          <div className="mt-2 flex items-center gap-2 flex-wrap">
            <Badge>{paper.source.toUpperCase()}</Badge>
            {paper.category && <Badge variant="secondary">{paper.category}</Badge>}
            {paper.method && <Badge variant="outline">{paper.method}</Badge>}
            <ReviewStatusBadge status={paper.review_status} />
            {paper.release_status && releaseStatusLabels[paper.release_status] && (
              <Badge variant="secondary" className={`text-[11px] ${releaseStatusLabels[paper.release_status].className}`}>
                {releaseStatusLabels[paper.release_status].label}
              </Badge>
            )}
            <span className="text-xs text-muted-foreground">
              Generated {new Date(paper.created_at).toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric" })}
            </span>
          </div>
        </div>
        {paper.rank && (
          <div className="text-right">
            <div className="text-3xl font-bold">#{paper.rank}</div>
            <div className="text-sm text-muted-foreground">Global Rank</div>
          </div>
        )}
      </div>

      {/* Paper Actions — Cite, Share, Report */}
      <div className="mt-4 flex items-center gap-2 flex-wrap border-y py-3">
        <CitationExport
          title={paper.title}
          paperId={id}
          source={paper.source}
          createdAt={paper.created_at}
          category={paper.category}
        />
        <ShareButtons title={paper.title} paperId={id} />
        <a
          href={`https://github.com/ryanwongyy/autonomous-research-infrastructure/issues/new?title=Paper+${encodeURIComponent(id)}:+&labels=paper-feedback&body=${encodeURIComponent(`Paper: ${paper.title}\nID: ${id}\n\nFeedback:\n`)}`}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1.5 rounded-md border border-border bg-background px-3 py-1.5 text-xs font-medium hover:bg-muted transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary sm:ml-auto"
        >
          <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/></svg>
          Report Issue
        </a>
      </div>

      {/* Quality at a Glance — synthesized indicators for quick researcher assessment */}
      <QualitySummary
        reviewLayersPassed={reviews.filter((r) => r.verdict === "pass").length}
        reviewLayersTotal={reviews.length}
        qualityScore={collegialSession?.final_quality_score ?? null}
        expertScore={
          expertReviews.length > 0
            ? expertReviews.reduce((sum, r) => sum + r.overall_score, 0) / expertReviews.length
            : null
        }
        conservativeRating={paper.conservative_rating}
        rank={paper.rank}
        noveltyVerdict={noveltyCheck?.verdict ?? null}
        correctionsCount={corrections.length}
      />

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

      {/* Researcher engagement callout */}
      {expertReviews.length === 0 && (
        <div className="mt-4 flex items-start gap-3 rounded-lg border border-blue-200 dark:border-blue-900 bg-blue-50/40 dark:bg-blue-950/20 px-4 py-3">
          <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className="text-blue-600 dark:text-blue-400 shrink-0 mt-0.5"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
          <div>
            <p className="text-sm font-medium text-blue-800 dark:text-blue-300">Expert review invited</p>
            <p className="text-xs text-blue-700/80 dark:text-blue-400/80 mt-0.5">
              This paper has not yet been reviewed by a human expert. If you have domain expertise, your feedback helps calibrate the system.{" "}
              <a
                href={`https://github.com/ryanwongyy/autonomous-research-infrastructure/issues/new?title=Expert+Review:+${encodeURIComponent(id)}&labels=expert-review&body=${encodeURIComponent(`Paper: ${paper.title}\nID: ${id}\n\nYour review:\n`)}`}
                target="_blank"
                rel="noopener noreferrer"
                className="underline hover:text-blue-900 dark:hover:text-blue-200 font-medium"
              >
                Submit a review
              </a>
            </p>
          </div>
        </div>
      )}

      {/* Significance Memo */}
      {significanceMemo && (
        <div className="mt-6">
          <SignificanceMemoCard memo={significanceMemo} />
        </div>
      )}

      {/* Ratings — collapsed by default since QualitySummary shows the key numbers */}
      {paper.mu !== null && (
        <>
          <Separator className="my-6" />
          <details>
            <summary className="text-xl font-semibold mb-4 cursor-pointer hover:text-primary transition-colors list-none flex items-center gap-2">
              <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className="shrink-0"><polyline points="6 9 12 15 18 9"/></svg>
              TrueSkill Ratings
              <span className="text-sm font-normal text-muted-foreground ml-2">
                Conservative: {paper.conservative_rating?.toFixed(1)} &middot; Elo: {paper.elo?.toFixed(0)}
              </span>
            </summary>
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
          </details>
        </>
      )}

      {/* Reviews */}
      <Separator className="my-6" />
      <h2 className="text-xl font-semibold mb-4">Reviews</h2>
      {reviews.length === 0 && (
        <p className="text-sm text-muted-foreground py-4">
          This paper has not been reviewed yet. Reviews are generated automatically as the paper progresses through the pipeline.
        </p>
      )}
      {reviews.length > 0 && (
        <>
          <ReviewPipelineSummary reviews={reviews} />

          <div className="space-y-4">
            {reviews.map((review) => (
              <Card key={review.id}>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-base">
                      {reviewStageLabels[review.stage] ?? review.stage.replace(/_/g, " ")} Review
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
                  {review.content.length > 500 ? (
                    <details>
                      <summary className="text-sm text-muted-foreground cursor-pointer">
                        <span className="whitespace-pre-wrap">{review.content.slice(0, 500)}...</span>
                        <span className="text-primary hover:underline ml-1">Show full review</span>
                      </summary>
                      <p className="text-sm text-muted-foreground whitespace-pre-wrap mt-2">
                        {review.content}
                      </p>
                    </details>
                  ) : (
                    <p className="text-sm text-muted-foreground whitespace-pre-wrap">
                      {review.content}
                    </p>
                  )}
                </CardContent>
              </Card>
            ))}
          </div>
        </>
      )}

      {/* Expert Reviews (human) */}
      <ExpertReviewsSection reviews={expertReviews} />

      {/* Collegial Review — Convergence Loop */}
      {collegialSession && (
        <>
          <Separator className="my-6" />
          <h2 className="text-xl font-semibold mb-4">Collegial Review</h2>

          {/* Summary verdict — quick-read for researchers */}
          <div className={`rounded-lg px-4 py-3 mb-4 text-sm ${
            collegialSession.status === "converged"
              ? "bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-200 dark:border-emerald-800 text-emerald-800 dark:text-emerald-300"
              : collegialSession.status === "plateaued"
              ? "bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800 text-amber-800 dark:text-amber-300"
              : "bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-800 text-blue-800 dark:text-blue-300"
          }`}>
            <strong>Verdict:</strong>{" "}
            {collegialSession.status === "converged"
              ? `Paper converged on "ready for submission" after ${collegialSession.current_round} rounds.`
              : collegialSession.status === "plateaued"
              ? `Review plateaued after ${collegialSession.current_round} rounds — minor revisions may still be needed.`
              : collegialSession.status === "max_rounds_reached"
              ? `Maximum ${collegialSession.max_rounds} review rounds reached without full convergence.`
              : `Review in progress (round ${collegialSession.current_round} of ${collegialSession.max_rounds}).`}
            {collegialSession.final_quality_score != null && (
              <> Final quality score: <strong className="font-mono">{collegialSession.final_quality_score.toFixed(1)}/10</strong>.</>
            )}
            {" "}{collegialSession.suggestions_accepted} of {collegialSession.suggestions_accepted + collegialSession.suggestions_rejected + collegialSession.suggestions_partially_incorporated} suggestions accepted.
          </div>

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
                    <Badge variant="outline" className="text-[11px]">
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
            <details className="mt-4">
              <summary className="text-base font-semibold mb-3 cursor-pointer hover:text-primary transition-colors list-none flex items-center gap-2">
                <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className="shrink-0"><polyline points="6 9 12 15 18 9"/></svg>
                Quality Trajectory ({collegialSession.quality_trajectory.length} rounds)
              </summary>
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
                                ? "bg-emerald-600 text-[11px]"
                                : "text-[11px]"
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
                              <span className="text-[11px] text-muted-foreground w-32 truncate">
                                {dim.replace(/_/g, " ")}
                              </span>
                              <div className="flex-1 h-2 rounded-full bg-muted overflow-hidden">
                                <div
                                  className={`h-full rounded-full transition-all ${
                                    (score as number) >= 7
                                      ? "bg-emerald-500 dark:bg-emerald-400"
                                      : (score as number) >= 5
                                      ? "bg-amber-500 dark:bg-amber-400"
                                      : "bg-red-500 dark:bg-red-400"
                                  }`}
                                  style={{ width: `${((score as number) / 10) * 100}%` }}
                                />
                              </div>
                              <span className="text-[11px] font-mono w-6 text-right">
                                {score as number}
                              </span>
                            </div>
                          ))}
                        </div>
                      )}
                      {/* Remaining gaps */}
                      {qa.remaining_gaps && qa.remaining_gaps.length > 0 && (
                        <div className="mt-2">
                          <span className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wide">
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
            </details>
          )}

          {/* Dialogue thread — collapsible for readability */}
          {collegialSession.exchanges.length > 0 && (
            <details className="mt-4">
              <summary className="text-base font-semibold mb-3 cursor-pointer hover:text-primary transition-colors list-none flex items-center gap-2">
                <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className="shrink-0"><polyline points="6 9 12 15 18 9"/></svg>
                Dialogue ({collegialSession.exchanges.filter((e: CollegialExchangeItem) => e.exchange_type !== "quality_assessment").length} exchanges)
              </summary>
              <div className="space-y-3">
                {collegialSession.exchanges
                  .filter((e: CollegialExchangeItem) => e.exchange_type !== "quality_assessment")
                  .map((exchange: CollegialExchangeItem) => {
                  const isColleague = exchange.speaker_role === "colleague";
                  const isDrafter = exchange.speaker_role === "drafter";
                  const colleagueColors = [
                    "border-l-blue-500 dark:border-l-blue-400",
                    "border-l-violet-500 dark:border-l-violet-400",
                    "border-l-teal-500 dark:border-l-teal-400",
                    "border-l-rose-500 dark:border-l-rose-400",
                    "border-l-orange-500 dark:border-l-orange-400",
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
                            ? (() => {
                                const profile = colleagueProfiles.find((p) => p.id === exchange.colleague_id);
                                return profile ? profile.name : `Colleague #${exchange.colleague_id ?? "?"}`;
                              })()
                            : isDrafter
                            ? "Drafter"
                            : "Quality Assessor"}
                        </span>
                        {isColleague && (() => {
                          const profile = colleagueProfiles.find((p) => p.id === exchange.colleague_id);
                          return profile ? (
                            <Badge variant="secondary" className="text-[11px] px-1.5 py-0">{profile.expertise_area}</Badge>
                          ) : null;
                        })()}
                        <Badge variant="outline" className="text-[11px] px-1.5 py-0">
                          {exchange.exchange_type.replace(/_/g, " ")}
                        </Badge>
                        {exchange.target_section && (
                          <Badge variant="secondary" className="text-[11px] px-1.5 py-0">
                            {exchange.target_section}
                          </Badge>
                        )}
                        <span className="ml-auto text-[11px] text-muted-foreground tabular-nums">
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
            </details>
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
                          {(() => {
                            const profile = colleagueProfiles.find((p) => p.id === ack.colleague_id);
                            return profile ? profile.name : `Colleague #${ack.colleague_id}`;
                          })()}
                        </span>
                        <Badge variant="outline" className="text-[11px] px-1.5 py-0">
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
          { key: "actionability", label: "Actionability", color: "bg-blue-500 dark:bg-blue-400" },
          { key: "specificity", label: "Specificity", color: "bg-purple-500 dark:bg-purple-400" },
          { key: "evidence_strength", label: "Evidence Strength", color: "bg-emerald-500 dark:bg-emerald-400" },
          { key: "stakeholder_relevance", label: "Stakeholder Relevance", color: "bg-amber-500 dark:bg-amber-400" },
          { key: "implementation_feasibility", label: "Implementation Feasibility", color: "bg-rose-500 dark:bg-rose-400" },
        ] as const;
        const avgScore = dimensions.reduce((sum, dim) => sum + (scores[dim.key] ?? 0), 0) / dimensions.length;
        return (
          <>
            <Separator className="my-6" />
            <details>
              <summary className="text-xl font-semibold mb-4 cursor-pointer hover:text-primary transition-colors list-none flex items-center gap-2">
                <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className="shrink-0"><polyline points="6 9 12 15 18 9"/></svg>
                Policy Usefulness
                <span className="text-sm font-normal text-muted-foreground ml-2">
                  Avg: {avgScore.toFixed(1)}/5
                </span>
              </summary>
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
                        <span className="w-28 sm:w-48 text-xs sm:text-sm font-medium shrink-0 truncate">
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
                <div className="mt-3 flex gap-4 text-[11px] text-muted-foreground border-t pt-2">
                  <span><span className="inline-block w-2 h-2 rounded-full bg-emerald-500 mr-1" />4-5 Strong</span>
                  <span><span className="inline-block w-2 h-2 rounded-full bg-amber-500 mr-1" />3 Moderate</span>
                  <span><span className="inline-block w-2 h-2 rounded-full bg-red-500 mr-1" />1-2 Weak</span>
                </div>
              </CardContent>
            </Card>
            </details>
          </>
        );
      })()}

      {/* Submission History */}
      <SubmissionHistorySection outcomes={submissionOutcomes} />

      {/* Novelty & Autonomy (side-by-side on desktop) */}
      {(noveltyCheck || autonomyCard) && (
        <>
          <Separator className="my-6" />
          <h2 className="text-xl font-semibold mb-4">Assessment &amp; Provenance</h2>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            {noveltyCheck && <NoveltyCheckCard check={noveltyCheck} />}
            {autonomyCard && <AutonomyCardSection card={autonomyCard} />}
          </div>
        </>
      )}

      {/* Corrections & Errata */}
      <CorrectionsSection corrections={corrections} />
    </div>
  );
}
