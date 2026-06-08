from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.account import Account
from app.repositories.account_repository import AccountRepository
from app.schemas.account import AccountCreate, AccountRead


class AccountService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = AccountRepository(db)

    def list_accounts(
        self,
        active: bool | None,
        limit: int,
        offset: int,
    ) -> list[AccountRead]:
        accounts = self.repository.list(active, limit, offset)
        return [self.to_read(account) for account in accounts]

    def get_account(self, user_id: int) -> AccountRead:
        return self.to_read(self._get_account(user_id))

    def create_account(self, payload: AccountCreate) -> AccountRead:
        try:
            account = self.repository.create(payload)
            self.db.commit()
            return self.to_read(account)
        except IntegrityError as exc:
            self.db.rollback()
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "Account username or user_id already exists",
            ) from exc

    def deactivate_account(self, user_id: int) -> bool:
        account = self._get_account(user_id)
        self.repository.deactivate(account)
        self.db.commit()
        return True

    def _get_account(self, user_id: int) -> Account:
        account = self.repository.get(user_id)
        if account is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Account not found")
        return account

    def to_read(self, account: Account) -> AccountRead:
        return AccountRead(
            user_id=account.user_id,
            username=account.username,
            email=account.email,
            user_agent=account.user_agent,
            active=account.active,
            proxy=account.proxy,
            error_msg=account.error_msg,
            last_used=account.last_used,
            has_password=bool(account.password),
            has_email_password=bool(account.email_password),
            has_headers=bool(account.headers and account.headers != "{}"),
            has_cookies=bool(account.cookies and account.cookies != "{}"),
            has_mfa_code=bool(account.mfa_code),
        )

