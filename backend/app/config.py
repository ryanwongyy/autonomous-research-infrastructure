from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    app_name: str = "Autonomous research infrastructure for AI governance"
    debug: bool = False

    # Use SQLite for dev, PostgreSQL for production:
    #   postgresql+asyncpg://user:pass@host:5432/ape_replica
    database_url: str = "sqlite+aiosqlite:///./ape_replica.db"

    anthropic_api_key: str = ""
    openai_api_key: str = ""
    google_api_key: str = ""

    # Data source API keys (optional — sources that need them degrade gracefully)
    regulations_gov_api_key: str = ""
    courtlistener_api_key: str = ""
    openalex_email: str = ""  # Not a key; enables OpenAlex polite pool

    default_domain: str = "ai_governance"
    domain_configs_dir: str = str(Path(__file__).parent.parent / "domain_configs")

    tournament_matches_per_day: int = 50
    tournament_batches: int = 10
    tournament_matches_per_batch: int = 5
    tournament_schedule_hour: int = 9  # UTC
    tournament_schedule_minute: int = 0

    trueskill_mu: float = 25.0
    trueskill_sigma: float = 8.333
    trueskill_beta: float = 4.167
    trueskill_tau: float = 0.083
    trueskill_draw_probability: float = 0.1

    elo_default: float = 1500.0
    elo_k_factor: float = 32.0

    papers_dir: str = str(Path(__file__).parent.parent / "papers")

    # Artifact storage
    artifact_store_path: str = str(Path(__file__).parent.parent / "artifacts")

    # Lock enforcement
    lock_enforcement: str = (
        "hard"  # "hard" = halt on violation, "soft" = log and continue
    )

    # Source freshness
    source_stale_days: int = 90  # source considered stale after this many days

    # Manifest drift threshold (0.0-1.0): minimum coherence between design and downstream artifacts
    drift_threshold: float = 0.8

    # ── Scout screening thresholds ──────────────────────────────────────
    # Each idea is scored on a 0-5 scale across six dimensions; the Scout
    # role accepts an idea only if (composite >= min_composite AND
    # novelty >= min_novelty AND data_adequacy >= min_data_adequacy).
    #
    # The original code hardcoded 4.0 / 4 / 4 — strict enough that fresh
    # Claude-generated ideas never pass (Claude rates its own ideas
    # conservatively at 3-3.5 typical). Looser early-operation defaults
    # let the rest of the pipeline run. Tighten when papers start
    # consistently passing into review.
    scout_screen_min_composite: float = 3.0
    scout_screen_min_novelty: int = 3
    scout_screen_min_data_adequacy: int = 3

    # If False (the default), Scout's gate is composite-only — the
    # weighted composite already includes novelty (0.20) and
    # data_adequacy (0.20) so a per-dimension AND-gate is a redundant
    # second filter. Production run #25110421840 demonstrated that the
    # AND-gate was provably blocking ideas (composite 3.10 and 3.20)
    # that the composite floor accepted, because Claude self-rated one
    # of those two dimensions at 2 even when overall composite was OK.
    #
    # If True, re-impose the per-dimension floors. Useful for mature
    # operation when the system is consistently producing higher-scoring
    # ideas and the operator wants to ratchet the bar up.
    scout_screen_strict_per_dimension: bool = False

    # ── LLM model IDs ──────────────────────────────────────────────────
    # Centralised so a deploy can flip to a new model id (e.g. when
    # Anthropic releases a new dated suffix) without code changes. Each
    # of these is overridable via env var with the same name in caps.
    #
    # Defaults match the publicly documented latest ids as of 2026-04.
    # Anthropic's *-4-5 aliases auto-resolve to the latest dated
    # snapshot, so they don't need updating each model release.
    #
    # NOTE: prior versions of this codebase hardcoded `claude-opus-4-6`
    # and `claude-sonnet-4-6` — those names did not exist publicly and
    # caused every cron-triggered Scout call to fail with HTTP 400.
    claude_opus_model: str = "claude-opus-4-5"
    claude_sonnet_model: str = "claude-sonnet-4-5"
    claude_haiku_model: str = "claude-haiku-4-5"
    openai_main_model: str = "gpt-4o"
    openai_reasoning_model: str = "o1"
    openai_fast_model: str = "gpt-4o-mini"
    judge_non_claude_model: str = "gpt-4o"  # L3 explicitly non-Claude
    google_main_model: str = "gemini-1.5-pro"

    # Per-LLM-call timeout. Long generations (Analyst's 16K-token code,
    # Drafter's 32K-token manuscript) can legitimately take 3-5 minutes
    # at the model side. The previous 120s default was too tight and
    # production runs killed Analyst with TimeoutError (run #25138168976).
    # 600s (10 min) gives generous headroom for the longest stages.
    llm_timeout_seconds: int = 600

    # Authentication (leave blank to disable auth in dev)
    ape_api_key: str = ""  # Required for all mutation endpoints when set
    ape_admin_key: str = ""  # Required for expensive ops (RSI, tournament, import)

    # Sentry DSN for error tracking (leave blank to disable)
    sentry_dsn: str = ""

    cors_origins: str = "http://localhost:3000,http://localhost:3001"

    @property
    def cors_origins_list(self) -> list[str]:
        return [s.strip() for s in self.cors_origins.split(",") if s.strip()]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
