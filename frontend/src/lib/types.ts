// ── Paper Family types ──────────────────────────────────────────────

export interface PaperFamily {
  id: string; // "F1"..."F11"
  name: string;
  short_name: string;
  description: string;
  lock_protocol_type: string;
  venue_ladder: { flagship: string[]; elite_field: string[] } | null;
  mandatory_checks: string[];
  fatal_failures: string[];
  elite_ceiling: string;
  max_portfolio_share: number;
  paper_count: number;
  active: boolean;
}

export interface PaperFamilyDetail extends PaperFamily {
  canonical_questions: string[];
  accepted_methods: string[];
  public_data_sources: string[];
  novelty_threshold: string;
  benchmark_config: Record<string, unknown> | null;
  review_rubric: {
    criteria: Array<{ name: string; weight: number; description: string }>;
    punished_mainly_for: string[];
  } | null;
  funnel_stages: Record<string, number>;
}

// ── Source Card types ───────────────────────────────────────────────

export interface SourceCard {
  id: string;
  name: string;
  url: string;
  tier: "A" | "B" | "C";
  source_type: string;
  access_method: string;
  requires_key: boolean;
  canonical_unit: string;
  claim_permissions: string[];
  claim_prohibitions: string[];
  known_traps: string[];
  fragility_score: number;
  active: boolean;
}

// ── Throughput & Funnel types ───────────────────────────────────────

export interface FunnelSnapshot {
  stages: Record<string, number>;
  killed: number;
  total_active: number;
  total_completed: number;
}

export interface ConversionRate {
  from: string;
  to: string;
  rate: number;
  count: number;
  converted: number;
}

export interface Bottleneck {
  stage: string;
  stuck_count: number;
  avg_days_in_stage: number;
  severity: "low" | "medium" | "high" | "critical";
}

export interface Projection {
  projected_annual: Record<string, number>;
  targets: Record<string, number>;
  on_track: boolean;
  gap_analysis: string;
}

// ── Release Pipeline types ──────────────────────────────────────────

export interface ReleasePipelineStatus {
  internal: {
    count: number;
    papers: Array<{ id: string; title: string; family_id: string }>;
  };
  candidate: {
    count: number;
    papers: Array<{ id: string; title: string; family_id: string }>;
  };
  submitted: {
    count: number;
    papers: Array<{ id: string; title: string; family_id: string }>;
  };
  public: {
    count: number;
    papers: Array<{ id: string; title: string; family_id: string }>;
  };
}

// ── Work Queue types ────────────────────────────────────────────────

export interface WorkQueueItem {
  paper_id: string;
  title: string;
  family_id: string;
  funnel_stage: string;
  priority: number;
  reason: string;
}

// ── Paper & Rating types ────────────────────────────────────────────

export interface Rating {
  mu: number;
  sigma: number;
  conservative_rating: number;
  elo: number;
  matches_played: number;
  wins: number;
  losses: number;
  draws: number;
}

export interface PolicyScores {
  actionability: number;
  specificity: number;
  evidence_strength: number;
  stakeholder_relevance: number;
  implementation_feasibility: number;
}

export interface Paper {
  id: string;
  title: string;
  abstract: string | null;
  source: string;
  category: string | null;
  family_id: string | null;
  country: string | null;
  method: string | null;
  status: string;
  review_status: string;
  release_status: string;
  funnel_stage: string;
  lock_version: number;
  novelty_score: number | null;
  data_adequacy_score: number | null;
  venue_fit_score: number | null;
  overall_screening_score: number | null;
  created_at: string;
  updated_at: string;
  rating: Rating | null;
}

export interface PaperClaim {
  id: string;
  claim_text: string;
  source_id: string;
  confidence: number;
  verified: boolean;
}

export interface ProvenanceReport {
  paper_id: string;
  events: Array<{
    timestamp: string;
    actor: string;
    action: string;
    detail: string;
  }>;
}

// ── Leaderboard types (updated – family_id now required) ────────────

