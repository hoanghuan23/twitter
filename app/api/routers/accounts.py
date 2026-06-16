from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from app.schemas.account import (
    AccountCookieUpdate,
    AccountCreate,
    AccountDeleteResponse,
    AccountRead,
)
from app.services.account_service import AccountService

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.get("", response_model=list[AccountRead])
def list_accounts(
    active: bool | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[AccountRead]:
    return AccountService().list_accounts(active, limit, offset)


@router.get("/{username}", response_model=AccountRead)
def get_account(username: str) -> AccountRead:
    return AccountService().get_account(username)


@router.post("", response_model=AccountRead, status_code=201)
async def create_account(payload: AccountCreate) -> AccountRead:
    raise HTTPException(
        status.HTTP_405_METHOD_NOT_ALLOWED,
        "Accounts are managed by twscrape accounts.db; use twscrape tooling to add accounts.",
    )


@router.patch("/{username}", response_model=AccountRead)
def update_account_cookies(
    username: str,
    payload: AccountCookieUpdate,
) -> AccountRead:
    raise HTTPException(
        status.HTTP_405_METHOD_NOT_ALLOWED,
        "Accounts are managed by twscrape accounts.db; use twscrape tooling to update accounts.",
    )


@router.delete("/{username}", response_model=AccountDeleteResponse)
def delete_account(
    username: str,
) -> AccountDeleteResponse:
    raise HTTPException(
        status.HTTP_405_METHOD_NOT_ALLOWED,
        "Accounts are managed by twscrape accounts.db; use twscrape tooling to disable accounts.",
    )
