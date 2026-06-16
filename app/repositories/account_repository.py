from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from app.config import settings
from app.models.account import Account


class AccountRepository:
    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = db_path or os.getenv("TWSCRAPE_DB_PATH", settings.twscrape_db_path)

    def list(self, active: bool | None, limit: int, offset: int) -> list[Account]:
        if not Path(self.db_path).exists():
            return []

        query = "SELECT * FROM accounts"
        params: list[object] = []
        if active is not None:
            query += " WHERE active = ?"
            params.append(1 if active else 0)
        query += " ORDER BY username ASC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [self._to_account(row) for row in rows]

    def get(self, username: str) -> Account | None:
        if not Path(self.db_path).exists():
            return None

        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM accounts WHERE username = ? COLLATE NOCASE LIMIT 1",
                (username,),
            ).fetchone()
        return self._to_account(row) if row is not None else None

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _to_account(self, row: sqlite3.Row) -> Account:
        data = dict(row)
        return Account(
            username=data["username"],
            password=data.get("password") or "",
            email=data.get("email") or "",
            email_password=data.get("email_password") or "",
            user_agent=data.get("user_agent") or "",
            active=bool(data.get("active")),
            locks=data.get("locks") or "{}",
            headers=data.get("headers") or "{}",
            cookies=data.get("cookies") or "{}",
            proxy=data.get("proxy"),
            error_msg=data.get("error_msg"),
            stats=data.get("stats") or "{}",
            last_used=data.get("last_used"),
            _tx=data.get("_tx"),
            mfa_code=data.get("mfa_code"),
        )
