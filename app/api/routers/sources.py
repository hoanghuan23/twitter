from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.source import DeleteResponse, SourceCreate, SourceRead
from app.services.twitter_source_service import TwitterSourceService

router = APIRouter(prefix="/sources", tags=["sources"])


@router.get("", response_model=list[SourceRead])
def list_sources(
    active: bool | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[SourceRead]:
    return TwitterSourceService(db).list_sources(active, limit, offset)


@router.get("/{source_id}", response_model=SourceRead)
def get_source(source_id: int, db: Session = Depends(get_db)) -> SourceRead:
    return TwitterSourceService(db).get_source(source_id)


@router.post("", response_model=SourceRead, status_code=201)
def create_source(payload: SourceCreate, db: Session = Depends(get_db)) -> SourceRead:
    return TwitterSourceService(db).create_source(payload)


@router.delete("/{source_id}", response_model=DeleteResponse)
def delete_source(source_id: int, db: Session = Depends(get_db)) -> DeleteResponse:
    deleted = TwitterSourceService(db).deactivate_source(source_id)
    return DeleteResponse(deleted=deleted)

