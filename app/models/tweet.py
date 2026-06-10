from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Tweet(Base):
    __tablename__ = "tweets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("twitter_sources.id"), nullable=False)
    tweet_id: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    tweet_url: Mapped[str] = mapped_column(String(500), nullable=False)
    content: Mapped[str | None] = mapped_column(Text)
    conversation_id: Mapped[str | None] = mapped_column(String(50))
    quoted_tweet_id: Mapped[str | None] = mapped_column(String(50))
    is_quote_tweet: Mapped[bool | None] = mapped_column(Boolean, default=False)
    in_reply_to_tweet_id: Mapped[str | None] = mapped_column(String(50))
    is_reply: Mapped[bool | None] = mapped_column(Boolean, default=False)
    lang: Mapped[str | None] = mapped_column(String(10))
    author_id: Mapped[str | None] = mapped_column(String(50))
    author_username: Mapped[str | None] = mapped_column(String(100))
    mentions: Mapped[str | None] = mapped_column(Text)
    urls: Mapped[str | None] = mapped_column(Text)
    posted_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime | None] = mapped_column(DateTime)
    is_tracked: Mapped[bool | None] = mapped_column(Boolean, default=True)
    tracking_until: Mapped[datetime | None] = mapped_column(DateTime)
    is_deleted: Mapped[bool | None] = mapped_column(Boolean, default=False)
    last_metric_update: Mapped[datetime | None] = mapped_column(DateTime)
    metric_tier: Mapped[str] = mapped_column(String(20), nullable=False, default="bootstrap")
    next_metric_update: Mapped[datetime | None] = mapped_column(DateTime)
    weighted_engagement: Mapped[int | None] = mapped_column(Integer)
    last_engagement_velocity: Mapped[float | None] = mapped_column(Float)
    engagement_rate: Mapped[float | None] = mapped_column(Float)
    cold_check_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    metric_scan_miss_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    view_count: Mapped[int | None] = mapped_column(Integer)
    possibly_sensitive: Mapped[bool | None] = mapped_column(Boolean, default=False)
    hashtags: Mapped[str | None] = mapped_column(Text)
    media: Mapped[str | None] = mapped_column(Text)

    source = relationship("TwitterSource", back_populates="tweets")
    metrics = relationship("TweetMetric", back_populates="tweet")