export interface LeaderboardEntry {
  rank: number | null;
  rank_change_48h: number;
  paper_id: string;
  title: string;
  source: string;
  category: string | null;
  family_id: string | null;
  mu: number;
  sigma: number;
  conservative_rating: number;
  elo: number;
  matches_played: number;
  wins: number;
  losses: number;
  draws: number;
  review_status: string;
}

export interface LeaderboardResponse {
  entries: LeaderboardEntry[];
  total: number;
  offset: number;
  limit: number;
}

// ── Stats types (retained for backward compatibility) ───────────────

export interface StatsResponse {
  total_papers: number;
  total_ai_papers: number;
  total_benchmark_papers: number;
  total_matches: number;
  total_tournament_runs: number;
  ai_win_rate: number;
  avg_elo_ai: number | null;
  avg_elo_benchmark: number | null;
}

export interface RatingDistributionBucket {
  bucket_start: number;
  bucket_end: number;
  count_ai: number;
  count_benchmark: number;
}

export interface RatingDistributionResponse {
  elo_distribution: RatingDistributionBucket[];
  conservative_distribution: RatingDistributionBucket[];
}

export interface TrueSkillProgressionPoint {
  date: string;
  paper_id: string;
  title: string;
  source: string;
  conservative_rating: number;
}

export interface MatchResponse {
  id: number;
  tournament_run_id: number;
  paper_a_id: string;
  paper_b_id: string;
  winner_id: string | null;
  judge_model: string;
  final_result: string;
  batch_number: number;
  created_at: string;
}

export interface CategoryInfo {
  slug: string;
  name: string;
  domain_id: string;
  paper_count: number;
}

// ── Reliability types ──────────────────────────────────────────────

export interface ReliabilityMetricData {
  value: number;
  threshold: number;
  passes: boolean;
  details: string;
}

export interface ReliabilityReport {
  paper_id: string;
  metrics: Record<string, ReliabilityMetricData>;
}

export interface FamilyReliabilityMetric {
  avg_value: number;
  min_value: number;
  max_value: number;
  papers_passing: number;
  total_papers: number;
  threshold: number;
}

export interface ReliabilityOverview {
  families: Array<{
    family_id: string;
    short_name: string;
    metrics: Record<string, FamilyReliabilityMetric>;
  }>;
  thresholds: Record<string, number>;
}

// ── Significance Memo types ────────────────────────────────────────

export interface SignificanceMemo {
  id: number;
  author: string;
  memo_text: string;
  tournament_rank_at_time: number | null;
  tournament_confidence_json: string | null;
  editorial_verdict: string;
  created_at: string | null;
}

// ── Submission Outcome types ───────────────────────────────────────

export interface SubmissionOutcome {
  id: number;
  venue_name: string;
  submitted_date: string | null;
  decision: string | null;
  decision_date: string | null;
  revision_rounds: number;
  reviewer_feedback_summary: string | null;
  created_at: string | null;
}

// ── Correction Record types ────────────────────────────────────────

export interface CorrectionRecord {
  id: number;
  correction_type: string;
  description: string;
  affected_claims_json: string | null;
  corrected_at: string | null;
  published_at: string | null;
  created_at: string | null;
}

// ── Expert Review types ────────────────────────────────────────────

export interface ExpertReview {
  id: number;
  expert_name: string;
  affiliation: string | null;
  review_date: string | null;
  overall_score: number;
  methodology_score: number | null;
  contribution_score: number | null;
  notes: string | null;
  is_pre_submission: boolean;
  created_at: string | null;
}

// ── Autonomy Card types ────────────────────────────────────────────

export interface AutonomyCard {
  role_autonomy: Record<string, string>;
  human_intervention_points: Array<{ role: string; level: string; description: string }>;
  overall_autonomy_score: number;
  created_at: string | null;
  updated_at: string | null;
}

// ── Failure Record types ───────────────────────────────────────────

export interface FailureRecord {
  id: number;
  failure_type: string;
  severity: string;
  detection_stage: string;
  root_cause_category: string | null;
  resolution: string | null;
  corrective_action: string | null;
  created_at: string | null;
}

export interface FailureDashboard {
  distribution: {
    total: number;
    by_type: Record<string, number>;
    by_severity: Record<string, number>;
    by_stage: Record<string, number>;
  };
  trends: Array<{ date: string; total: number }>;
}

