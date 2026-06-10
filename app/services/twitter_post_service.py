from __future__ import annotations

import json
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.tweet import Tweet
from app.repositories.metric_repository import TweetMetricRepository
from app.repositories.post_repository import TwitterPostRepository
from app.schemas.post import PostRead


class TwitterPostService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = TwitterPostRepository(db)
        self.metric_repository = TweetMetricRepository(db)

    def list_posts(
        self,
        source_id: int | None,
        author_username: str | None,
        limit: int,
        offset: int,
    ) -> list[PostRead]:
        tweets = self.repository.list(source_id, author_username, limit, offset)
        return self._to_post_reads(tweets)

    def latest_posts(self, limit: int) -> list[PostRead]:
        tweets = self.repository.latest(limit)
        return self._to_post_reads(tweets)

    def get_post(self, post_id: int) -> PostRead:
        tweet = self.repository.get(post_id)
        if tweet is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Post not found")
        return self._to_post_reads([tweet])[0]

    def upsert_post(self, source_id: int, data: dict[str, Any]) -> tuple[Tweet, bool]:
        return self.repository.upsert(source_id, data)

    def _to_post_reads(self, tweets: list[Tweet]) -> list[PostRead]:
        metrics_by_tweet_id = self.metric_repository.latest_by_tweet_ids(
            [tweet.id for tweet in tweets]
        )
        posts: list[PostRead] = []
        for tweet in tweets:
            metric = metrics_by_tweet_id.get(tweet.id)
            posts.append(
                PostRead(
                    id=tweet.id,
                    source_id=tweet.source_id,
                    post_id=tweet.tweet_id,
                    post_url=tweet.tweet_url,
                    content=tweet.content,
                    conversation_id=tweet.conversation_id,
                    lang=tweet.lang,
                    author_id=tweet.author_id,
                    author_username=tweet.author_username,
                    media=self._media_urls(tweet.media),
                    posted_at=tweet.posted_at,
                    created_at=tweet.created_at,
                    view_count=tweet.view_count,
                    like_count=metric.like_count if metric else None,
                    reply_count=metric.reply_count if metric else None,
                    retweet_count=metric.retweet_count if metric else None,
                    quote_count=metric.quote_count if metric else None,
                    weighted_engagement=tweet.weighted_engagement,
                    last_velocity=tweet.last_engagement_velocity,
                    engagement_rate=tweet.engagement_rate,
                    metric_tier=tweet.metric_tier,
                    last_metric_update=tweet.last_metric_update,
                    next_metric_update=tweet.next_metric_update,
                )
            )
        return posts

    def _media_urls(self, media: str | None) -> list[str]:
        if not media:
            return []
        try:
            value = json.loads(media)
        except json.JSONDecodeError:
            return []
        if not isinstance(value, list):
            return []
        return [item for item in value if isinstance(item, str)]
