from __future__ import annotations

import traceback

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.crawler.tweet_normalizer import normalize_tweet
from app.crawler.twscrape_client import TwscrapeClient
from app.models.pipeline_job import TwitterPipelineJob
from app.repositories.job_repository import TwitterPipelineJobRepository
from app.repositories.metric_repository import TweetMetricRepository
from app.repositories.post_repository import TwitterPostRepository
from app.repositories.source_repository import TwitterSourceRepository
from app.services.twitter_source_service import TwitterSourceService


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

            for raw_tweet in raw_tweets:
                data = normalize_tweet(raw_tweet)
                metric_data = data.pop("metrics", {})
                tweet, is_new = self.post_repository.upsert(source.id, data)
                self.metric_repository.create_snapshot(tweet.id, job.id, metric_data)
                tweets_new += 1 if is_new else 0
                items_updated += 0 if is_new else 1

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
