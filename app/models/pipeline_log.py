from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TwitterPipelineLog(Base):
    __tablename__ = "twitter_pipeline_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[int | None] = mapped_column(ForeignKey("twitter_pipeline_jobs.id"))
    source_id: Mapped[int | None] = mapped_column(ForeignKey("twitter_sources.id"))
    log_level: Mapped[str | None] = mapped_column(String(20))
    message: Mapped[str] = mapped_column(Text, nullable=False)
    error_type: Mapped[str | None] = mapped_column(String(100))
    error_details: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime | None] = mapped_column(DateTime)

    job = relationship("TwitterPipelineJob", back_populates="logs")
    source = relationship("TwitterSource", back_populates="logs")

