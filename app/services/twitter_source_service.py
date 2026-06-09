from __future__ import annotations

import logging
from datetime import datetime, timedelta
from urllib.parse import quote

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.crawler.twscrape_client import TwscrapeClient
from app.models.twitter_source import TwitterSource
from app.repositories.account_repository import AccountRepository
from app.repositories.source_repository import TwitterSourceRepository
from app.schemas.source import SourceCreate
from app.utils.time import utc_now

try:
    from twscrape.accounts_pool import NoAccountError
except ImportError:
    class NoAccountError(Exception):
        pass


logger = logging.getLogger(__name__)


class TwitterSourceService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = TwitterSourceRepository(db)
        self.account_repository = AccountRepository(db)
        self.twscrape_client = TwscrapeClient()

    def list_sources(
        self,
        active: bool | None,
        limit: int,
        offset: int,
    ) -> list[TwitterSource]:
        return self.repository.list(active=active, limit=limit, offset=offset)

    def get_source(self, source_id: int) -> TwitterSource:
        source = self.repository.get(source_id)
        if source is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Source not found")
        return source

    async def create_source(self, payload: SourceCreate) -> TwitterSource:
        account_username = self._resolve_account_username(payload.account_username)
        enriched_fields = await self._source_enriched_fields(payload)
        enriched_fields["account_username"] = account_username
        source = self.repository.create(payload, enriched_fields)
        self.db.commit()
        return source

    def _resolve_account_username(self, account_username: str | None) -> str:
        if account_username is not None:
            account = self.account_repository.get(account_username)
            if account is None:
                raise HTTPException(
                    status.HTTP_404_NOT_FOUND,
                    "Crawler account not found: "
                    f"{account_username}. Use an existing /accounts username, "
                    "or omit account_username to use the first active crawler account.",
                )
            return account.username

        account = self.account_repository.first_active()
        if account is None:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "No active twitter account available for source creation",
            )
        return account.username

    async def _source_enriched_fields(self, payload: SourceCreate) -> dict[str, object]:
        if payload.source_type == "account":
            return await self._account_enriched_fields(payload)

        source_name = (payload.source_name or "").strip()
        twitter_url = (payload.twitter_url or "").strip()
        if not source_name and not twitter_url:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"source_name is required for {payload.source_type} sources",
            )

        search_query = self._normalize_search_query(payload.source_type, source_name or twitter_url)
        if not search_query:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"source_name is required for {payload.source_type} sources",
            )
        if not twitter_url:
            twitter_url = self._search_url(search_query)

        return {
            "twitter_url": twitter_url,
            "source_name": search_query,
        }

    def _normalize_search_query(self, source_type: str, value: str) -> str:
        query = value.strip()
        if source_type == "hashtag":
            tag = query.lstrip("#").strip()
            return f"#{tag}" if tag else ""
        return query

    def _search_url(self, query: str) -> str:
        return f"https://x.com/search?q={quote(query, safe='')}&src=typed_query"

    async def _account_enriched_fields(self, payload: SourceCreate) -> dict[str, object]:
        username = (payload.source_name or "").strip().lstrip("@")
        if not username:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "source_name is required for account sources",
            )

        try:
            user = await self.twscrape_client.get_user_by_login(username)
        except NoAccountError as exc:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "No twscrape account available for username lookup. "
                f"Add or login an account, or wait for cooldown. Detail: {exc}",
            ) from exc
        except RuntimeError as exc:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                str(exc),
            ) from exc
        except Exception as exc:
            logger.exception("Twitter username lookup failed for %s", username)
            detail = str(exc) or exc.__class__.__name__
            if "No account available" in detail:
                raise HTTPException(
                    status.HTTP_503_SERVICE_UNAVAILABLE,
                    "No twscrape account available for username lookup. "
                    f"Add or login an account, or wait for cooldown. Detail: {detail}",
                ) from exc

            raise HTTPException(
                status.HTTP_502_BAD_GATEWAY,
                f"Twitter lookup failed for: {username}. {exc.__class__.__name__}: {detail}",
            ) from exc

        if user is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                f"Twitter user not found: {username}",
            )

        return {
            "twitter_id": str(user.id_str),
            "twitter_url": user.url,
            "source_name": user.username,
            "description": user.rawDescription,
            "followers_count": user.followersCount,
            "following_count": user.friendsCount,
            "tweet_count": user.statusesCount,
            "protected": user.protected,
            "verified": user.verified,
        }

    def deactivate_source(self, source_id: int) -> bool:
        source = self.get_source(source_id)
        self.repository.deactivate(source)
        self.db.commit()
        return True

    def due_sources(self, limit: int) -> list[TwitterSource]:
        return self.repository.due_sources(utc_now(), limit)

    def mark_scraped(self, source: TwitterSource) -> None:
        interval = self.scrape_interval_minutes(source)
        now = utc_now()
        source.last_scraped = now
        source.next_scrape = now + timedelta(minutes=interval)
        self.db.flush()

    def scrape_interval_minutes(self, source: TwitterSource) -> int:
        if source.schedule_override_minutes:
            return source.schedule_override_minutes
        if source.schedule_tier == 1:
            return 15
        if source.schedule_tier == 2:
            return 60
        if source.schedule_tier == 3:
            return 360
        return settings.default_scrape_interval_minutes
