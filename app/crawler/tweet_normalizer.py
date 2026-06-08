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


def normalize_tweet(tweet: Any) -> dict[str, Any]:
    user = _get(tweet, "user", "author", default={})
    tweet_id = str(_get(tweet, "id", "id_str", "tweet_id"))
    author_username = _get(user, "username", "screen_name")
    posted_at = _to_datetime(_get(tweet, "date", "created_at", "posted_at"))

    return {
        "tweet_id": tweet_id,
        "tweet_url": _get(tweet, "url", default=f"https://x.com/i/web/status/{tweet_id}"),
        "content": _get(tweet, "rawContent", "content", "text", "full_text"),
        "conversation_id": str(_get(tweet, "conversationId", "conversation_id", default=""))
        or None,
        "quoted_tweet_id": str(_get(tweet, "quotedTweetId", "quoted_tweet_id", default=""))
        or None,
        "is_quote_tweet": bool(_get(tweet, "quotedTweet", "is_quote_tweet", default=False)),
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
        "media": _json(_get(tweet, "media")),
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
            "bookmark_count": _get(
                tweet, "bookmarkCount", "bookmark_count", default=0
            )
            or 0,
        },
    }
