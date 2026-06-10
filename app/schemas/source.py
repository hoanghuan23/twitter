from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


SourceType = Literal["account", "hashtag", "keyword"]


class SourceCreate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "source_type": "account",
                "topic_id": 1,
                "source_name": "user_name",
                "include_replies": False,
                "max_days_old": 1,
            }
        }
    )

    account_username: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
        description=(
            "Optional crawler account username from the local accounts table. "
            "Omit this to use the first active crawler account."
        ),
    )
    source_type: SourceType
    topic_id: int | None = Field(default=None, ge=1)
    twitter_url: str | None = Field(default=None, min_length=1, max_length=255)
    twitter_id: str | None = Field(default=None, max_length=50)
    source_name: str | None = Field(
        default=None,
        max_length=255,
        description="For source_type='account', this is the target Twitter/X username to track.",
    )
    description: str | None = None
    include_replies: bool = False
    max_days_old: int | None = Field(default=None, ge=1)


class SourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    account_username: str
    source_type: str
    topic_id: int | None
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
    daily_views: int | None
    daily_engagement: int | None
    engagement_rate: float | None
    source_score: int | None
    protected: bool | None
    verified: bool | None


class DeleteResponse(BaseModel):
    deleted: bool
