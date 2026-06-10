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
            "viewCount": 1000,
        }


class ExistingTweetNotDueClient:
    async def crawl_source(self, source: TwitterSource, limit: int | None = None):
        yield {
            "id": "tweet-1",
            "url": "https://x.com/example/status/tweet-1",
            "rawContent": "changed content",
            "date": utc_now(),
            "user": {"id": "12345", "username": "example"},
            "likeCount": 99,
            "replyCount": 0,
            "retweetCount": 0,
            "quoteCount": 0,
            "viewCount": 5000,
        }


def test_crawler_service_persists_tweets_metrics_and_job(db_session: Session) -> None:
    db_session.add(Account(username="crawler"))
    db_session.add(
        TwitterSource(
            id=1,
            account_username="crawler",
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
    assert job.session_username == "crawler"
    assert job.tweets_found == 1
    assert job.tweets_new == 1

    tweet = db_session.scalar(select(Tweet).where(Tweet.tweet_id == "tweet-1"))
    assert tweet is not None
    assert tweet.content == "hello"
    assert tweet.weighted_engagement == 21
    assert tweet.engagement_rate == 1
    assert tweet.metric_tier == "bootstrap"
    assert tweet.next_metric_update is not None

    metric = db_session.scalar(select(TweetMetric).where(TweetMetric.tweet_id == tweet.id))
    assert metric is not None
    assert metric.like_count == 7

    source = db_session.get(TwitterSource, 1)
    assert source is not None
    assert source.daily_views == 1000
    assert source.daily_engagement == 10
    assert source.source_score == 21
    assert source.schedule_tier == 2
    assert source.next_scrape is not None

    analytics = db_session.scalar(
        select(TwitterAnalyticsCache).where(TwitterAnalyticsCache.source_id == source.id)
    )
    assert analytics is not None
    assert analytics.total_tweets == 1
    assert analytics.total_likes == 7
    assert analytics.total_replies == 2
    assert analytics.total_retweets == 1
    assert analytics.total_quotes == 0
    assert analytics.avg_likes_per_tweet == 7
    assert analytics.top_tweet_id == "tweet-1"


def test_crawler_service_skips_existing_tweet_metrics_before_due_time(
    db_session: Session,
) -> None:
    now = utc_now()
    db_session.add(Account(username="crawler"))
    db_session.add(
        TwitterSource(
            id=1,
            account_username="crawler",
            source_type="account",
            twitter_id="12345",
            twitter_url="https://x.com/example",
            is_active=True,
            created_at=now,
        )
    )
    tweet = Tweet(
        source_id=1,
        tweet_id="tweet-1",
        tweet_url="https://x.com/example/status/tweet-1",
        content="original content",
        posted_at=now,
        is_tracked=True,
        last_metric_update=now - timedelta(minutes=5),
        metric_tier="warm",
        next_metric_update=now + timedelta(minutes=30),
        view_count=1000,
    )
    db_session.add(tweet)
    db_session.flush()
    db_session.add(
        TweetMetric(
            tweet_id=tweet.id,
            like_count=7,
            reply_count=2,
            retweet_count=1,
            quote_count=0,
            recorded_at=now - timedelta(minutes=5),
        )
    )
    db_session.commit()

    service = TwitterCrawlerService(db_session, client=ExistingTweetNotDueClient())
    job = asyncio.run(service.crawl_source(1))

    assert job.status == "done"
    assert job.tweets_found == 1
    assert job.tweets_new == 0
    assert job.items_updated == 0

    db_session.refresh(tweet)
    assert tweet.content == "original content"
    assert tweet.view_count == 1000
    assert tweet.last_metric_update == now - timedelta(minutes=5)
    assert tweet.next_metric_update == now + timedelta(minutes=30)

    metrics = db_session.scalars(
        select(TweetMetric).where(TweetMetric.tweet_id == tweet.id)
    ).all()
    assert len(metrics) == 1
    assert metrics[0].like_count == 7
