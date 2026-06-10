from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.tweet import Tweet
from app.utils.time import utc_now


class TwitterPostRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list(
        self,
        source_id: int | None,
        author_username: str | None,
        limit: int,
        offset: int,
    ) -> list[Tweet]:
        stmt = select(Tweet)
        if source_id is not None:
            stmt = stmt.where(Tweet.source_id == source_id)
        if author_username is not None:
            stmt = stmt.where(Tweet.author_username == author_username)
        stmt = stmt.order_by(Tweet.posted_at.desc()).limit(limit).offset(offset)
        return list(self.db.scalars(stmt))

    def latest(self, limit: int) -> list[Tweet]:
        stmt = select(Tweet).order_by(Tweet.posted_at.desc()).limit(limit)
        return list(self.db.scalars(stmt))

    def latest_posted_at_for_source(self, source_id: int) -> datetime | None:
        stmt = (
            select(Tweet.posted_at)
            .where(Tweet.source_id == source_id)
            .order_by(Tweet.posted_at.desc())
            .limit(1)
        )
        return self.db.scalar(stmt)

    def get(self, post_id: int) -> Tweet | None:
        return self.db.get(Tweet, post_id)

    def get_by_tweet_id(self, tweet_id: str) -> Tweet | None:
        stmt = select(Tweet).where(Tweet.tweet_id == tweet_id)
        return self.db.scalar(stmt)

    def recent_for_source(
        self,
        source_id: int,
        cutoff: datetime,
    ) -> list[Tweet]:
        stmt = (
            select(Tweet)
            .where(Tweet.source_id == source_id)
            .where(Tweet.posted_at >= cutoff)
            .order_by(Tweet.posted_at.desc())
        )
        return list(self.db.scalars(stmt))

    def due_for_metric_update(self, now: datetime, limit: int) -> list[Tweet]:
        stmt = (
            select(Tweet)
            .where(Tweet.is_tracked == True)  # noqa: E712
            .where(Tweet.metric_tier != "expired")
            .where((Tweet.next_metric_update.is_(None)) | (Tweet.next_metric_update <= now))
            .order_by(Tweet.next_metric_update.asc(), Tweet.id.asc())
            .limit(limit)
        )
        return list(self.db.scalars(stmt))

    def upsert(self, source_id: int, data: dict[str, Any]) -> tuple[Tweet, bool]:
        tweet = self.get_by_tweet_id(data["tweet_id"])
        is_new = tweet is None
        if tweet is None:
            tweet = Tweet(source_id=source_id, tweet_id=data["tweet_id"])
            self.db.add(tweet)

        tweet.source_id = source_id
        tweet.tweet_url = data["tweet_url"]
        tweet.content = data.get("content")
        tweet.conversation_id = data.get("conversation_id")
        tweet.quoted_tweet_id = data.get("quoted_tweet_id")
        tweet.is_quote_tweet = data.get("is_quote_tweet", False)
        tweet.in_reply_to_tweet_id = data.get("in_reply_to_tweet_id")
        tweet.is_reply = data.get("is_reply", False)
        tweet.lang = data.get("lang")
        tweet.author_id = data.get("author_id")
        tweet.author_username = data.get("author_username")
        tweet.mentions = data.get("mentions")
        tweet.urls = data.get("urls")
        tweet.posted_at = data["posted_at"]
        tweet.created_at = data.get("created_at") or utc_now()
        tweet.view_count = data.get("view_count")
        tweet.possibly_sensitive = data.get("possibly_sensitive", False)
        tweet.hashtags = data.get("hashtags")
        tweet.media = data.get("media")
        self.db.flush()
        return tweet, is_new

    def mark_metric_miss(
        self,
        tweet: Tweet,
        miss_limit: int,
        retry_after: timedelta,
    ) -> Tweet:
        tweet.metric_scan_miss_count += 1
        if tweet.metric_scan_miss_count >= miss_limit:
            tweet.metric_tier = "expired"
            tweet.is_tracked = False
            tweet.next_metric_update = None
        else:
            tweet.next_metric_update = utc_now() + retry_after
        self.db.flush()
        return tweet
