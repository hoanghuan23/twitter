from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TwitterAnalyticsCache(Base):
    __tablename__ = "twitter_analytics_cache"
    __table_args__ = (
        UniqueConstraint("source_id", "date"),
        Index("idx_tw_analytics_source_date", "source_id", "date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("twitter_sources.id"), nullable=False)
    date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    total_tweets: Mapped[int | None] = mapped_column(Integer, default=0)
    total_likes: Mapped[int | None] = mapped_column(Integer, default=0)
    total_replies: Mapped[int | None] = mapped_column(Integer, default=0)
    total_retweets: Mapped[int | None] = mapped_column(Integer, default=0)
    total_quotes: Mapped[int | None] = mapped_column(Integer, default=0)
    avg_likes_per_tweet: Mapped[float | None] = mapped_column(Float)
    top_tweet_id: Mapped[str | None] = mapped_column(String(50))
    growth_rate: Mapped[float | None] = mapped_column(Float)
    cached_at: Mapped[datetime | None] = mapped_column(DateTime)

    source = relationship("TwitterSource", back_populates="analytics_cache")
