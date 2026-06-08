from __future__ import annotations

import asyncio
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.tweet import Tweet
from app.models.tweet_metric import TweetMetric
from app.models.twitter_source import TwitterSource
from app.services.twitter_crawler_service import TwitterCrawlerService
from app.utils.time import utc_now


class FakeTwscrapeClient:
    async def crawl_source(self, source: TwitterSource, limit: int | None = None):
        yield {
            "id": "tweet-1",
            "url": "https://x.com/example/status/tweet-1",
            "rawContent": "hello",
            "date": utc_now(),
            "user": {"id": "12345", "username": "example"},
            "likeCount": 7,
            "replyCount": 2,
            "retweetCount": 1,
            "quoteCount": 0,
            "bookmarkCount": 3,
        }


def test_crawler_service_persists_tweets_metrics_and_job(db_session: Session) -> None:
    db_session.add(Account(user_id=1, username="crawler"))
    db_session.add(
        TwitterSource(
            id=1,
            user_id=1,
            source_type="account",
            twitter_id="12345",
            twitter_url="https://x.com/example",
            is_active=True,
            created_at=utc_now(),
        )
    )
    db_session.commit()

    service = TwitterCrawlerService(db_session, client=FakeTwscrapeClient())
    job = asyncio.run(service.crawl_source(1))

    assert job.status == "done"
    assert job.tweets_found == 1
    assert job.tweets_new == 1

    tweet = db_session.scalar(select(Tweet).where(Tweet.tweet_id == "tweet-1"))
    assert tweet is not None
    assert tweet.content == "hello"

    metric = db_session.scalar(select(TweetMetric).where(TweetMetric.tweet_id == tweet.id))
    assert metric is not None
    assert metric.like_count == 7
