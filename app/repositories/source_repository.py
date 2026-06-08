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

    def create(self, payload: SourceCreate) -> TwitterSource:
        now = utc_now()
        source = TwitterSource(
            user_id=payload.user_id,
            source_type=payload.source_type,
            twitter_id=payload.twitter_id,
            twitter_url=payload.twitter_url,
            source_name=payload.source_name,
            description=payload.description,
            include_replies=payload.include_replies,
            max_days_old=payload.max_days_old,
            schedule_tier=payload.schedule_tier,
            schedule_override_minutes=payload.schedule_override_minutes,
            is_active=True,
            created_at=now,
            next_scrape=now,
        )
        self.db.add(source)
        self.db.flush()
        return source

    def deactivate(self, source: TwitterSource) -> TwitterSource:
        source.is_active = False
        self.db.flush()
        return source

    def due_sources(self, now: datetime, limit: int) -> list[TwitterSource]:
        stmt = (
            select(TwitterSource)
            .where(TwitterSource.is_active == True)  # noqa: E712
            .where((TwitterSource.next_scrape.is_(None)) | (TwitterSource.next_scrape <= now))
            .order_by(TwitterSource.next_scrape.asc(), TwitterSource.id.asc())
            .limit(limit)
        )
        return list(self.db.scalars(stmt))
