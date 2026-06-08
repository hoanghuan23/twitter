from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.account import DEFAULT_ACCOUNT_STATS, Account
from app.schemas.account import AccountCreate


class AccountRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list(self, active: bool | None, limit: int, offset: int) -> list[Account]:
        stmt = select(Account)
        if active is not None:
            stmt = stmt.where(Account.active == active)
        stmt = stmt.order_by(Account.user_id.desc()).limit(limit).offset(offset)
        return list(self.db.scalars(stmt))

    def get(self, user_id: int) -> Account | None:
        return self.db.get(Account, user_id)

    def create(self, payload: AccountCreate) -> Account:
        account = Account(
            username=payload.username,
            password=payload.password,
            email=payload.email,
            email_password=payload.email_password,
            user_agent=payload.user_agent,
            active=payload.active,
            locks=payload.locks or "{}",
            headers=payload.headers or "{}",
            cookies=payload.cookies,
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

