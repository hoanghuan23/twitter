from __future__ import annotations

from datetime import date, datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.tweet import Tweet
from app.models.twitter_analytics_cache import TwitterAnalyticsCache
from app.models.twitter_source import TwitterSource
from app.repositories.metric_repository import TweetMetricRepository
from app.services.metric_tier_service import weighted_engagement
from app.utils.time import utc_now


class TwitterAnalyticsService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.metric_repository = TweetMetricRepository(db)

    def refresh_daily_cache(
        self,
        source: TwitterSource,
        target_date: date | None = None,
    ) -> TwitterAnalyticsCache:
        day = target_date or utc_now().date()
        day_start = datetime.combine(day, time.min)
        day_end = day_start + timedelta(days=1)
        tweets = self._tweets_for_day(source.id, day_start, day_end)
        metrics_by_tweet_id = self.metric_repository.latest_by_tweet_ids(
            [tweet.id for tweet in tweets]
        )

        total_likes = 0
        total_replies = 0
        total_retweets = 0
        total_quotes = 0
        top_tweet_id: str | None = None
        top_score = -1

        for tweet in tweets:
            metric = metrics_by_tweet_id.get(tweet.id)
            if metric is None:
                continue

            total_likes += int(metric.like_count or 0)
            total_replies += int(metric.reply_count or 0)
            total_retweets += int(metric.retweet_count or 0)
            total_quotes += int(metric.quote_count or 0)

            score = weighted_engagement(metric)
            if score > top_score:
                top_score = score
                top_tweet_id = tweet.tweet_id

        cache = self._get_or_create(source.id, day_start)
        cache.total_tweets = len(tweets)
        cache.total_likes = total_likes
        cache.total_replies = total_replies
        cache.total_retweets = total_retweets
        cache.total_quotes = total_quotes
        cache.avg_likes_per_tweet = total_likes / len(tweets) if tweets else 0
        cache.top_tweet_id = top_tweet_id
        cache.growth_rate = self._growth_rate(source.id, day_start, total_likes)
        cache.cached_at = utc_now()
        self.db.flush()
        return cache

    def refresh_existing_daily_caches(self) -> int:
        rows = self.db.execute(select(Tweet.source_id, Tweet.posted_at)).all()
        source_dates = {
            (source_id, posted_at.date())
            for source_id, posted_at in rows
            if posted_at is not None
        }

        refreshed_count = 0
        for source_id, target_date in source_dates:
            source = self.db.get(TwitterSource, source_id)
            if source is None:
                continue
            self.refresh_daily_cache(source, target_date)
            refreshed_count += 1
        return refreshed_count

    def _tweets_for_day(
        self,
        source_id: int,
        day_start: datetime,
        day_end: datetime,
    ) -> list[Tweet]:
        stmt = (
            select(Tweet)
            .where(Tweet.source_id == source_id)
            .where(Tweet.posted_at >= day_start)
            .where(Tweet.posted_at < day_end)
            .order_by(Tweet.posted_at.desc())
        )
        return list(self.db.scalars(stmt))

    def _get_or_create(
        self,
        source_id: int,
        day_start: datetime,
    ) -> TwitterAnalyticsCache:
        stmt = (
            select(TwitterAnalyticsCache)
            .where(TwitterAnalyticsCache.source_id == source_id)
            .where(TwitterAnalyticsCache.date == day_start)
            .limit(1)
        )
        cache = self.db.scalar(stmt)
        if cache is not None:
            return cache

        cache = TwitterAnalyticsCache(source_id=source_id, date=day_start)
        self.db.add(cache)
        self.db.flush()
        return cache

    def _growth_rate(
        self,
        source_id: int,
        day_start: datetime,
        total_likes: int,
    ) -> float | None:
        previous_day = day_start - timedelta(days=1)
        stmt = (
            select(TwitterAnalyticsCache)
            .where(TwitterAnalyticsCache.source_id == source_id)
            .where(TwitterAnalyticsCache.date == previous_day)
            .limit(1)
        )
        previous = self.db.scalar(stmt)
        if previous is None or not previous.total_likes:
            return None
        return (total_likes - previous.total_likes) / previous.total_likes * 100
