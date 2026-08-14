"""Central configuration. Never hardcode credentials — everything here is
sourced from environment variables (see .env.example at repo root)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="", extra="ignore")

    app_env: str = "development"  # development | test | production
    provider_mode: str = "fake"  # "fake" forces every provider role to the fake adapter

    database_url: str = "sqlite+pysqlite:///./dev.db"
    redis_url: str = "redis://localhost:6379/0"

    storage_backend: str = "local"  # local | s3 | gdrive
    storage_local_root: str = "./storage"
    s3_bucket: str | None = None
    s3_region: str | None = None
    s3_endpoint_url: str | None = None
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None

    # Defaults sized against config/production_policy.yaml's
    # default_target_final_designs=30 at per_design_budget_usd below, with
    # headroom for the exploratory-generation funnel (see
    # app/pipeline/production_controller.py's requested_budget_cap).
    daily_budget_usd: float = 150.0
    monthly_budget_usd: float = 3500.0
    per_design_budget_usd: float = 3.0

    celery_task_always_eager: bool = False
    # Production default per docs/EVENTS.md; override to a small value
    # (e.g. in tests) so retry/backoff paths don't slow down a fast suite.
    celery_retry_backoff_max: float = 600.0
    celery_max_retries: int = 5

    production_policy_path: str = str(CONFIG_DIR / "production_policy.yaml")
    providers_config_path: str = str(CONFIG_DIR / "providers.yaml")

    log_level: str = "INFO"
    frontend_origin: str = "http://localhost:3000"

    # Real web-search-based Market Intelligence adapter (see
    # app/providers/web_search_market_intelligence.py). Unset by default --
    # the daily cycle falls back to DatabaseMarketIntelligenceAdapter
    # (whatever has been ingested via the API) when this isn't configured,
    # never to a fabricated trend. What it searches FOR is computed by
    # app/pipeline/market_research_planner.py from
    # config/market_research_queries.yaml + config/seasonal_calendar.yaml,
    # not a fixed list here.
    serpapi_key: str | None = None
    # Shared-secret gate on POST /api/market-intelligence/signals -- that
    # endpoint lets an OUT-OF-PROCESS caller (an agent-driven web research
    # job, not just the trusted frontend) write data that later influences
    # real production decisions, so unlike the rest of this dashboard-only
    # API it should not be left open in any deployment reachable by anyone
    # but that one job. Unset (None) leaves it open, which is only
    # acceptable for local/dev use.
    market_signal_ingestion_token: str | None = None

    @property
    def is_test(self) -> bool:
        return self.app_env == "test"


@lru_cache
def get_settings() -> Settings:
    return Settings()
