from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AccountRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    username: str
    email: str | None
    user_agent: str | None
    active: bool | None
    proxy: str | None
    error_msg: str | None
    last_used: datetime | None
    has_password: bool
    has_email_password: bool
    has_headers: bool
    has_cookies: bool
    has_mfa_code: bool
