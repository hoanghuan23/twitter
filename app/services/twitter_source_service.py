from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.models.twitter_source import TwitterSource
from app.repositories.source_repository import TwitterSourceRepository
from app.schemas.source import SourceCreate
from app.utils.time import utc_now


class TwitterSourceService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = TwitterSourceRepository(db)

    def list_sources(
        self,
        active: bool | None,
        limit: int,
        offset: int,
    ) -> list[TwitterSource]:
        return self.repository.list(active=active, limit=limit, offset=offset)

    def get_source(self, source_id: int) -> TwitterSource:
        source = self.repository.get(source_id)
        if source is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Source not found")
        return source

    def create_source(self, payload: SourceCreate) -> TwitterSource:
        source = self.repository.create(payload)
        self.db.commit()
        return source

    def deactivate_source(self, source_id: int) -> bool:
        source = self.get_source(source_id)
        self.repository.deactivate(source)
        self.db.commit()
        return True

    def due_sources(self, limit: int) -> list[TwitterSource]:
        return self.repository.due_sources(utc_now(), limit)

    def mark_scraped(self, source: TwitterSource) -> None:
        interval = self.scrape_interval_minutes(source)
        now = utc_now()
        source.last_scraped = now
        source.next_scrape = now + timedelta(minutes=interval)
        self.db.flush()

    def scrape_interval_minutes(self, source: TwitterSource) -> int:
        if source.schedule_override_minutes:
            return source.schedule_override_minutes
        if source.schedule_tier == 1:
            return 15
        if source.schedule_tier == 2:
            return 60
        if source.schedule_tier == 3:
            return 360
        return settings.default_scrape_interval_minutes