// ── Novelty Check types ────────────────────────────────────────────

export interface NoveltyCheck {
  id: number;
  verdict: string;
  highest_similarity_score: number;
  checked_against_count: number;
  similar_papers: Array<{ paper_id: string; similarity: number }>;
  model_used: string;
  created_at: string | null;
}

// ── Cohort types ───────────────────────────────────────────────────

export interface CohortTag {
  cohort_id: string;
  generation_model: string;
  review_models_json: string | null;
  tournament_judge_model: string | null;
  created_at: string | null;
}

export interface CohortComparison {
  cohort_id: string;
  paper_count: number;
  generation_model: string;
  avg_mu: number;
  avg_conservative_rating: number;
  rated_papers: number;
}

// ── RSI (Recursive Self-Improvement) types ────────────────────────

export interface RSIExperiment {
  id: number;
  tier: string;
  name: string;
  status: string;
  cohort_id: string | null;
  family_id: string | null;
  created_by: string;
  proposed_at: string | null;
  activated_at: string | null;
  rolled_back_at: string | null;
  config_snapshot: Record<string, unknown> | null;
  result_summary: Record<string, unknown> | null;
}

export interface PromptVersion {
  id: number;
  target_type: string;
  target_key: string;
  version: number;
  prompt_text: string;
  diff_from_previous: string | null;
  experiment_id: number | null;
  is_active: boolean;
  performance: Record<string, unknown> | null;
  created_at: string | null;
}

export interface RSIGateLog {
  id: number;
  experiment_id: number;
  gate_type: string;
  decision: string;
  decided_at: string | null;
  notes: string | null;
}

export interface RSIDashboard {
  by_tier: Record<string, number>;
  by_status: Record<string, number>;
  recent_gates: RSIGateLog[];
  total_experiments: number;
}

export interface TierHealthItem {
  tier: string;
  name: string;
  status: string;
  active_experiments: number;
  last_decision: string | null;
}

export interface MetaPipelineRun {
  id: number;
  status: string;
  observation: Record<string, unknown> | null;
  proposals: Record<string, unknown>[] | null;
  shadow_results: Record<string, unknown> | null;
  promotion_decision: string | null;
  production_delta: Record<string, unknown> | null;
  started_at: string | null;
  completed_at: string | null;
}

// ── Collegial Review types ────────────────────────────────────────

export interface ColleagueProfile {
  id: number;
  name: string;
  expertise_area: string;
  perspective_description: string;
  active: boolean;
}

export interface CollegialExchangeItem {
  id: number;
  speaker_role: "colleague" | "drafter" | "assessor";
  colleague_id: number | null;
  turn_number: number;
  round_number: number;
  exchange_type: string;
  target_section: string | null;
  content: string | null;
  created_at: string | null;
}

export interface AcknowledgmentItem {
  colleague_id: number;
  contribution_type: string;
  contribution_summary: string;
  acknowledgment_text: string;
  exchanges_count: number;
  accepted_suggestions: number;
}

export interface QualityDimensions {
  methodology_rigor: number;
  contribution_clarity: number;
  literature_engagement: number;
  argument_coherence: number;
  venue_fit: number;
}

export interface QualityAssessment {
  round: number;
  overall_score: number;
  verdict: "ready" | "minor_revision" | "major_revision";
  dimensions: QualityDimensions;
  remaining_gaps: Array<{
    dimension: string;
    gap: string;
    priority: "high" | "medium" | "low";
    section: string;
  }>;
  improvements_from_previous: string[];
  assessor_note: string;
}

export interface CollegialSession {
  session_id: number;
  status: string;
  current_round: number;
  max_rounds: number;
  target_venue: string | null;
  final_quality_score: number | null;
  quality_trajectory: QualityAssessment[];
  total_exchanges: number;
  suggestions_accepted: number;
  suggestions_rejected: number;
  suggestions_partially_incorporated: number;
  session_summary: string | null;
  started_at: string | null;
  completed_at: string | null;
  exchanges: CollegialExchangeItem[];
  acknowledgments: AcknowledgmentItem[];
}
