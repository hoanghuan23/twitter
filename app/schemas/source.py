from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


SourceType = Literal["account", "hashtag", "keyword"]


class SourceCreate(BaseModel):
    user_id: int
    source_type: SourceType
    twitter_url: str = Field(min_length=1, max_length=255)
    twitter_id: str | None = Field(default=None, max_length=50)
    source_name: str | None = Field(default=None, max_length=255)
    description: str | None = None
    include_replies: bool = False
    max_days_old: int | None = Field(default=None, ge=1)
    schedule_tier: int | None = Field(default=None, ge=1)
    schedule_override_minutes: int | None = Field(default=None, ge=1)


class SourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    source_type: str
    twitter_id: str | None
    twitter_url: str
    source_name: str | None
    description: str | None
    followers_count: int | None
    following_count: int | None
    tweet_count: int | None
    is_active: bool | None
    include_replies: bool | None
    max_days_old: int | None
    created_at: datetime | None
    last_scraped: datetime | None
    next_scrape: datetime | None
    schedule_tier: int | None
    schedule_override_minutes: int | None
    protected: bool | None
    verified: bool | None


class DeleteResponse(BaseModel):
    deleted: bool

