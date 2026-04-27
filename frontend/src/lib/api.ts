import type {
  PaperFamily,
  PaperFamilyDetail,
  SourceCard,
  FunnelSnapshot,
  ConversionRate,
  Bottleneck,
  Projection,
  ReleasePipelineStatus,
  WorkQueueItem,
  Paper,
  PaperClaim,
  ProvenanceReport,
  LeaderboardResponse,
  StatsResponse,
  RatingDistributionResponse,
  TrueSkillProgressionPoint,
  CategoryInfo,
  MatchResponse,
  ReliabilityReport,
  ReliabilityOverview,
  SignificanceMemo,
  SubmissionOutcome,
  CorrectionRecord,
  ExpertReview,
  AutonomyCard,
  FailureDashboard,
  FailureRecord,
  NoveltyCheck,
  CohortTag,
  CohortComparison,
  RSIDashboard,
  RSIExperiment,
  PromptVersion,
  MetaPipelineRun,
  CollegialSession,
  ColleagueProfile,
  AcknowledgmentItem,
} from "./types";

// ── Base fetch helper ───────────────────────────────────────────────

export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

/** Server-side fetch with no-cache, for use in Server Components */
export async function serverFetch<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    signal: AbortSignal.timeout(15_000),
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });

  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
  }

  return res.json();
}

// ── Paper Families ──────────────────────────────────────────────────

export async function getFamilies(): Promise<{
  families: PaperFamily[];
  total: number;
}> {
  return apiFetch("/families");
}

export async function getFamily(familyId: string): Promise<PaperFamilyDetail> {
  return apiFetch(`/families/${familyId}`);
}

// ── Source Cards ────────────────────────────────────────────────────

export async function getSources(
  tier?: string
): Promise<{ sources: SourceCard[]; total: number }> {
  const params = tier ? `?tier=${tier}` : "";
  return apiFetch(`/sources${params}`);
}

export async function getSource(sourceId: string): Promise<SourceCard> {
  return apiFetch(`/sources/${sourceId}`);
}

// ── Leaderboard (family_id REQUIRED) ────────────────────────────────

export async function getLeaderboard(params: {
  family_id: string;
  page?: number;
  per_page?: number;
  sort_by?: string;
  sort_dir?: string;
}): Promise<LeaderboardResponse> {
  const searchParams = new URLSearchParams();
  searchParams.set("family_id", params.family_id);
  if (params.page) searchParams.set("page", String(params.page));
  if (params.per_page) searchParams.set("per_page", String(params.per_page));
  if (params.sort_by) searchParams.set("sort_by", params.sort_by);
  if (params.sort_dir) searchParams.set("sort_dir", params.sort_dir);
  return apiFetch(`/leaderboard?${searchParams.toString()}`);
}

// ── Throughput / Funnel ─────────────────────────────────────────────

export async function getFunnel(
  familyId?: string
): Promise<FunnelSnapshot> {
  const params = familyId ? `?family_id=${familyId}` : "";
  return apiFetch(`/throughput/funnel${params}`);
}

export async function getConversionRates(
  familyId?: string
): Promise<{ conversions: ConversionRate[] }> {
  const params = familyId ? `?family_id=${familyId}` : "";
  return apiFetch(`/throughput/conversion-rates${params}`);
}

export async function getBottlenecks(
  familyId?: string
): Promise<{ bottlenecks: Bottleneck[] }> {
  const params = familyId ? `?family_id=${familyId}` : "";
  return apiFetch(`/throughput/bottlenecks${params}`);
}

export async function getProjections(): Promise<Projection> {
  return apiFetch("/throughput/projections");
}

export async function getWorkQueue(
  familyId?: string
): Promise<{ items: WorkQueueItem[] }> {
  const params = familyId ? `?family_id=${familyId}` : "";
  return apiFetch(`/throughput/work-queue${params}`);
}

// ── Release Pipeline ────────────────────────────────────────────────

export async function getReleaseStatus(
  familyId?: string
): Promise<ReleasePipelineStatus> {
  const params = familyId ? `?family_id=${familyId}` : "";
  return apiFetch(`/release/status${params}`);
}

// ── Papers ──────────────────────────────────────────────────────────

