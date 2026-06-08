from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TwitterPipelineJob(Base):
    __tablename__ = "twitter_pipeline_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_type: Mapped[str] = mapped_column(String(20), nullable=False, default="scrape_timeline")
    source_id: Mapped[int | None] = mapped_column(ForeignKey("twitter_sources.id"))
    session_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.user_id"))
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="pending")
    tweets_found: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tweets_new: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    items_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    items_updated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    items_failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rate_limit_hits: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)

    source = relationship("TwitterSource", back_populates="jobs")
    metrics = relationship("TweetMetric", back_populates="job")
    logs = relationship("TwitterPipelineLog", back_populates="job")

