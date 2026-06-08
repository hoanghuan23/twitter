from __future__ import annotations

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
                    posted_at=tweet.posted_at,
                    created_at=tweet.created_at,
                    view_count=tweet.view_count,
                    like_count=metric.like_count if metric else None,
                    reply_count=metric.reply_count if metric else None,
                    retweet_count=metric.retweet_count if metric else None,
                    quote_count=metric.quote_count if metric else None,
                    bookmark_count=metric.bookmark_count if metric else None,
                )
            )
        return posts

