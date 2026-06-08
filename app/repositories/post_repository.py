from __future__ import annotations

from datetime import datetime
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

    def get(self, post_id: int) -> Tweet | None:
        return self.db.get(Tweet, post_id)

    def get_by_tweet_id(self, tweet_id: str) -> Tweet | None:
        stmt = select(Tweet).where(Tweet.tweet_id == tweet_id)
        return self.db.scalar(stmt)

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
        tweet.last_metric_update = utc_now()
        self.db.flush()
        return tweet, is_new
