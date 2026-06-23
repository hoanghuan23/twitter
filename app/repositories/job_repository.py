from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.pipeline_job import TwitterPipelineJob
from app.models.pipeline_log import TwitterPipelineLog
from app.utils.time import utc_now


class TwitterPipelineJobRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_running(
        self,
        source_id: int | None,
        session_username: str | None,
        job_type: str = "scrape_timeline",
    ) -> TwitterPipelineJob:
        job = TwitterPipelineJob(
            job_type=job_type,
            source_id=source_id,
            session_username=session_username,
            status="running",
            started_at=utc_now(),
        )
        self.db.add(job)
        self.db.flush()
        return job

    def get(self, job_id: int) -> TwitterPipelineJob | None:
        return self.db.get(TwitterPipelineJob, job_id)

    def list(self, limit: int, offset: int) -> list[TwitterPipelineJob]:
        stmt = (
            select(TwitterPipelineJob)
            .order_by(TwitterPipelineJob.started_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(self.db.scalars(stmt))

    def mark_done(
        self,
        job: TwitterPipelineJob,
        tweets_found: int,
        tweets_new: int,
        items_updated: int,
        items_failed: int = 0,
    ) -> TwitterPipelineJob:
        job.status = "done"
        job.tweets_found = tweets_found
        job.tweets_new = tweets_new
        job.items_total = tweets_found
        job.items_updated = items_updated
        job.items_failed = items_failed
        job.finished_at = utc_now()
        self.db.flush()
        return job

    def mark_failed(self, job: TwitterPipelineJob, message: str) -> TwitterPipelineJob:
        job.status = "failed"
        job.error_message = message
        job.finished_at = utc_now()
        self.db.flush()
        return job

    def mark_deferred(self, job: TwitterPipelineJob, message: str) -> TwitterPipelineJob:
        job.status = "deferred"
        job.error_message = message
        job.finished_at = utc_now()
        self.db.flush()
        return job

    def log(
        self,
        job_id: int | None,
        source_id: int | None,
        level: str,
        message: str,
        error_type: str | None = None,
        error_details: str | None = None,
    ) -> TwitterPipelineLog:
        log = TwitterPipelineLog(
            job_id=job_id,
            source_id=source_id,
            log_level=level,
            message=message,
            error_type=error_type,
            error_details=error_details,
            created_at=utc_now(),
        )
        self.db.add(log)
        self.db.flush()
        return log
