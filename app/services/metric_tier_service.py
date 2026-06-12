from __future__ import annotations

from datetime import datetime, timedelta

from app.models.tweet import Tweet
from app.models.tweet_metric import TweetMetric
from app.scheduler_rules import engagement_weights, tweet_metric_rules
from app.utils.time import utc_now


def weighted_engagement(metric: TweetMetric) -> int:
    return (
        int(metric.like_count or 0) * engagement_weights.like
        + int(metric.reply_count or 0) * engagement_weights.reply
        + int(metric.retweet_count or 0) * engagement_weights.retweet
        + int(metric.quote_count or 0) * engagement_weights.quote
    )


def raw_engagement(metric: TweetMetric) -> int:
    return (
        int(metric.like_count or 0)
        + int(metric.reply_count or 0)
        + int(metric.retweet_count or 0)
        + int(metric.quote_count or 0)
    )


def engagement_rate(metric: TweetMetric, view_count: int | None) -> float:
    return raw_engagement(metric) / max(int(view_count or 0), 1) * 100


class TweetMetricTierService:
    def apply_snapshot(
        self,
        tweet: Tweet,
        current_metric: TweetMetric,
        previous_metric: TweetMetric | None,
        now: datetime | None = None,
    ) -> Tweet:
        update_time = current_metric.recorded_at or now or utc_now()
        score = weighted_engagement(current_metric)
        rate = engagement_rate(current_metric, tweet.view_count)

        tweet.weighted_engagement = score
        tweet.engagement_rate = rate
        tweet.last_metric_update = update_time
        tweet.metric_scan_miss_count = 0

        if previous_metric is None:
            velocity = 0.0
        else:
            velocity = self._velocity(score, previous_metric, update_time)
        tier = self._tier(tweet, velocity, rate, update_time, previous_metric is not None)

        tweet.last_engagement_velocity = velocity
        tweet.metric_tier = tier

        if tier == "expired":
            tweet.is_tracked = False
            tweet.next_metric_update = None
        else:
            tweet.is_tracked = True
            tweet.next_metric_update = update_time + timedelta(
                minutes=self._interval_minutes(tier)
            )
        return tweet

    def _velocity(
        self,
        current_score: int,
        previous_metric: TweetMetric,
        update_time: datetime,
    ) -> float:
        previous_time = previous_metric.recorded_at
        if previous_time is None:
            return 0.0
        elapsed_hours = (update_time - previous_time).total_seconds() / 3600
        if elapsed_hours <= 0:
            return 0.0
        previous_score = weighted_engagement(previous_metric)
        return max((current_score - previous_score) / elapsed_hours, 0.0)

    def _tier(
        self,
        tweet: Tweet,
        velocity: float,
        rate: float,
        update_time: datetime,
        has_previous_metric: bool,
    ) -> str:
        if self._tweet_age_hours(tweet, update_time) >= tweet_metric_rules.expired_age_hours:
            return "expired"
        if not has_previous_metric:
            return "bootstrap"
        if (
            velocity >= tweet_metric_rules.hot_velocity_min
            or rate >= tweet_metric_rules.hot_engagement_rate_min
        ):
            return "hot"
        if (
            velocity >= tweet_metric_rules.warm_velocity_min
            or rate >= tweet_metric_rules.warm_engagement_rate_min
        ):
            return "warm"
        return "cold"

    def _tweet_age_hours(self, tweet: Tweet, update_time: datetime) -> float:
        if tweet.posted_at is None:
            return 0.0
        return (update_time - tweet.posted_at).total_seconds() / 3600

    def _interval_minutes(self, tier: str) -> int:
        if tier == "hot":
            return tweet_metric_rules.hot_interval_minutes
        if tier == "warm":
            return tweet_metric_rules.warm_interval_minutes
        if tier == "bootstrap":
            return tweet_metric_rules.bootstrap_interval_minutes
        return tweet_metric_rules.cold_interval_minutes
