from __future__ import annotations

import logging
import traceback
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.crawler.tweet_normalizer import normalize_tweet
from app.crawler.twscrape_client import TwscrapeClient
from app.models.pipeline_job import TwitterPipelineJob
from app.repositories.job_repository import TwitterPipelineJobRepository
from app.repositories.metric_repository import TweetMetricRepository
from app.repositories.post_repository import TwitterPostRepository
from app.repositories.source_repository import TwitterSourceRepository
from app.scheduler_rules import tweet_metric_rules
from app.services.metric_tier_service import TweetMetricTierService
from app.services.source_tier_service import SourceTierService
from app.services.twitter_analytics_service import TwitterAnalyticsService
from app.utils.time import utc_now


logger = logging.getLogger(__name__)


class TweetMetricUpdateService:
    def __init__(
        self,
        db: Session,
        client: TwscrapeClient | None = None,
    ) -> None:
        self.db = db
        self.client = client or TwscrapeClient()
        self.post_repository = TwitterPostRepository(db)
        self.metric_repository = TweetMetricRepository(db)
        self.source_repository = TwitterSourceRepository(db)
        self.job_repository = TwitterPipelineJobRepository(db)
        self.metric_tier_service = TweetMetricTierService()
        self.source_tier_service = SourceTierService(db)
        self.analytics_service = TwitterAnalyticsService(db)

    async def update_due_tweet_metrics(self, limit: int) -> TwitterPipelineJob | None:
        due_tweets = self.post_repository.due_for_metric_update(utc_now(), limit)
        if not due_tweets:
            logger.debug("No tweets due for metric update limit=%s", limit)
            return None

        job = self.job_repository.create_running(
            source_id=None,
            session_username=None,
            job_type="update_metric",
        )
        self.db.commit()
        logger.info(
            "Starting metric update job_id=%s due_tweets=%s limit=%s",
            job.id,
            len(due_tweets),
            limit,
        )

        items_updated = 0
        items_failed = 0
        affected_source_ids: set[int] = set()
        affected_dates_by_source_id: dict[int, set[date]] = {}
        try:
            for tweet in due_tweets:
                affected_source_ids.add(tweet.source_id)
                raw_tweet = await self.client.get_tweet_details(tweet.tweet_id)
                if raw_tweet is None:
                    self.post_repository.mark_metric_miss(
                        tweet,
                        miss_limit=tweet_metric_rules.metric_scan_miss_limit,
                        retry_after=timedelta(
                            minutes=tweet_metric_rules.metric_scan_miss_retry_minutes
                        ),
                    )
                    items_failed += 1
                    logger.warning(
                        "Tweet metric miss job_id=%s tweet_id=%s source_id=%s "
                        "miss_count=%s is_tracked=%s metric_tier=%s next_metric_update=%s",
                        job.id,
                        tweet.tweet_id,
                        tweet.source_id,
                        tweet.metric_scan_miss_count,
                        tweet.is_tracked,
                        tweet.metric_tier,
                        tweet.next_metric_update,
                    )
                    continue

                data = normalize_tweet(raw_tweet)
                metric_data = data.pop("metrics", {})
                previous_metric = self.metric_repository.latest_for_tweet(tweet.id)
                updated_tweet, _ = self.post_repository.upsert(tweet.source_id, data)
                metric = self.metric_repository.create_snapshot(
                    updated_tweet.id,
                    job.id,
                    metric_data,
                )
                self.metric_tier_service.apply_snapshot(
                    updated_tweet,
                    metric,
                    previous_metric,
                )
                affected_dates_by_source_id.setdefault(updated_tweet.source_id, set()).add(
                    updated_tweet.posted_at.date()
                )
                items_updated += 1
                logger.info(
                    "Updated tweet metrics job_id=%s tweet_id=%s source_id=%s "
                    "author=%s url=%s like_count=%s reply_count=%s retweet_count=%s "
                    "quote_count=%s view_count=%s metric_tier=%s next_metric_update=%s",
                    job.id,
                    updated_tweet.tweet_id,
                    updated_tweet.source_id,
                    updated_tweet.author_username,
                    updated_tweet.tweet_url,
                    metric.like_count,
                    metric.reply_count,
                    metric.retweet_count,
                    metric.quote_count,
                    updated_tweet.view_count,
                    updated_tweet.metric_tier,
                    updated_tweet.next_metric_update,
                )

            for source_id in affected_source_ids:
                source = self.source_repository.get(source_id)
                if source is not None:
                    self.source_tier_service.refresh_source_score(source)
                    for affected_date in affected_dates_by_source_id.get(source_id, set()):
                        self.analytics_service.refresh_daily_cache(source, affected_date)

            self.job_repository.mark_done(
                job,
                tweets_found=len(due_tweets),
                tweets_new=0,
                items_updated=items_updated,
                items_failed=items_failed,
            )
            logger.info(
                "Finished metric update job_id=%s total=%s updated=%s failed=%s "
                "affected_sources=%s",
                job.id,
                len(due_tweets),
                items_updated,
                items_failed,
                len(affected_source_ids),
            )
            self.db.commit()
            return job
        except Exception as exc:
            self.db.rollback()
            error_message = str(exc)
            job = self.job_repository.get(job.id) or job
            self.job_repository.mark_failed(job, error_message)
            logger.exception(
                "Metric update failed job_id=%s error_type=%s error=%s",
                job.id,
                exc.__class__.__name__,
                error_message,
            )
            self.job_repository.log(
                job_id=job.id,
                source_id=None,
                level="ERROR",
                message=error_message,
                error_type=exc.__class__.__name__,
                error_details=traceback.format_exc(),
            )
            self.db.commit()
            return job
