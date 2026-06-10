from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EngagementWeights:
    like: int = 1
    reply: int = 4
    retweet: int = 6
    quote: int = 8


@dataclass(frozen=True)
class TweetMetricRules:
    bootstrap_interval_minutes: int = 20
    hot_interval_minutes: int = 15
    warm_interval_minutes: int = 30
    cold_interval_minutes: int = 120
    hot_velocity_min: float = 150
    warm_velocity_min: float = 50
    cold_velocity_min: float = 10
    hot_engagement_rate_min: float = 5
    warm_engagement_rate_min: float = 2
    expired_age_hours: int = 24
    metric_scan_miss_limit: int = 3
    metric_scan_miss_retry_minutes: int = 60


@dataclass(frozen=True)
class SourceScheduleRules:
    lookback_hours: int = 24
    tier_1_interval_minutes: int = 60
    tier_2_interval_minutes: int = 120
    tier_3_interval_minutes: int = 180
    tier_4_interval_minutes: int = 360
    tier_1_daily_views_min: int = 1_000_000
    tier_2_daily_views_min: int = 100_000
    tier_3_daily_views_min: int = 10_000
    tier_1_engagement_rate_min: float = 3
    tier_2_engagement_rate_min: float = 1


engagement_weights = EngagementWeights()
tweet_metric_rules = TweetMetricRules()
source_schedule_rules = SourceScheduleRules()
