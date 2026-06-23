from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.config import settings
from app.utils.time import utc_now


@dataclass(frozen=True)
class QueueAvailability:
    available: bool
    retry_at: datetime | None = None


class AccountQuotaService:
    """Reads twscrape's account locks without taking ownership of its database."""

    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = db_path or settings.twscrape_db_path

    def availability(self, queue: str, now: datetime | None = None) -> QueueAvailability:
        now = now or utc_now()
        if not Path(self.db_path).exists():
            # Do not block callers that use an injected/fake twscrape client. A real
            # client will still raise NoAccountError, which is deferred below.
            return QueueAvailability(available=True)

        try:
            with sqlite3.connect(self.db_path) as connection:
                rows = connection.execute(
                    "SELECT locks FROM accounts WHERE active = 1"
                ).fetchall()
        except sqlite3.Error:
            return QueueAvailability(available=True)

        if not rows:
            return QueueAvailability(available=False, retry_at=self._fallback_retry_at(now))

        unlock_times: list[datetime] = []
        has_invalid_lock_data = False
        for (locks_raw,) in rows:
            valid, unlock_at = self._unlock_at(locks_raw, queue)
            if not valid:
                has_invalid_lock_data = True
                continue
            if unlock_at is None or unlock_at <= now:
                return QueueAvailability(available=True)
            unlock_times.append(unlock_at)

        if has_invalid_lock_data:
            return QueueAvailability(available=False, retry_at=self._fallback_retry_at(now))

        return QueueAvailability(
            available=False,
            retry_at=min(unlock_times) + timedelta(
                seconds=settings.no_account_unlock_buffer_seconds
            ),
        )

    def retry_at(self, queue: str, now: datetime | None = None) -> datetime:
        now = now or utc_now()
        availability = self.availability(queue, now)
        return availability.retry_at or self._fallback_retry_at(now)

    def _fallback_retry_at(self, now: datetime) -> datetime:
        return now + timedelta(minutes=settings.no_account_retry_fallback_minutes)

    def _unlock_at(self, locks_raw: object, queue: str) -> tuple[bool, datetime | None]:
        try:
            locks = json.loads(locks_raw or "{}")
            if not isinstance(locks, dict):
                return False, None
            value = locks.get(queue)
            if not isinstance(value, str):
                return True, None
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is not None:
                return True, parsed.astimezone(timezone.utc).replace(tzinfo=None)
            return True, parsed
        except (TypeError, ValueError, json.JSONDecodeError):
            return False, None
