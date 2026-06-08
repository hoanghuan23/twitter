from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class PostRead(BaseModel):
    id: int
    source_id: int
    post_id: str
    post_url: str
    content: str | None
    conversation_id: str | None
    lang: str | None
    author_id: str | None
    author_username: str | None
    posted_at: datetime
    created_at: datetime | None
    view_count: int | None
    like_count: int | None = None
    reply_count: int | None = None
    retweet_count: int | None = None
    quote_count: int | None = None
    bookmark_count: int | None = None

