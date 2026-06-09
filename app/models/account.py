from __future__ import annotations

from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


DEFAULT_ACCOUNT_STATS = "{}"
DEFAULT_USER_AGENT = "Mozilla/5.0"


class Account(Base):
    __tablename__ = "accounts"

    username: Mapped[str] = mapped_column(Text, primary_key=True)
    password: Mapped[str] = mapped_column(Text, nullable=False, default="")
    email: Mapped[str] = mapped_column(Text, nullable=False, default="")
    email_password: Mapped[str] = mapped_column(Text, nullable=False, default="")
    user_agent: Mapped[str] = mapped_column(Text, nullable=False, default=DEFAULT_USER_AGENT)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    locks: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    headers: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    cookies: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    proxy: Mapped[str | None] = mapped_column(Text)
    error_msg: Mapped[str | None] = mapped_column(Text)
    stats: Mapped[str] = mapped_column(
        Text,
        default=DEFAULT_ACCOUNT_STATS,
        server_default=DEFAULT_ACCOUNT_STATS,
        nullable=False,
    )
    last_used: Mapped[str | None] = mapped_column(Text)
    _tx: Mapped[str | None] = mapped_column(Text)
    mfa_code: Mapped[str | None] = mapped_column(Text)

    sources = relationship("TwitterSource", back_populates="account")
