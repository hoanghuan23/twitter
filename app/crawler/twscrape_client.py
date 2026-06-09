from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlparse

from app.config import settings
from app.models.twitter_source import TwitterSource
from app.utils.time import utc_now


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
        if source.source_type == "account":
            crawl_limit = limit if limit is not None else settings.account_crawl_limit
            async for tweet in self._crawl_account(source, crawl_limit):
                yield tweet
            return

        crawl_limit = limit if limit is not None else settings.default_crawl_limit
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

        cutoff = self._account_cutoff(source)
        first_timeline_tweet = True
        expected_author_id = str(user_id)
        async for tweet in self.api.user_tweets(user_id, limit=limit):
            in_reply_to_tweet_id = self._get(
                tweet,
                "inReplyToTweetId",
                "in_reply_to_tweet_id",
            )
            if not source.include_replies and in_reply_to_tweet_id:
                continue
            if not self._tweet_matches_author(tweet, expected_author_id):
                continue
            if self._is_repost(tweet):
                continue

            if cutoff is not None and self._tweet_is_older_than(tweet, cutoff):
                if first_timeline_tweet:
                    first_timeline_tweet = False
                    continue
                break

            first_timeline_tweet = False
            yield tweet

    def _tweet_matches_author(self, tweet: object, expected_author_id: str) -> bool:
        user = self._get(tweet, "user", "author")
        author_id = self._get(user, "id", "id_str", "user_id")
        return str(author_id) == expected_author_id

    def _is_repost(self, tweet: object) -> bool:
        if self._get(tweet, "retweetedTweet", "retweeted_tweet") is not None:
            return True
        content = self._get(tweet, "rawContent", "content", "text", "full_text")
        return isinstance(content, str) and content.lstrip().startswith("RT @")

    def _account_cutoff(self, source: TwitterSource) -> datetime | None:
        if source.created_at is None:
            return None
        max_days_old = source.max_days_old or 1
        return utc_now() - timedelta(days=max_days_old)

    def _tweet_is_older_than(self, tweet: object, cutoff: datetime) -> bool:
        tweet_date = self._get(tweet, "date", "created_at", "posted_at")
        if tweet_date is None:
            return False
        return self._to_naive_utc(tweet_date) < cutoff

    def _to_naive_utc(self, value: Any) -> datetime:
        if isinstance(value, str):
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value
            return value.astimezone(timezone.utc).replace(tzinfo=None)
        raise TypeError(f"Unsupported datetime value: {value!r}")

    def _get(self, value: object, *names: str) -> Any:
        for name in names:
            if isinstance(value, dict) and name in value:
                return value[name]
            if hasattr(value, name):
                return getattr(value, name)
        return None

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
