from pathlib import Path

from pydantic_settings import BaseSettings


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
    lock_enforcement: str = "hard"  # "hard" = halt on violation, "soft" = log and continue

    # Source freshness
    source_stale_days: int = 90  # source considered stale after this many days

    # Manifest drift threshold (0.0-1.0): minimum coherence between design and downstream artifacts
    drift_threshold: float = 0.8

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
