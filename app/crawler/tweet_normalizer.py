from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from app.utils.time import utc_now


def _get(value: Any, *names: str, default: Any = None) -> Any:
    for name in names:
        if isinstance(value, dict) and name in value:
            return value[name]
        if hasattr(value, name):
            return getattr(value, name)
    return default


def _to_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value.replace(tzinfo=None) if value.tzinfo else value
    if isinstance(value, str):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.replace(tzinfo=None) if parsed.tzinfo else parsed
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _json(value: Any) -> str | None:
    if value is None:
        return None
    try:
        return json.dumps(value, default=str, ensure_ascii=True)
    except TypeError:
        return json.dumps(str(value), ensure_ascii=True)


def _iter_items(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return []


def _best_video_url(video: Any) -> str | None:
    variants = _iter_items(_get(video, "variants", default=[]))
    if not variants:
        return None

    bitrate_variants = [
        variant
        for variant in variants
        if _get(variant, "url") and _get(variant, "bitrate") is not None
    ]
    if bitrate_variants:
        best = max(
            bitrate_variants,
            key=lambda variant: int(_get(variant, "bitrate", default=0) or 0),
        )
        return _get(best, "url")

    for variant in reversed(variants):
        if url := _get(variant, "url"):
            return url
    return None


def _media_urls(media: Any) -> list[str]:
    urls: list[str] = []
    if media is None:
        return urls

    for photo in _iter_items(_get(media, "photos", default=[])):
        if url := _get(photo, "url"):
            urls.append(str(url))

    for video in _iter_items(_get(media, "videos", default=[])):
        if url := _best_video_url(video):
            urls.append(str(url))

    for animated in _iter_items(_get(media, "animated", default=[])):
        if url := _get(animated, "videoUrl", "video_url"):
            urls.append(str(url))

    return urls


def normalize_tweet(tweet: Any) -> dict[str, Any]:
    user = _get(tweet, "user", "author", default={})
    tweet_id = str(_get(tweet, "id", "id_str", "tweet_id"))
    author_username = _get(user, "username", "screen_name")
    posted_at = _to_datetime(_get(tweet, "date", "created_at", "posted_at"))
    quoted_tweet = _get(tweet, "quotedTweet", "quoted_tweet")
    quoted_tweet_id = _get(tweet, "quotedTweetId", "quoted_tweet_id")
    if quoted_tweet_id is None and quoted_tweet is not None:
        quoted_tweet_id = _get(quoted_tweet, "id_str", "id", "tweet_id")

    return {
        "tweet_id": tweet_id,
        "tweet_url": _get(tweet, "url", default=f"https://x.com/i/web/status/{tweet_id}"),
        "content": _get(tweet, "rawContent", "content", "text", "full_text"),
        "conversation_id": str(_get(tweet, "conversationId", "conversation_id", default=""))
        or None,
        "quoted_tweet_id": str(quoted_tweet_id or "") or None,
        "is_quote_tweet": bool(
            quoted_tweet or _get(tweet, "isQuoteStatus", "is_quote_tweet", default=False)
        ),
        "in_reply_to_tweet_id": str(
            _get(tweet, "inReplyToTweetId", "in_reply_to_tweet_id", default="")
        )
        or None,
        "is_reply": bool(_get(tweet, "inReplyToTweetId", "is_reply", default=False)),
        "lang": _get(tweet, "lang"),
        "author_id": str(_get(user, "id", "id_str", "user_id", default="")) or None,
        "author_username": author_username,
        "mentions": _json(_get(tweet, "mentionedUsers", "mentions")),
        "urls": _json(_get(tweet, "links", "urls")),
        "hashtags": _json(_get(tweet, "hashtags")),
        "media": _json(_media_urls(_get(tweet, "media"))),
        "posted_at": posted_at,
        "created_at": utc_now(),
        "view_count": _get(tweet, "viewCount", "view_count"),
        "possibly_sensitive": bool(
            _get(tweet, "possiblySensitive", "possibly_sensitive", default=False)
        ),
        "metrics": {
            "like_count": _get(tweet, "likeCount", "like_count", default=0) or 0,
            "reply_count": _get(tweet, "replyCount", "reply_count", default=0) or 0,
            "retweet_count": _get(tweet, "retweetCount", "retweet_count", default=0)
            or 0,
            "quote_count": _get(tweet, "quoteCount", "quote_count", default=0) or 0,
        },
    }
