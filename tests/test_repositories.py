from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.twitter_source import TwitterSource
from app.repositories.post_repository import TwitterPostRepository
from app.utils.time import utc_now


def test_post_upsert_is_idempotent_by_tweet_id(db_session: Session) -> None:
    db_session.add(Account(user_id=1, username="crawler"))
    db_session.add(
        TwitterSource(
            id=1,
            user_id=1,
            source_type="account",
            twitter_id="12345",
            twitter_url="https://x.com/example",
            is_active=True,
            created_at=utc_now(),
        )
    )
    db_session.commit()

    repository = TwitterPostRepository(db_session)
    payload = {
        "tweet_id": "tweet-1",
        "tweet_url": "https://x.com/example/status/tweet-1",
        "content": "first",
        "posted_at": utc_now(),
    }
    tweet, is_new = repository.upsert(1, payload)
    assert is_new is True
    assert tweet.content == "first"

    payload["content"] = "updated"
    same_tweet, is_new = repository.upsert(1, payload)
    assert is_new is False
    assert same_tweet.id == tweet.id
    assert same_tweet.content == "updated"
