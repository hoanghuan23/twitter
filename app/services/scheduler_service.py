from __future__ import annotations

import asyncio
import logging

from app.config import settings
from app.database import SessionLocal
from app.services.twitter_crawler_service import TwitterCrawlerService
from app.services.twitter_source_service import TwitterSourceService

logger = logging.getLogger(__name__)


class SchedulerService:
    def __init__(self) -> None:
        self._task: asyncio.Task | None = None
        self._stopping = asyncio.Event()

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        self._stopping.set()
        if self._task is not None:
            await self._task

    async def _run_loop(self) -> None:
        while not self._stopping.is_set():
            await self.crawl_due_sources()
            try:
                await asyncio.wait_for(
                    self._stopping.wait(),
                    timeout=settings.scheduler_interval_seconds,
                )
            except TimeoutError:
                continue

    async def crawl_due_sources(self) -> list[int]:
        job_ids: list[int] = []
        with SessionLocal() as db:
            source_service = TwitterSourceService(db)
            sources = source_service.due_sources(settings.crawl_due_limit)
            for source in sources:
                crawler_service = TwitterCrawlerService(db)
                job = await crawler_service.crawl_source(source.id)
                job_ids.append(job.id)
                if job.status == "failed":
                    logger.warning("Crawl job %s failed: %s", job.id, job.error_message)
        return job_ids


scheduler_service = SchedulerService()

