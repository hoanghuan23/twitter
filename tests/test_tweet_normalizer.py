from __future__ import annotations

import json
from types import SimpleNamespace

from app.crawler.tweet_normalizer import normalize_tweet
from app.utils.time import utc_now


def test_normalize_quote_tweet_keeps_source_tweet_data_only() -> None:
    quoted_tweet = SimpleNamespace(
        id_str="quoted-1",
        rawContent="original content",
        user=SimpleNamespace(id="999", username="other"),
        media=SimpleNamespace(photos=[SimpleNamespace(url="https://pbs.twimg.com/original.jpg")]),
    )
    tweet = SimpleNamespace(
        id="tweet-1",
        url="https://x.com/example/status/tweet-1",
        date=utc_now(),
        user=SimpleNamespace(id="2455740283", username="example"),
        rawContent="my quote comment",
        conversationId="conversation-1",
        quotedTweet=quoted_tweet,
        isQuoteStatus=True,
        media=SimpleNamespace(photos=[]),
    )

    data = normalize_tweet(tweet)

    assert data["tweet_id"] == "tweet-1"
    assert data["content"] == "my quote comment"
    assert data["author_id"] == "2455740283"
    assert data["author_username"] == "example"
    assert data["is_quote_tweet"] is True
    assert data["quoted_tweet_id"] == "quoted-1"
    assert json.loads(data["media"]) == []


def test_normalize_media_stores_only_media_urls() -> None:
    tweet = SimpleNamespace(
        id="tweet-1",
        url="https://x.com/example/status/tweet-1",
        date=utc_now(),
        user=SimpleNamespace(id="2455740283", username="example"),
        rawContent="with media",
        conversationId="conversation-1",
        media=SimpleNamespace(
            photos=[SimpleNamespace(url="https://pbs.twimg.com/photo.jpg")],
            videos=[
                SimpleNamespace(
                    thumbnailUrl="https://pbs.twimg.com/thumb.jpg",
                    variants=[
                        SimpleNamespace(bitrate=256000, url="https://video.twimg.com/360.mp4"),
                        SimpleNamespace(bitrate=2176000, url="https://video.twimg.com/1080.mp4"),
                        SimpleNamespace(url="https://video.twimg.com/no-bitrate.mp4"),
                    ],
                )
            ],
            animated=[SimpleNamespace(videoUrl="https://video.twimg.com/animated.mp4")],
        ),
    )

    data = normalize_tweet(tweet)

    assert json.loads(data["media"]) == [
        "https://pbs.twimg.com/photo.jpg",
        "https://video.twimg.com/1080.mp4",
        "https://video.twimg.com/animated.mp4",
    ]
    assert "thumb" not in data["media"]
