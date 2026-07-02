from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

from app.database_migrations import ensure_runtime_schema


def test_runtime_migration_allows_deferred_pipeline_jobs(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'twitter.db'}")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE twitter_sources (id INTEGER PRIMARY KEY)"))
        connection.execute(
            text(
                """
                CREATE TABLE twitter_pipeline_jobs (
                    id INTEGER PRIMARY KEY,
                    job_type VARCHAR(20) NOT NULL DEFAULT 'scraper_job',
                    source_id INTEGER REFERENCES twitter_sources(id) ON DELETE SET NULL,
                    session_username TEXT,
                    status VARCHAR(10) NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending', 'running', 'done', 'failed')),
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
                "CREATE TABLE twitter_pipeline_logs ("
                "id INTEGER PRIMARY KEY, "
                "job_id INTEGER REFERENCES twitter_pipeline_jobs(id))"
            )
        )
        connection.execute(text("INSERT INTO twitter_pipeline_jobs (id, status) VALUES (1, 'done')"))

    ensure_runtime_schema(engine)

    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO twitter_pipeline_jobs (id, status) VALUES (2, 'deferred')")
        )
        statuses = connection.execute(
            text("SELECT status FROM twitter_pipeline_jobs ORDER BY id")
        ).scalars().all()
    assert statuses == ["done", "deferred"]


def test_runtime_migration_adds_twitter_source_unique_indexes(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'twitter.db'}")
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE twitter_sources (
                    id INTEGER PRIMARY KEY,
                    source_type VARCHAR(10) NOT NULL,
                    twitter_id VARCHAR(50),
                    twitter_url VARCHAR(255) NOT NULL,
                    source_name VARCHAR(255)
                )
                """
            )
        )

    ensure_runtime_schema(engine)

    with engine.begin() as connection:
        indexes = connection.execute(text("PRAGMA index_list('twitter_sources')")).mappings().all()
        index_names = {index["name"] for index in indexes}
        connection.execute(
            text(
                """
                INSERT INTO twitter_sources
                    (source_type, twitter_id, twitter_url, source_name)
                VALUES
                    ('hashtag', NULL, 'https://x.com/search?q=%23worldcup', '#WorldCup')
                """
            )
        )
        with pytest.raises(IntegrityError):
            connection.execute(
                text(
                    """
                    INSERT INTO twitter_sources
                        (source_type, twitter_id, twitter_url, source_name)
                    VALUES
                        ('hashtag', NULL, 'https://x.com/search?q=%23worldcup', '#worldcup')
                    """
                )
            )

    assert "uq_tw_source_twitter_url" in index_names