export async function getPublicPapers(limit = 100): Promise<Paper[]> {
  return apiFetch(`/papers/public?limit=${limit}`);
}

export async function getPaper(paperId: string): Promise<Paper> {
  return apiFetch(`/papers/${paperId}`);
}

export async function getPaperClaims(
  paperId: string
): Promise<{ claims: PaperClaim[] }> {
  return apiFetch(`/papers/${paperId}/claims`);
}

export async function getPaperProvenance(
  paperId: string
): Promise<ProvenanceReport> {
  return apiFetch(`/papers/${paperId}/provenance`);
}

// ── Retained legacy endpoints ───────────────────────────────────────

export async function getStats(): Promise<StatsResponse> {
  return apiFetch("/stats");
}

export async function getRatingDistribution(): Promise<RatingDistributionResponse> {
  return apiFetch("/stats/rating-distribution");
}

export async function getTrueSkillProgression(): Promise<
  TrueSkillProgressionPoint[]
> {
  return apiFetch("/stats/trueskill-progression");
}

export async function getCategories(): Promise<CategoryInfo[]> {
  return apiFetch("/categories");
}

export async function getCategory(
  slug: string
): Promise<CategoryInfo & { papers: Paper[] }> {
  return apiFetch(`/categories/${slug}`);
}

export async function getMatches(
  limit = 20
): Promise<{ matches: MatchResponse[] }> {
  return apiFetch(`/matches?limit=${limit}`);
}

export async function triggerTournament(): Promise<{ run_id: number }> {
  return apiFetch("/tournament/run", { method: "POST" });
}

// ── Reliability ────────────────────────────────────────────────────

export async function getPaperReliability(paperId: string): Promise<ReliabilityReport> {
  return apiFetch(`/reliability/paper/${paperId}`);
}

export async function getFamilyReliability(familyId: string): Promise<ReliabilityReport> {
  return apiFetch(`/reliability/family/${familyId}`);
}

export async function getReliabilityOverview(): Promise<ReliabilityOverview> {
  return apiFetch("/reliability/overview");
}

// ── Significance Memo ──────────────────────────────────────────────

export async function getSignificanceMemo(paperId: string): Promise<SignificanceMemo> {
  return apiFetch(`/papers/${paperId}/significance-memo`);
}

