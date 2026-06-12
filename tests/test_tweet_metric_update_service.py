from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.pipeline_log import TwitterPipelineLog
from app.models.tweet import Tweet
from app.models.tweet_metric import TweetMetric
from app.models.twitter_analytics_cache import TwitterAnalyticsCache
from app.models.twitter_source import TwitterSource
from app.services.tweet_metric_update_service import TweetMetricUpdateService
from app.services import tweet_metric_update_service as metric_update_module
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


def raw_tweet(tweet_id: str, content: str, like_count: int = 200):
    return {
        "id": tweet_id,
        "url": f"https://x.com/example/status/{tweet_id}",
        "rawContent": content,
        "date": utc_now(),
        "user": {"id": "12345", "username": "example"},
        "likeCount": like_count,
        "replyCount": 0,
        "retweetCount": 0,
        "quoteCount": 0,
        "viewCount": 1000,
    }


def test_update_due_tweet_metrics_creates_update_job_and_refreshes_tiers(
    db_session: Session,
    caplog,
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
    caplog.set_level(logging.INFO, logger="app.services.tweet_metric_update_service")
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

    log_messages = "\n".join(caplog.messages)
    assert "Updated tweet metrics" in log_messages
    assert f"job_id={job.id}" in log_messages
    assert "tweet_id=123" in log_messages
    assert "like_count=200" in log_messages
    assert "reply_count=0" in log_messages
    assert "retweet_count=0" in log_messages
    assert "quote_count=0" in log_messages
    assert "Finished metric update" in log_messages
    assert "updated=1" in log_messages


def test_update_due_tweet_metrics_fetches_all_details_before_writing_metrics(
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
    tweets = [
        Tweet(
            source_id=1,
            tweet_id=str(tweet_id),
            tweet_url=f"https://x.com/example/status/{tweet_id}",
            content="old",
            posted_at=now,
            created_at=now,
            is_tracked=True,
            metric_tier="warm",
            next_metric_update=now - timedelta(minutes=1),
            view_count=100,
        )
        for tweet_id in (123, 456)
    ]
    db_session.add_all([source, *tweets])
    db_session.flush()
    for tweet in tweets:
        db_session.add(
            TweetMetric(tweet_id=tweet.id, like_count=0, recorded_at=now - timedelta(hours=1))
        )
    db_session.commit()

    class InspectingTweetDetailsClient:
        def __init__(self) -> None:
            self.calls: list[str] = []

        async def get_tweet_details(self, tweet_id: str):
            self.calls.append(tweet_id)
            metric_count = db_session.scalar(select(func.count()).select_from(TweetMetric))
            current_contents = db_session.scalars(
                select(Tweet.content).order_by(Tweet.tweet_id)
            ).all()
            assert metric_count == 2
            assert current_contents == ["old", "old"]
            return raw_tweet(tweet_id, f"updated-{tweet_id}", like_count=int(tweet_id))

    fake_client = InspectingTweetDetailsClient()
    service = TweetMetricUpdateService(db_session, client=fake_client)
    job = asyncio.run(service.update_due_tweet_metrics(limit=10))

    assert job is not None
    assert job.status == "done"
    assert fake_client.calls == ["123", "456"]
    assert db_session.scalar(select(func.count()).select_from(TweetMetric)) == 4
    assert db_session.scalars(select(Tweet.content).order_by(Tweet.tweet_id)).all() == [
        "updated-123",
        "updated-456",
    ]


def test_update_due_tweet_metrics_marks_job_failed_when_fetch_raises(
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
    db_session.commit()

    class RaisingTweetDetailsClient:
        async def get_tweet_details(self, tweet_id: str):
            raise RuntimeError(f"fetch failed for {tweet_id}")

    service = TweetMetricUpdateService(db_session, client=RaisingTweetDetailsClient())
    job = asyncio.run(service.update_due_tweet_metrics(limit=10))

    assert job is not None
    assert job.status == "failed"
    assert job.error_message == "fetch failed for 123"
    log = db_session.scalar(select(TwitterPipelineLog).where(TwitterPipelineLog.job_id == job.id))
    assert log is not None
    assert log.error_type == "RuntimeError"
    assert log.message == "fetch failed for 123"


def test_update_due_tweet_metrics_expires_old_tweets_without_fetching_details(
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
        tweet_id="old",
        tweet_url="https://x.com/example/status/old",
        content="old content",
        posted_at=now - timedelta(hours=24),
        created_at=now,
        is_tracked=True,
        metric_tier="hot",
        next_metric_update=now - timedelta(minutes=1),
        view_count=100,
    )
    db_session.add_all([source, tweet])
    db_session.commit()

    class NoFetchTweetDetailsClient:
        def __init__(self) -> None:
            self.calls: list[str] = []

        async def get_tweet_details(self, tweet_id: str):
            self.calls.append(tweet_id)
            raise AssertionError("old tweet details should not be fetched")

    fake_client = NoFetchTweetDetailsClient()
    service = TweetMetricUpdateService(db_session, client=fake_client)
    job = asyncio.run(service.update_due_tweet_metrics(limit=10))

    assert job is None
    assert fake_client.calls == []
    assert tweet.metric_tier == "expired"
    assert tweet.is_tracked is False
    assert tweet.next_metric_update is None
    assert db_session.scalar(select(func.count()).select_from(TweetMetric)) == 0


def test_update_due_tweet_metrics_waits_for_in_process_lock(db_session: Session) -> None:
    async def run() -> None:
        await metric_update_module._metric_update_lock.acquire()
        try:
            service = TweetMetricUpdateService(db_session, client=FakeTweetDetailsClient())
            task = asyncio.create_task(service.update_due_tweet_metrics(limit=10))
            await asyncio.sleep(0)
            assert not task.done()
        finally:
            metric_update_module._metric_update_lock.release()

        assert await task is None

    asyncio.run(run())
