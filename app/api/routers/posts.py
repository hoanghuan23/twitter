from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.post import PostRead
from app.services.twitter_post_service import TwitterPostService

router = APIRouter(prefix="/posts", tags=["posts"])


@router.get("", response_model=list[PostRead])
def list_posts(
    source_id: int | None = Query(default=None),
    author_username: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[PostRead]:
    return TwitterPostService(db).list_posts(source_id, author_username, limit, offset)


@router.get("/latest", response_model=list[PostRead])
def latest_posts(
    limit: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[PostRead]:
    return TwitterPostService(db).latest_posts(limit)


@router.get("/{post_id}", response_model=PostRead)
def get_post(post_id: int, db: Session = Depends(get_db)) -> PostRead:
    return TwitterPostService(db).get_post(post_id)

