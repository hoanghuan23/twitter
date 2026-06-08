from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class JobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_type: str
    source_id: int | None
    session_id: int | None
    status: str
    tweets_found: int
    tweets_new: int
    items_total: int
    items_updated: int
    items_failed: int
    rate_limit_hits: int
    error_message: str | None
    started_at: datetime | None
    finished_at: datetime | None


class CrawlDueResponse(BaseModel):
    jobs_started: int
    job_ids: list[int]

