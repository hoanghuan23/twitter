from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.account import AccountCreate, AccountDeleteResponse, AccountRead
from app.services.account_service import AccountService

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.get("", response_model=list[AccountRead])
def list_accounts(
    active: bool | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[AccountRead]:
    return AccountService(db).list_accounts(active, limit, offset)


@router.get("/{username}", response_model=AccountRead)
def get_account(username: str, db: Session = Depends(get_db)) -> AccountRead:
    return AccountService(db).get_account(username)


@router.post("", response_model=AccountRead, status_code=201)
async def create_account(payload: AccountCreate, db: Session = Depends(get_db)) -> AccountRead:
    return await AccountService(db).create_account(payload)


@router.delete("/{username}", response_model=AccountDeleteResponse)
def delete_account(
    username: str,
    db: Session = Depends(get_db),
) -> AccountDeleteResponse:
    deleted = AccountService(db).deactivate_account(username)
    return AccountDeleteResponse(deleted=deleted)

