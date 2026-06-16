from __future__ import annotations

from fastapi import APIRouter, Query

from app.schemas.account import AccountRead
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
