from __future__ import annotations

import asyncio

from app.services.scheduler_service import SchedulerService


def test_scheduler_loop_runs_source_and_metric_work() -> None:
    service = SchedulerService()
    calls: list[str] = []

    async def fake_crawl_due_sources() -> list[int]:
        calls.append("sources")
        return []

    async def fake_update_due_tweet_metrics() -> int:
        calls.append("metrics")
        service._stopping.set()
        return 0

    service.crawl_due_sources = fake_crawl_due_sources  # type: ignore[method-assign]
    service.update_due_tweet_metrics = fake_update_due_tweet_metrics  # type: ignore[method-assign]

    asyncio.run(service._run_loop())

    assert calls == ["sources", "metrics"]
