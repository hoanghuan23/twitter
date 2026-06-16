from __future__ import annotations

from dataclasses import dataclass


DEFAULT_ACCOUNT_STATS = "{}"
DEFAULT_USER_AGENT = "Mozilla/5.0"


@dataclass(frozen=True)
class Account:
    username: str
    password: str = ""
    email: str = ""
    email_password: str = ""
    user_agent: str = DEFAULT_USER_AGENT
    active: bool = False
    locks: str = "{}"
    headers: str = "{}"
    cookies: str = "{}"
    proxy: str | None = None
    error_msg: str | None = None
    stats: str = DEFAULT_ACCOUNT_STATS
    last_used: str | None = None
    _tx: str | None = None
    mfa_code: str | None = None
