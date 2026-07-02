from __future__ import annotations

from datetime import datetime

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.models.twitter_source import TwitterSource
from app.schemas.source import SourceCreate
from app.utils.time import utc_now


class TwitterSourceRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list(self, active: bool | None, limit: int, offset: int) -> list[TwitterSource]:
        stmt: Select[tuple[TwitterSource]] = select(TwitterSource)
        if active is not None:
            stmt = stmt.where(TwitterSource.is_active == active)
        stmt = stmt.order_by(TwitterSource.id.desc()).limit(limit).offset(offset)
        return list(self.db.scalars(stmt))

    def get(self, source_id: int) -> TwitterSource | None:
        return self.db.get(TwitterSource, source_id)

    def create(
        self,
        payload: SourceCreate,
        enriched_fields: dict[str, object] | None = None,
    ) -> TwitterSource:
        data = payload.model_dump()
        if enriched_fields:
            data.update(enriched_fields)

        now = utc_now()
        existing = self._get_existing(data)
        if existing is not None:
            self._apply_data(existing, data)
            existing.is_active = True
            existing.next_scrape = existing.next_scrape or now
            self.db.flush()
            return existing

        if data["source_type"] == "account" and data.get("max_days_old") is None:
            data["max_days_old"] = 1

        source = TwitterSource(
            source_type=data["source_type"],
            topic_id=data.get("topic_id"),
            twitter_id=data.get("twitter_id"),
            twitter_url=data["twitter_url"],
            source_name=data.get("source_name"),
            description=data.get("description"),
            followers_count=data.get("followers_count"),
            following_count=data.get("following_count"),
            tweet_count=data.get("tweet_count"),
            protected=data.get("protected"),
            verified=data.get("verified"),
            include_replies=data["include_replies"],
            max_days_old=data.get("max_days_old"),
            is_active=True,
            created_at=now,
            next_scrape=now,
        )
        self.db.add(source)
        self.db.flush()
        return source

    def _get_existing(self, data: dict[str, object]) -> TwitterSource | None:
        twitter_url = data.get("twitter_url")
        if twitter_url:
            stmt = (
                select(TwitterSource)
                .where(TwitterSource.twitter_url == str(twitter_url))
                .limit(1)
            )
            existing = self.db.scalar(stmt)
            if existing is not None:
                return existing

        twitter_id = data.get("twitter_id")
        if twitter_id:
            stmt = (
                select(TwitterSource)
                .where(TwitterSource.twitter_id == str(twitter_id))
                .where(TwitterSource.source_type == data["source_type"])
                .limit(1)
            )
            return self.db.scalar(stmt)

        return None

    def _apply_data(self, source: TwitterSource, data: dict[str, object]) -> None:
        source.twitter_url = str(data["twitter_url"])
        source.topic_id = data.get("topic_id")  # type: ignore[assignment]
        source.source_name = data.get("source_name")  # type: ignore[assignment]
        source.description = data.get("description")  # type: ignore[assignment]
        source.followers_count = data.get("followers_count")  # type: ignore[assignment]
        source.following_count = data.get("following_count")  # type: ignore[assignment]
        source.tweet_count = data.get("tweet_count")  # type: ignore[assignment]
        source.protected = data.get("protected")  # type: ignore[assignment]
        source.verified = data.get("verified")  # type: ignore[assignment]
        source.include_replies = bool(data["include_replies"])
        source.max_days_old = data.get("max_days_old")  # type: ignore[assignment]

    def deactivate(self, source: TwitterSource) -> TwitterSource:
        source.is_active = False
        self.db.flush()
        return source

    def update_config(self, source: TwitterSource, data: dict[str, object]) -> TwitterSource:
        for field, value in data.items():
            setattr(source, field, value)
        self.db.flush()
        return source

    def due_sources(self, now: datetime, limit: int) -> list[TwitterSource]:
        stmt = (
            select(TwitterSource)
            .where(TwitterSource.is_active == True)  # noqa: E712
            .where((TwitterSource.next_scrape.is_(None)) | (TwitterSource.next_scrape <= now))
            .order_by(
                TwitterSource.next_scrape.is_not(None).asc(),
                TwitterSource.last_scraped.is_not(None).asc(),
                TwitterSource.last_scraped.asc(),
                TwitterSource.next_scrape.asc(),
                TwitterSource.id.asc(),
            )
            .limit(limit)
        )
        return list(self.db.scalars(stmt))

    def defer_due_sources(self, now: datetime, retry_at: datetime) -> int:
        sources = self.due_sources(now, limit=100_000)
        for source in sources:
            source.next_scrape = retry_at
        self.db.flush()
        return len(sources)
