from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.repositories.job_repository import TwitterPipelineJobRepository
from app.schemas.job import CrawlDueResponse, JobRead
from app.services.twitter_crawler_service import TwitterCrawlerService
from app.services.twitter_source_service import TwitterSourceService
from app.utils.time import utc_now

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=list[JobRead])
def list_jobs(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[JobRead]:
    return TwitterPipelineJobRepository(db).list(limit, offset)


@router.post("/sources/{source_id}/crawl", response_model=JobRead)
async def crawl_source(
    source_id: int,
    limit: int | None = Query(default=None, ge=1, le=500),
    db: Session = Depends(get_db),
) -> JobRead:
    return await TwitterCrawlerService(db).crawl_source(source_id, limit=limit)


@router.post("/crawl-due", response_model=CrawlDueResponse)
async def crawl_due_sources(db: Session = Depends(get_db)) -> CrawlDueResponse:
    sources = TwitterSourceService(db).due_sources(settings.crawl_due_limit)
    job_ids: list[int] = []
    for index, source in enumerate(sources):
        job = await TwitterCrawlerService(db).crawl_source(source.id)
        job_ids.append(job.id)
        # TEMP: Keep crawling the selected due sources even if one source is deferred.
        # if job.status == "deferred":
        #     deferred_source = TwitterSourceService(db).repository.get(source.id)
        #     retry_at = deferred_source.next_scrape if deferred_source else None
        #     if retry_at is not None:
        #         TwitterSourceService(db).repository.defer_due_sources(utc_now(), retry_at)
        #         db.commit()
        #     break
        if settings.crawl_source_delay_seconds > 0 and index < len(sources) - 1:
            await asyncio.sleep(settings.crawl_source_delay_seconds)
    return CrawlDueResponse(jobs_started=len(job_ids), job_ids=job_ids)


@router.get("/{job_id}", response_model=JobRead)
def get_job(job_id: int, db: Session = Depends(get_db)) -> JobRead:
    job = TwitterPipelineJobRepository(db).get(job_id)
    if job is None:
        from fastapi import HTTPException, status

        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    return job
