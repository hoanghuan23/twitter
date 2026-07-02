from __future__ import annotations

import logging

from sqlalchemy import Engine, inspect, text
from sqlalchemy.exc import SQLAlchemyError


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
    if "twitter_pipeline_jobs" in existing_tables:
        _ensure_deferred_pipeline_job_status(engine)
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
        if "twitter_sources" in existing_tables:
            _ensure_twitter_source_unique_indexes(connection)


def _ensure_twitter_source_unique_indexes(connection) -> None:
    index_statements = [
        (
            "uq_tw_source_twitter_url",
            """
            CREATE UNIQUE INDEX IF NOT EXISTS uq_tw_source_twitter_url
            ON twitter_sources (twitter_url)
            """,
        ),
    ]
    for index_name, statement in index_statements:
        try:
            connection.execute(text(statement))
        except SQLAlchemyError:
            logger.warning(
                "Could not create unique index %s on twitter_sources. "
                "Existing duplicate rows may need cleanup first.",
                index_name,
                exc_info=True,
            )


def _ensure_deferred_pipeline_job_status(engine: Engine) -> None:
    """Rebuild the SQLite table only when its old CHECK excludes ``deferred``."""
    with engine.connect() as connection:
        create_sql = connection.execute(
            text(
                "SELECT sql FROM sqlite_master "
                "WHERE type = 'table' AND name = 'twitter_pipeline_jobs'"
            )
        ).scalar_one_or_none()
        if not create_sql or "deferred" in create_sql.lower():
            return

        connection.commit()
        connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
        connection.exec_driver_sql("PRAGMA legacy_alter_table=ON")
        connection.commit()
        try:
            with connection.begin():
                connection.execute(text("ALTER TABLE twitter_pipeline_jobs RENAME TO _old_pipeline_jobs"))
                connection.execute(
                    text(
                        """
                        CREATE TABLE twitter_pipeline_jobs (
                            id INTEGER PRIMARY KEY,
                            job_type VARCHAR(20) NOT NULL DEFAULT 'scraper_job'
                                CHECK (job_type IN ('scrape_timeline', 'scraper_job', 'update_metric', 'analytics')),
                            source_id INTEGER REFERENCES twitter_sources(id) ON DELETE SET NULL,
                            session_username TEXT,
                            status VARCHAR(10) NOT NULL DEFAULT 'pending'
                                CHECK (status IN ('pending', 'running', 'done', 'failed', 'deferred')),
                            tweets_found INTEGER NOT NULL DEFAULT 0,
                            tweets_new INTEGER NOT NULL DEFAULT 0,
                            items_total INTEGER NOT NULL DEFAULT 0,
                            items_updated INTEGER NOT NULL DEFAULT 0,
                            items_failed INTEGER NOT NULL DEFAULT 0,
                            rate_limit_hits INTEGER NOT NULL DEFAULT 0,
                            error_message TEXT,
                            started_at DATETIME,
                            finished_at DATETIME
                        )
                        """
                    )
                )
                connection.execute(
                    text(
                        """
                        INSERT INTO twitter_pipeline_jobs
                        SELECT id, job_type, source_id, session_username, status,
                               tweets_found, tweets_new, items_total, items_updated,
                               items_failed, rate_limit_hits, error_message, started_at, finished_at
                        FROM _old_pipeline_jobs
                        """
                    )
                )
                connection.execute(text("DROP TABLE _old_pipeline_jobs"))
                connection.execute(
                    text("CREATE INDEX IF NOT EXISTS idx_tw_pipeline_jobs_source_time "
                         "ON twitter_pipeline_jobs (source_id, started_at DESC)")
                )
                connection.execute(
                    text("CREATE INDEX IF NOT EXISTS idx_tw_pipeline_jobs_type_status "
                         "ON twitter_pipeline_jobs (job_type, status, started_at DESC)")
                )
        finally:
            connection.exec_driver_sql("PRAGMA legacy_alter_table=OFF")
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
