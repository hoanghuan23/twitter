from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models.twitter_source import TwitterSource
from app.repositories.metric_repository import TweetMetricRepository
from app.repositories.post_repository import TwitterPostRepository
from app.scheduler_rules import source_schedule_rules
from app.services.metric_tier_service import raw_engagement, weighted_engagement
from app.utils.time import utc_now


class SourceTierService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.post_repository = TwitterPostRepository(db)
        self.metric_repository = TweetMetricRepository(db)

    def refresh_source_score(
        self,
        source: TwitterSource,
        now: datetime | None = None,
    ) -> TwitterSource:
        current_time = now or utc_now()
        cutoff = current_time - timedelta(hours=source_schedule_rules.lookback_hours)
        tweets = self.post_repository.recent_for_source(source.id, cutoff)
        metrics_by_tweet_id = self.metric_repository.latest_by_tweet_ids(
            [tweet.id for tweet in tweets]
        )

        daily_views = 0
        daily_engagement = 0
        source_score = 0
        for tweet in tweets:
            metric = metrics_by_tweet_id.get(tweet.id)
            if metric is None:
                continue
            daily_views += int(tweet.view_count or 0)
            daily_engagement += raw_engagement(metric)
            source_score += weighted_engagement(metric)

        rate = daily_engagement / max(daily_views, 1) * 100
        source.daily_views = daily_views
        source.daily_engagement = daily_engagement
        source.engagement_rate = rate
        source.source_score = source_score
        source.schedule_tier = self._schedule_tier(daily_views, rate)
        self.db.flush()
        return source

    def interval_minutes(self, source: TwitterSource) -> int:
        if source.schedule_override_minutes:
            return source.schedule_override_minutes
        if source.schedule_tier == 1:
            return source_schedule_rules.tier_1_interval_minutes
        if source.schedule_tier == 2:
            return source_schedule_rules.tier_2_interval_minutes
        if source.schedule_tier == 3:
            return source_schedule_rules.tier_3_interval_minutes
        return source_schedule_rules.tier_4_interval_minutes

    def _schedule_tier(self, daily_views: int, engagement_rate: float) -> int:
        if (
            daily_views >= source_schedule_rules.tier_1_daily_views_min
            or engagement_rate >= source_schedule_rules.tier_1_engagement_rate_min
        ):
            return 1
        if (
            daily_views >= source_schedule_rules.tier_2_daily_views_min
            or engagement_rate >= source_schedule_rules.tier_2_engagement_rate_min
        ):
            return 2
        if daily_views >= source_schedule_rules.tier_3_daily_views_min:
            return 3
        return 4
