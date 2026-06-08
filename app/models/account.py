from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


DEFAULT_ACCOUNT_STATS = '{"UserByScreenName": 1}'


class Account(Base):
    __tablename__ = "accounts"

    user_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    password: Mapped[str | None] = mapped_column(String(255))
    email: Mapped[str | None] = mapped_column(String(255))
    email_password: Mapped[str | None] = mapped_column(String(255))
    user_agent: Mapped[str | None] = mapped_column(String(512))
    active: Mapped[bool | None] = mapped_column(Boolean, default=True)
    locks: Mapped[str | None] = mapped_column(Text)
    headers: Mapped[str | None] = mapped_column(Text)
    cookies: Mapped[str | None] = mapped_column(Text)
    proxy: Mapped[str | None] = mapped_column(String(255))
    error_msg: Mapped[str | None] = mapped_column(Text)
    stats: Mapped[str | None] = mapped_column(
        Text,
        default=DEFAULT_ACCOUNT_STATS,
        server_default=DEFAULT_ACCOUNT_STATS,
    )
    last_used: Mapped[datetime | None] = mapped_column(DateTime)
    _tx: Mapped[str | None] = mapped_column(Text)
    mfa_code: Mapped[str | None] = mapped_column(String(50))

    sources = relationship("TwitterSource", back_populates="account")
