from __future__ import annotations

from datetime import timedelta

from app.models.tweet import Tweet
from app.models.tweet_metric import TweetMetric
from app.scheduler_rules import tweet_metric_rules
from app.services.metric_tier_service import TweetMetricTierService
from app.utils.time import utc_now


def _tweet(age_hours: int = 1, view_count: int = 1000) -> Tweet:
    now = utc_now()
    return Tweet(
        source_id=1,
        tweet_id="tweet-1",
        tweet_url="https://x.com/example/status/tweet-1",
        posted_at=now - timedelta(hours=age_hours),
        view_count=view_count,
    )


def test_first_snapshot_bootstraps_score_rate_and_next_update() -> None:
    now = utc_now()
    tweet = _tweet()
    metric = TweetMetric(
        like_count=50,
        reply_count=10,
        retweet_count=20,
        quote_count=5,
        recorded_at=now,
    )

    TweetMetricTierService().apply_snapshot(tweet, metric, previous_metric=None)

    assert tweet.weighted_engagement == 250
    assert tweet.engagement_rate == 8.5
    assert tweet.last_engagement_velocity == 0
    assert tweet.metric_tier == "bootstrap"
    assert tweet.next_metric_update == now + timedelta(
        minutes=tweet_metric_rules.bootstrap_interval_minutes
    )


def test_velocity_is_clamped_and_young_slow_tweet_stays_cold() -> None:
    now = utc_now()
    tweet = _tweet(age_hours=2, view_count=10_000)
    previous = TweetMetric(like_count=100, recorded_at=now - timedelta(hours=1))
    current = TweetMetric(like_count=50, recorded_at=now)

    TweetMetricTierService().apply_snapshot(tweet, current, previous)

    assert tweet.last_engagement_velocity == 0
    assert tweet.metric_tier == "cold"
    assert tweet.is_tracked is True
    assert tweet.next_metric_update == now + timedelta(
        minutes=tweet_metric_rules.cold_interval_minutes
    )


def test_hot_warm_and_expired_tiers() -> None:
    now = utc_now()
    service = TweetMetricTierService()

    hot = _tweet()
    service.apply_snapshot(
        hot,
        TweetMetric(like_count=200, recorded_at=now),
        TweetMetric(like_count=0, recorded_at=now - timedelta(hours=1)),
    )
    assert hot.metric_tier == "hot"

    warm = _tweet(view_count=10_000)
    service.apply_snapshot(
        warm,
        TweetMetric(like_count=70, recorded_at=now),
        TweetMetric(like_count=0, recorded_at=now - timedelta(hours=1)),
    )
    assert warm.metric_tier == "warm"

    expired = _tweet(age_hours=25)
    service.apply_snapshot(
        expired,
        TweetMetric(like_count=1, recorded_at=now),
        TweetMetric(like_count=1, recorded_at=now - timedelta(hours=1)),
    )
    assert expired.metric_tier == "expired"
    assert expired.is_tracked is False
    assert expired.next_metric_update is None


def test_tweets_at_or_over_24h_expire_even_with_hot_metrics() -> None:
    now = utc_now()
    at_cutoff = Tweet(
        source_id=1,
        tweet_id="at-cutoff",
        tweet_url="https://x.com/example/status/at-cutoff",
        posted_at=now - timedelta(hours=24),
        view_count=1_000,
    )
    over_cutoff = Tweet(
        source_id=1,
        tweet_id="over-cutoff",
        tweet_url="https://x.com/example/status/over-cutoff",
        posted_at=now - timedelta(hours=25),
        view_count=1_000,
    )

    for tweet in (at_cutoff, over_cutoff):
        TweetMetricTierService().apply_snapshot(
            tweet,
            TweetMetric(like_count=10_000, recorded_at=now),
            TweetMetric(like_count=0, recorded_at=now - timedelta(hours=1)),
        )

        assert tweet.metric_tier == "expired"
        assert tweet.is_tracked is False
        assert tweet.next_metric_update is None
