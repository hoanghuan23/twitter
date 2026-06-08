from __future__ import annotations

import os
from dataclasses import dataclass


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./data/twitter.db")
    twscrape_db_path: str = os.getenv("TWSCRAPE_DB_PATH", "./data/twitter.db")
    scheduler_enabled: bool = _bool_env("TWITTER_SCHEDULER_ENABLED", False)
    scheduler_interval_seconds: int = int(os.getenv("TWITTER_SCHEDULER_INTERVAL_SECONDS", "300"))
    crawl_due_limit: int = int(os.getenv("TWITTER_CRAWL_DUE_LIMIT", "10"))
    default_scrape_interval_minutes: int = int(
        os.getenv("TWITTER_DEFAULT_SCRAPE_INTERVAL_MINUTES", "60")
    )
    default_crawl_limit: int = int(os.getenv("TWITTER_DEFAULT_CRAWL_LIMIT", "50"))


settings = Settings()