export async function createSignificanceMemo(
  paperId: string,
  body: { author: string; memo_text: string; editorial_verdict: string }
): Promise<SignificanceMemo> {
  return apiFetch(`/papers/${paperId}/significance-memo`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

// ── Submission Outcomes ────────────────────────────────────────────

export async function getPaperOutcomes(paperId: string): Promise<SubmissionOutcome[]> {
  return apiFetch(`/papers/${paperId}/outcomes`);
}

export async function getOutcomesDashboard(): Promise<{
  overall: { total: number; accepted: number; rejected: number; desk_reject: number; r_and_r: number; pending: number; acceptance_rate: number };
  per_family: Array<{ family_id: string; short_name: string; total: number; accepted: number; rejected: number; acceptance_rate: number }>;
}> {
  return apiFetch("/outcomes/dashboard");
}

// ── Corrections ────────────────────────────────────────────────────

export async function getPaperCorrections(paperId: string): Promise<CorrectionRecord[]> {
  return apiFetch(`/papers/${paperId}/corrections`);
}

export async function getCorrectionsDashboard(): Promise<{
  families: Array<{
    family_id: string;
    short_name: string;
    total_public_papers: number;
    total_corrections: number;
    correction_rate: number;
  }>;
}> {
  return apiFetch("/corrections/dashboard");
}

// ── Expert Reviews ─────────────────────────────────────────────────

export async function getPaperExpertReviews(paperId: string): Promise<ExpertReview[]> {
  return apiFetch(`/papers/${paperId}/expert-reviews`);
}

// ── Autonomy ───────────────────────────────────────────────────────

export async function getPaperAutonomyCard(paperId: string): Promise<AutonomyCard> {
  return apiFetch(`/papers/${paperId}/autonomy-card`);
}

export async function getFamilyAutonomyStats(familyId: string): Promise<{ family_id: string; avg_autonomy_score: number | null; total_papers: number }> {
  return apiFetch(`/families/${familyId}/autonomy-stats`);
}

// ── Failures ───────────────────────────────────────────────────────

export async function getFailuresDashboard(familyId?: string, days?: number): Promise<FailureDashboard> {
  const params = new URLSearchParams();
  if (familyId) params.set("family_id", familyId);
  if (days) params.set("days", String(days));
  return apiFetch(`/failures/dashboard?${params}`);
}

export async function getPaperFailures(paperId: string): Promise<FailureRecord[]> {
  return apiFetch(`/papers/${paperId}/failures`);
}

// ── Novelty ────────────────────────────────────────────────────────

export async function triggerNoveltyCheck(paperId: string): Promise<NoveltyCheck> {
  return apiFetch(`/papers/${paperId}/novelty-check`, { method: "POST" });
}

export async function getNoveltyCheck(paperId: string): Promise<NoveltyCheck> {
  return apiFetch(`/papers/${paperId}/novelty-check`);
}

// ── Cohorts ────────────────────────────────────────────────────────

export async function getCohorts(): Promise<CohortTag[]> {
  return apiFetch("/cohorts");
}

export async function getCohort(cohortId: string): Promise<CohortComparison> {
  return apiFetch(`/cohorts/${cohortId}`);
}

export async function getPaperCohort(paperId: string): Promise<CohortTag> {
  return apiFetch(`/papers/${paperId}/cohort`);
}

// ── RSI (Recursive Self-Improvement) ──────────────────────────────

export async function getRSIDashboard(): Promise<RSIDashboard> {
  return apiFetch("/rsi/dashboard");
}

export async function getRSIExperiments(params?: { tier?: string; family_id?: string; status?: string }): Promise<RSIExperiment[]> {
  const searchParams = new URLSearchParams();
  if (params?.tier) searchParams.set("tier", params.tier);
  if (params?.family_id) searchParams.set("family_id", params.family_id);
  if (params?.status) searchParams.set("status", params.status);
  const qs = searchParams.toString();
  return apiFetch(`/rsi/experiments${qs ? `?${qs}` : ""}`);
}

export async function getRSIExperiment(id: number): Promise<RSIExperiment> {
  return apiFetch(`/rsi/experiments/${id}`);
}

export async function activateRSIExperiment(id: number): Promise<RSIExperiment> {
  return apiFetch(`/rsi/experiments/${id}/activate`, { method: "POST" });
}

export async function rollbackRSIExperiment(id: number, reason?: string): Promise<RSIExperiment> {
  return apiFetch(`/rsi/experiments/${id}/rollback`, {
    method: "POST",
    body: JSON.stringify({ reason: reason || "" }),
  });
}

export async function getPromptHistory(targetType: string, targetKey: string): Promise<PromptVersion[]> {
  return apiFetch(`/rsi/prompts/${targetType}/${targetKey}/history`);
}

export async function getImprovementSummary() {
  return apiFetch("/rsi/tier4b/summary");
}

export async function getCohortDeltas() {
  return apiFetch("/rsi/tier4b/cohort-deltas");
}

export async function getMetaPipelineRuns(): Promise<MetaPipelineRun[]> {
  return apiFetch("/rsi/tier4c/runs");
}

export async function triggerMetaCycle(): Promise<MetaPipelineRun> {
  return apiFetch("/rsi/tier4c/start-cycle", { method: "POST" });
}

export async function getRolePromptStatus() {
  return apiFetch("/rsi/tier1a/status");
}

export async function getAllLayerAccuracy() {
  return apiFetch("/rsi/tier1b/accuracy");
}

export async function getAllFamilyHealth() {
  return apiFetch("/rsi/tier2a/health");
}

export async function getTaxonomyStatus() {
  return apiFetch("/rsi/tier4a/status");
}

// ── Collegial Review ──────────────────────────────────────────────

export async function getColleagueProfiles(): Promise<{ profiles: ColleagueProfile[] }> {
  return apiFetch("/collegial/profiles");
}

export async function getCollegialSession(paperId: string): Promise<{ session: CollegialSession | null }> {
  return apiFetch(`/papers/${paperId}/collegial-session`);
}

export async function getPaperAcknowledgments(paperId: string): Promise<{ acknowledgments: AcknowledgmentItem[] }> {
  return apiFetch(`/papers/${paperId}/acknowledgments`);
}
