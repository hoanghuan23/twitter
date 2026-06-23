from __future__ import annotations

import logging
import traceback
from datetime import date, timedelta

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
from app.services.account_quota_service import AccountQuotaService
from app.utils.time import utc_now

try:
    from twscrape.accounts_pool import NoAccountError
except ImportError:
    class NoAccountError(Exception):
        pass


logger = logging.getLogger(__name__)


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
        self.account_quota_service = AccountQuotaService()

    async def crawl_source(self, source_id: int, limit: int | None = None) -> TwitterPipelineJob:
        source = self.source_repository.get(source_id)
        if source is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Source not found")

        job = self.job_repository.create_running(
            source_id=source.id,
            session_username=None,
            job_type="scrape_timeline",
        )
        self.db.commit()
        logger.info("------------------")
        logger.info(
            "Starting source scrape job_id=%s source_id=%s source_type=%s "
            "source_name=%s limit=%s",
            job.id,
            source.id,
            source.source_type,
            source.source_name,
            limit,
        )

        tweets_found = 0
        tweets_new = 0
        items_updated = 0
        tweets_recent_24h_found = 0
        tweets_recent_24h_saved = 0
        availability = self.account_quota_service.availability("UserTweets")
        if not availability.available:
            return self._defer_no_account_job(
                job.id,
                source.id,
                availability.retry_at,
                "No twscrape account available for queue UserTweets",
            )

        try:
            affected_dates: set[date] = set()
            latest_posted_at = self.post_repository.latest_posted_at_for_source(source.id)
            consecutive_old_posts = 0
            recent_24h_cutoff = utc_now() - timedelta(hours=24)

            async for raw_tweet in self.client.crawl_source(source, limit=limit):
                tweets_found += 1
                data = normalize_tweet(raw_tweet)
                is_recent_24h = data["posted_at"] >= recent_24h_cutoff
                tweets_recent_24h_found += 1 if is_recent_24h else 0
                if (
                    latest_posted_at is not None
                    and data["posted_at"] <= latest_posted_at
                ):
                    consecutive_old_posts += 1
                    if consecutive_old_posts >= 2:
                        break
                    continue

                consecutive_old_posts = 0
                metric_data = data.pop("metrics", {})
                tweet, is_new = self.post_repository.upsert(source.id, data)
                affected_dates.add(tweet.posted_at.date())
                previous_metric = self.metric_repository.latest_for_tweet(tweet.id)
                metric = self.metric_repository.create_snapshot(tweet.id, job.id, metric_data)
                self.metric_tier_service.apply_snapshot(tweet, metric, previous_metric)
                tweets_new += 1 if is_new else 0
                items_updated += 0 if is_new else 1
                tweets_recent_24h_saved += 1 if is_recent_24h else 0

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
            logger.info(
                "------------------\n"
                "Finished source scrape job_id=%s source_id=%s source_name=%s "
                "tweets_found=%s tweets_new=%s items_updated=%s "
                "tweets_recent_24h_found=%s tweets_recent_24h_saved=%s "
                "affected_dates=%s next_scrape=%s",
                job.id,
                source.id,
                source.source_name,
                tweets_found,
                tweets_new,
                items_updated,
                tweets_recent_24h_found,
                tweets_recent_24h_saved,
                len(affected_dates),
                source.next_scrape,
            )
            self.db.commit()
            return job
        except NoAccountError as exc:
            return self._defer_no_account_job(
                job.id,
                source.id,
                self.account_quota_service.retry_at("UserTweets"),
                str(exc) or "No twscrape account available for queue UserTweets",
            )
        except Exception as exc:
            self.db.rollback()
            error_message = str(exc)
            job = self.job_repository.get(job.id) or job
            self.job_repository.mark_failed(job, error_message)
            logger.exception(
                "Source scrape failed job_id=%s source_id=%s source_name=%s "
                "error_type=%s error=%s",
                job.id,
                source.id,
                source.source_name,
                exc.__class__.__name__,
                error_message,
            )
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

    def _defer_no_account_job(
        self,
        job_id: int,
        source_id: int,
        retry_at,
        detail: str,
    ) -> TwitterPipelineJob:
        self.db.rollback()
        job = self.job_repository.get(job_id)
        source = self.source_repository.get(source_id)
        if job is None or source is None:
            raise RuntimeError("Crawl job or source disappeared while deferring")

        source.next_scrape = retry_at
        message = f"{detail}; deferred until {retry_at.isoformat()}"
        self.job_repository.mark_deferred(job, message)
        self.job_repository.log(
            job_id=job.id,
            source_id=source.id,
            level="WARNING",
            message=message,
            error_type="NoAccountError",
        )
        logger.warning(
            "Source scrape deferred job_id=%s source_id=%s queue=UserTweets retry_at=%s",
            job.id,
            source.id,
            retry_at,
        )
        self.db.commit()
        return job
