from __future__ import annotations

import logging

from sqlalchemy import Engine, inspect, text


logger = logging.getLogger(__name__)

SQLITE_COLUMNS: dict[str, dict[str, str]] = {
    "tweets": {
        "weighted_engagement": "INTEGER",
        "engagement_rate": "FLOAT",
    },
    "twitter_sources": {
        "daily_views": "INTEGER",
        "daily_engagement": "INTEGER",
        "engagement_rate": "FLOAT",
        "source_score": "INTEGER",
    },
}


def ensure_runtime_schema(engine: Engine) -> None:
    if engine.dialect.name != "sqlite":
        return

    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    with engine.begin() as connection:
        if "twitter_analytics_cache" not in existing_tables:
            connection.execute(
                text(
                    """
                    CREATE TABLE twitter_analytics_cache (
                        id INTEGER NOT NULL,
                        source_id INTEGER NOT NULL,
                        date DATETIME NOT NULL,
                        total_tweets INTEGER DEFAULT 0,
                        total_likes INTEGER DEFAULT 0,
                        total_replies INTEGER DEFAULT 0,
                        total_retweets INTEGER DEFAULT 0,
                        total_quotes INTEGER DEFAULT 0,
                        avg_likes_per_tweet FLOAT,
                        top_tweet_id VARCHAR(50),
                        growth_rate FLOAT,
                        cached_at DATETIME,
                        PRIMARY KEY (id),
                        UNIQUE (source_id, date),
                        FOREIGN KEY(source_id) REFERENCES twitter_sources (id)
                    )
                    """
                )
            )
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_tw_analytics_source_date "
                "ON twitter_analytics_cache (source_id, date)"
            )
        )
        if "twitter_analytics_cache" in existing_tables:
            analytics_columns = {
                column["name"]
                for column in inspector.get_columns("twitter_analytics_cache")
            }
            if "total_bookmarks" in analytics_columns:
                connection.execute(
                    text("ALTER TABLE twitter_analytics_cache DROP COLUMN total_bookmarks")
                )

        for table_name, columns in SQLITE_COLUMNS.items():
            if table_name not in existing_tables:
                continue
            existing_columns = {
                column["name"] for column in inspector.get_columns(table_name)
            }
            if table_name == "twitter_sources" and "account_username" in existing_columns:
                logger.warning(
                    "SQLite table twitter_sources still has legacy account_username column. "
                    "The app ignores this column because accounts are managed in accounts.db; "
                    "rebuild or migrate twitter.db from data/schema_table_twitter.sql when convenient."
                )
            for column_name, column_type in columns.items():
                if column_name not in existing_columns:
                    connection.execute(
                        text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")
                    )
