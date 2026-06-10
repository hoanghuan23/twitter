from __future__ import annotations

import asyncio
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.tweet import Tweet
from app.models.tweet_metric import TweetMetric
from app.models.twitter_analytics_cache import TwitterAnalyticsCache
from app.models.twitter_source import TwitterSource
from app.services.tweet_metric_update_service import TweetMetricUpdateService
from app.utils.time import utc_now


class FakeTweetDetailsClient:
    async def get_tweet_details(self, tweet_id: str):
        assert tweet_id == "123"
        return {
            "id": "123",
            "url": "https://x.com/example/status/123",
            "rawContent": "updated",
            "date": utc_now(),
            "user": {"id": "12345", "username": "example"},
            "likeCount": 200,
            "replyCount": 0,
            "retweetCount": 0,
            "quoteCount": 0,
            "viewCount": 1000,
        }


def test_update_due_tweet_metrics_creates_update_job_and_refreshes_tiers(
    db_session: Session,
) -> None:
    now = utc_now()
    db_session.add(Account(username="crawler"))
    source = TwitterSource(
        id=1,
        account_username="crawler",
        source_type="account",
        twitter_id="12345",
        twitter_url="https://x.com/example",
        source_name="example",
        is_active=True,
        created_at=now,
    )
    tweet = Tweet(
        source_id=1,
        tweet_id="123",
        tweet_url="https://x.com/example/status/123",
        content="old",
        posted_at=now,
        created_at=now,
        is_tracked=True,
        metric_tier="warm",
        next_metric_update=now - timedelta(minutes=1),
        view_count=100,
    )
    db_session.add_all([source, tweet])
    db_session.flush()
    db_session.add(
        TweetMetric(tweet_id=tweet.id, like_count=0, recorded_at=now - timedelta(hours=1))
    )
    db_session.commit()

    service = TweetMetricUpdateService(db_session, client=FakeTweetDetailsClient())
    job = asyncio.run(service.update_due_tweet_metrics(limit=10))

    assert job is not None
    assert job.job_type == "update_metric"
    assert job.status == "done"
    assert job.items_updated == 1

    metrics = db_session.scalars(
        select(TweetMetric).where(TweetMetric.tweet_id == tweet.id)
    ).all()
    assert len(metrics) == 2
    assert tweet.content == "updated"
    assert tweet.metric_tier == "hot"
    assert source.daily_views == 1000
    assert source.schedule_tier == 1

    analytics = db_session.scalar(
        select(TwitterAnalyticsCache).where(TwitterAnalyticsCache.source_id == source.id)
    )
    assert analytics is not None
    assert analytics.total_tweets == 1
    assert analytics.total_likes == 200
    assert analytics.top_tweet_id == "123"
