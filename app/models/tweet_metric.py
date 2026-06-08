from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TweetMetric(Base):
    __tablename__ = "tweet_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tweet_id: Mapped[int] = mapped_column(ForeignKey("tweets.id"), nullable=False)
    job_id: Mapped[int | None] = mapped_column(ForeignKey("twitter_pipeline_jobs.id"))
    like_count: Mapped[int | None] = mapped_column(Integer, default=0)
    reply_count: Mapped[int | None] = mapped_column(Integer, default=0)
    retweet_count: Mapped[int | None] = mapped_column(Integer, default=0)
    quote_count: Mapped[int | None] = mapped_column(Integer, default=0)
    bookmark_count: Mapped[int | None] = mapped_column(Integer, default=0)
    recorded_at: Mapped[datetime | None] = mapped_column(DateTime)

    tweet = relationship("Tweet", back_populates="metrics")
    job = relationship("TwitterPipelineJob", back_populates="metrics")

