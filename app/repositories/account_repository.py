from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.account import DEFAULT_ACCOUNT_STATS, DEFAULT_USER_AGENT, Account
from app.schemas.account import AccountCookieUpdate, AccountCreate


class AccountRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list(self, active: bool | None, limit: int, offset: int) -> list[Account]:
        stmt = select(Account)
        if active is not None:
            stmt = stmt.where(Account.active == active)
        stmt = stmt.order_by(Account.username.asc()).limit(limit).offset(offset)
        return list(self.db.scalars(stmt))

    def get(self, username: str) -> Account | None:
        return self.db.get(Account, username)

    def first_active(self) -> Account | None:
        stmt = (
            select(Account)
            .where(Account.active == True)  # noqa: E712
            .order_by(Account.username.asc())
            .limit(1)
        )
        return self.db.scalar(stmt)

    def create(self, payload: AccountCreate) -> Account:
        account = Account(
            username=payload.username,
            password=payload.password or "",
            email=payload.email or "",
            email_password=payload.email_password or "",
            user_agent=payload.user_agent or DEFAULT_USER_AGENT,
            active=payload.active,
            locks=payload.locks or "{}",
            headers=payload.headers or "{}",
            cookies=payload.cookies or "{}",
            proxy=payload.proxy,
            stats=DEFAULT_ACCOUNT_STATS,
            mfa_code=payload.mfa_code,
        )
        self.db.add(account)
        self.db.flush()
        return account

    def deactivate(self, account: Account) -> Account:
        account.active = False
        self.db.flush()
        return account

    def update_cookies(
        self,
        account: Account,
        payload: AccountCookieUpdate,
    ) -> Account:
        account.cookies = payload.cookies or "{}"
        self.db.flush()
        return account
