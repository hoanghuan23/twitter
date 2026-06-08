from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TwitterSource(Base):
    __tablename__ = "twitter_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("accounts.user_id"), nullable=False)
    source_type: Mapped[str] = mapped_column(String(10), nullable=False)
    twitter_id: Mapped[str | None] = mapped_column(String(50))
    twitter_url: Mapped[str] = mapped_column(String(255), nullable=False)
    source_name: Mapped[str | None] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    followers_count: Mapped[int | None] = mapped_column(Integer)
    following_count: Mapped[int | None] = mapped_column(Integer)
    tweet_count: Mapped[int | None] = mapped_column(Integer)
    is_active: Mapped[bool | None] = mapped_column(Boolean, default=True)
    include_replies: Mapped[bool | None] = mapped_column(Boolean, default=False)
    max_days_old: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_scraped: Mapped[datetime | None] = mapped_column(DateTime)
    next_scrape: Mapped[datetime | None] = mapped_column(DateTime)
    schedule_tier: Mapped[int | None] = mapped_column(Integer)
    schedule_override_minutes: Mapped[int | None] = mapped_column(Integer)
    protected: Mapped[bool | None] = mapped_column(Boolean, default=False)
    verified: Mapped[bool | None] = mapped_column(Boolean, default=False)

    account = relationship("Account", back_populates="sources")
    tweets = relationship("Tweet", back_populates="source")
    jobs = relationship("TwitterPipelineJob", back_populates="source")
    logs = relationship("TwitterPipelineLog", back_populates="source")

