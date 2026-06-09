from __future__ import annotations

from collections.abc import AsyncIterator
from urllib.parse import urlparse

from app.config import settings
from app.models.twitter_source import TwitterSource


class TwscrapeClient:
    def __init__(self) -> None:
        self._api = None

    @property
    def api(self):
        if self._api is None:
            try:
                from twscrape import API
            except ImportError as exc:
                raise RuntimeError(
                    "twscrape is not installed. Install dependencies from requirements.txt."
                ) from exc
            self._api = API(settings.twscrape_db_path, raise_when_no_account=True)
        return self._api

    async def crawl_source(
        self,
        source: TwitterSource,
        limit: int | None = None,
    ) -> AsyncIterator[object]:
        crawl_limit = limit or settings.default_crawl_limit
        if source.source_type == "account":
            async for tweet in self._crawl_account(source, crawl_limit):
                yield tweet
            return

        query = self._search_query(source)
        async for tweet in self.api.search(query, limit=crawl_limit):
            yield tweet

    async def _crawl_account(
        self,
        source: TwitterSource,
        limit: int,
    ) -> AsyncIterator[object]:
        twitter_id = source.twitter_id
        if twitter_id and twitter_id.isdigit():
            user_id = int(twitter_id)
        else:
            username = twitter_id or source.source_name or self._username_from_url(
                source.twitter_url
            )
            user = await self.get_user_by_login(username)
            user_id = int(user.id)

        async for tweet in self.api.user_tweets(user_id, limit=limit):
            if source.include_replies or not getattr(tweet, "inReplyToTweetId", None):
                yield tweet

    def _search_query(self, source: TwitterSource) -> str:
        if source.source_type == "hashtag":
            value = source.source_name or source.twitter_id or source.twitter_url
            return value if value.startswith("#") else f"#{value}"
        return source.source_name or source.twitter_id or source.twitter_url

    def _username_from_url(self, twitter_url: str) -> str:
        parsed = urlparse(twitter_url)
        path = parsed.path.strip("/")
        if not path:
            return twitter_url.strip("@")
        return path.split("/")[0].strip("@")

    async def get_user_by_login(self, username: str):
        return await self.api.user_by_login(username)
