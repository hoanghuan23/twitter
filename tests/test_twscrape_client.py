from __future__ import annotations

import asyncio
from datetime import timedelta
from types import SimpleNamespace

from app.crawler.twscrape_client import TwscrapeClient
from app.models.twitter_source import TwitterSource
from app.utils.time import utc_now


class FakeApi:
    def __init__(self, tweets: list[SimpleNamespace]) -> None:
        self.tweets = tweets
        self.user_tweets_calls: list[tuple[int, int]] = []
        self.seen_tweet_ids: list[str] = []

    async def user_tweets(self, user_id: int, limit: int):
        self.user_tweets_calls.append((user_id, limit))
        for tweet in self.tweets:
            self.seen_tweet_ids.append(tweet.id)
            yield tweet


class NoLookupTwscrapeClient(TwscrapeClient):
    async def get_user_by_login(self, username: str):
        raise AssertionError("username lookup should not be used when twitter_id is numeric")


async def _collect_tweets(client: TwscrapeClient, source: TwitterSource, limit: int = 50):
    return [tweet async for tweet in client._crawl_account(source, limit)]


async def _collect_source(client: TwscrapeClient, source: TwitterSource):
    return [tweet async for tweet in client.crawl_source(source)]


def _tweet(
    tweet_id: str,
    date,
    user_id: str = "2455740283",
    **overrides,
) -> SimpleNamespace:
    data = {
        "id": tweet_id,
        "date": date,
        "user": SimpleNamespace(id=user_id, username=f"user-{user_id}"),
        "rawContent": tweet_id,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def test_crawl_account_uses_numeric_twitter_id_and_stops_after_24h() -> None:
    created_at = utc_now()
    api = FakeApi(
        [
            _tweet("quote-original-old", created_at - timedelta(days=2), user_id="111"),
            _tweet(
                "repost",
                created_at - timedelta(hours=1),
                rawContent="RT @other: ignored",
                retweetedTweet=SimpleNamespace(id="source-tweet"),
            ),
            _tweet("pinned-old", created_at - timedelta(days=2)),
            _tweet("recent", created_at - timedelta(hours=1)),
            _tweet(
                "quote",
                created_at - timedelta(hours=1),
                quotedTweet=SimpleNamespace(id="quoted-original"),
            ),
            _tweet("old", created_at - timedelta(days=2)),
            _tweet("after-stop", created_at - timedelta(minutes=5)),
        ]
    )
    client = NoLookupTwscrapeClient()
    client._api = api
    source = TwitterSource(
        source_type="account",
        twitter_id="2455740283",
        twitter_url="https://x.com/example",
        source_name="example",
        include_replies=False,
        max_days_old=1,
        created_at=created_at,
    )

    tweets = asyncio.run(_collect_tweets(client, source, limit=25))

    assert api.user_tweets_calls == [(2455740283, 25)]
    assert [tweet.id for tweet in tweets] == ["recent", "quote"]
    assert api.seen_tweet_ids == [
        "quote-original-old",
        "repost",
        "pinned-old",
        "recent",
        "quote",
        "old",
    ]


def test_crawl_account_skips_replies_unless_enabled() -> None:
    created_at = utc_now()
    reply = SimpleNamespace(
        id="reply",
        date=created_at - timedelta(hours=1),
        user=SimpleNamespace(id="2455740283", username="example"),
        inReplyToTweetId="parent",
    )
    original = SimpleNamespace(
        id="original",
        date=created_at - timedelta(hours=1),
        user=SimpleNamespace(id="2455740283", username="example"),
    )

    skip_api = FakeApi([reply, original])
    skip_client = NoLookupTwscrapeClient()
    skip_client._api = skip_api
    skip_source = TwitterSource(
        source_type="account",
        twitter_id="2455740283",
        twitter_url="https://x.com/example",
        include_replies=False,
        max_days_old=1,
        created_at=created_at,
    )

    include_api = FakeApi([reply, original])
    include_client = NoLookupTwscrapeClient()
    include_client._api = include_api
    include_source = TwitterSource(
        source_type="account",
        twitter_id="2455740283",
        twitter_url="https://x.com/example",
        include_replies=True,
        max_days_old=1,
        created_at=created_at,
    )

    skipped = asyncio.run(_collect_tweets(skip_client, skip_source))
    included = asyncio.run(_collect_tweets(include_client, include_source))

    assert [tweet.id for tweet in skipped] == ["original"]
    assert [tweet.id for tweet in included] == ["reply", "original"]


def test_crawl_source_uses_account_crawl_limit_when_limit_is_blank() -> None:
    api = FakeApi([])
    client = NoLookupTwscrapeClient()
    client._api = api
    source = TwitterSource(
        source_type="account",
        twitter_id="2455740283",
        twitter_url="https://x.com/example",
        include_replies=False,
        max_days_old=1,
        created_at=utc_now(),
    )

    tweets = asyncio.run(_collect_source(client, source))

    assert tweets == []
    assert api.user_tweets_calls == [(2455740283, 500)]
