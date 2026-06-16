from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException, status

from app.models.account import Account
from app.repositories.account_repository import AccountRepository
from app.schemas.account import AccountRead


class AccountService:
    def __init__(self, repository: AccountRepository | None = None) -> None:
        self.repository = repository or AccountRepository()

    def list_accounts(
        self,
        active: bool | None,
        limit: int,
        offset: int,
    ) -> list[AccountRead]:
        accounts = self.repository.list(active, limit, offset)
        return [self.to_read(account) for account in accounts]

    def get_account(self, username: str) -> AccountRead:
        return self.to_read(self._get_account(username))

    def _get_account(self, username: str) -> Account:
        account = self.repository.get(username)
        if account is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Account not found")
        return account

    def to_read(self, account: Account) -> AccountRead:
        return AccountRead(
            username=account.username,
            email=account.email,
            user_agent=account.user_agent,
            active=account.active,
            proxy=account.proxy,
            error_msg=account.error_msg,
            last_used=self._parse_last_used(account.last_used),
            has_password=bool(account.password),
            has_email_password=bool(account.email_password),
            has_headers=bool(account.headers and account.headers != "{}"),
            has_cookies=bool(account.cookies and account.cookies != "{}"),
            has_mfa_code=bool(account.mfa_code),
        )

    def _parse_last_used(self, value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
