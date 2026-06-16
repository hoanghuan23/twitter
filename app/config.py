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
    twscrape_db_path: str = os.getenv("TWSCRAPE_DB_PATH", "./data/accounts.db")
    scheduler_enabled: bool = _bool_env("TWITTER_SCHEDULER_ENABLED", True)
    scheduler_interval_seconds: int = int(os.getenv("TWITTER_SCHEDULER_INTERVAL_SECONDS", "120"))
    crawl_due_limit: int = int(os.getenv("TWITTER_CRAWL_DUE_LIMIT", "10"))
    metric_due_limit: int = int(os.getenv("TWITTER_METRIC_DUE_LIMIT", "50"))
    default_scrape_interval_minutes: int = int(
        os.getenv("TWITTER_DEFAULT_SCRAPE_INTERVAL_MINUTES", "60")
    )
    default_crawl_limit: int = int(os.getenv("TWITTER_DEFAULT_CRAWL_LIMIT", "50")) # use for source_type = (hashtag/keyword)
    account_crawl_limit: int = int(os.getenv("TWITTER_ACCOUNT_CRAWL_LIMIT", "500")) # user for source_type = account


settings = Settings()
