from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.tweet_metric import TweetMetric
from app.utils.time import utc_now


class TweetMetricRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_snapshot(
        self,
        tweet_id: int,
        job_id: int | None,
        metrics: dict[str, Any],
    ) -> TweetMetric:
        metric = TweetMetric(
            tweet_id=tweet_id,
            job_id=job_id,
            like_count=metrics.get("like_count", 0),
            reply_count=metrics.get("reply_count", 0),
            retweet_count=metrics.get("retweet_count", 0),
            quote_count=metrics.get("quote_count", 0),
            recorded_at=utc_now(),
        )
        self.db.add(metric)
        self.db.flush()
        return metric

    def latest_by_tweet_ids(self, tweet_ids: list[int]) -> dict[int, TweetMetric]:
        if not tweet_ids:
            return {}
        stmt = (
            select(TweetMetric)
            .where(TweetMetric.tweet_id.in_(tweet_ids))
            .order_by(TweetMetric.tweet_id.asc(), TweetMetric.recorded_at.desc())
        )
        latest: dict[int, TweetMetric] = {}
        for metric in self.db.scalars(stmt):
            latest.setdefault(metric.tweet_id, metric)
        return latest

    def latest_for_tweet(self, tweet_id: int) -> TweetMetric | None:
        stmt = (
            select(TweetMetric)
            .where(TweetMetric.tweet_id == tweet_id)
            .order_by(TweetMetric.recorded_at.desc(), TweetMetric.id.desc())
            .limit(1)
        )
        return self.db.scalar(stmt)
