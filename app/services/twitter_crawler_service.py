from __future__ import annotations

import traceback
from datetime import date

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.crawler.tweet_normalizer import normalize_tweet
from app.crawler.twscrape_client import TwscrapeClient
from app.models.pipeline_job import TwitterPipelineJob
from app.repositories.job_repository import TwitterPipelineJobRepository
from app.repositories.metric_repository import TweetMetricRepository
from app.repositories.post_repository import TwitterPostRepository
from app.repositories.source_repository import TwitterSourceRepository
from app.services.metric_tier_service import TweetMetricTierService
from app.services.source_tier_service import SourceTierService
from app.services.twitter_analytics_service import TwitterAnalyticsService
from app.services.twitter_source_service import TwitterSourceService
from app.utils.time import utc_now


class TwitterCrawlerService:
    def __init__(
        self,
        db: Session,
        client: TwscrapeClient | None = None,
    ) -> None:
        self.db = db
        self.client = client or TwscrapeClient()
        self.source_repository = TwitterSourceRepository(db)
        self.post_repository = TwitterPostRepository(db)
        self.metric_repository = TweetMetricRepository(db)
        self.job_repository = TwitterPipelineJobRepository(db)
        self.source_service = TwitterSourceService(db)
        self.metric_tier_service = TweetMetricTierService()
        self.source_tier_service = SourceTierService(db)
        self.analytics_service = TwitterAnalyticsService(db)

    async def crawl_source(self, source_id: int, limit: int | None = None) -> TwitterPipelineJob:
        source = self.source_repository.get(source_id)
        if source is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Source not found")

        job = self.job_repository.create_running(
            source_id=source.id,
            session_username=source.account_username,
            job_type="scrape_timeline",
        )
        self.db.commit()

        tweets_found = 0
        tweets_new = 0
        items_updated = 0
        try:
            raw_tweets = [
                raw_tweet
                async for raw_tweet in self.client.crawl_source(source, limit=limit)
            ]
            tweets_found = len(raw_tweets)
            affected_dates: set[date] = set()
            current_time = utc_now()

            for raw_tweet in raw_tweets:
                data = normalize_tweet(raw_tweet)
                metric_data = data.pop("metrics", {})
                existing_tweet = self.post_repository.get_by_tweet_id(data["tweet_id"])
                should_record_metric = (
                    existing_tweet is None
                    or existing_tweet.next_metric_update is None
                    or existing_tweet.next_metric_update <= current_time
                )
                if not should_record_metric:
                    continue

                tweet, is_new = self.post_repository.upsert(source.id, data)
                affected_dates.add(tweet.posted_at.date())
                previous_metric = self.metric_repository.latest_for_tweet(tweet.id)
                metric = self.metric_repository.create_snapshot(tweet.id, job.id, metric_data)
                self.metric_tier_service.apply_snapshot(tweet, metric, previous_metric)
                tweets_new += 1 if is_new else 0
                items_updated += 0 if is_new else 1

            self.source_tier_service.refresh_source_score(source)
            for affected_date in affected_dates:
                self.analytics_service.refresh_daily_cache(source, affected_date)
            self.source_service.mark_scraped(source)
            self.job_repository.mark_done(
                job,
                tweets_found=tweets_found,
                tweets_new=tweets_new,
                items_updated=items_updated,
            )
            self.db.commit()
            return job
        except Exception as exc:
            self.db.rollback()
            error_message = str(exc)
            job = self.job_repository.get(job.id) or job
            self.job_repository.mark_failed(job, error_message)
            self.job_repository.log(
                job_id=job.id,
                source_id=source.id,
                level="ERROR",
                message=error_message,
                error_type=exc.__class__.__name__,
                error_details=traceback.format_exc(),
            )
            self.db.commit()
            return job
