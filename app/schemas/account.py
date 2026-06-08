from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


JsonText = dict[str, Any] | list[Any] | str | None


def to_json_text(value: JsonText) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=True)


class AccountCreate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "user_id": 0,
                "username": "string",
                "password": "string",
                "email": "string",
                "email_password": "string",
                "user_agent": "string",
                "active": True,
                "locks": {},
                "headers": {},
                "cookies": {},
                "proxy": "string",
                "mfa_code": "string",
            }
        }
    )

    user_id: int | None = None
    username: str = Field(min_length=1, max_length=255)
    password: str | None = Field(default=None, max_length=255)
    email: str | None = Field(default=None, max_length=255)
    email_password: str | None = Field(default=None, max_length=255)
    user_agent: str | None = Field(default=None, max_length=512)
    active: bool = True
    locks: JsonText = None
    headers: JsonText = None
    cookies: JsonText = None
    proxy: str | None = Field(default=None, max_length=255)
    mfa_code: str | None = Field(default=None, max_length=50)

    @field_validator("locks", "headers", "cookies", mode="after")
    @classmethod
    def serialize_json_text(cls, value: JsonText) -> str | None:
        return to_json_text(value)


class AccountRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
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


class AccountDeleteResponse(BaseModel):
    deleted: bool
