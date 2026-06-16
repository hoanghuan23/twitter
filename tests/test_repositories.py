from __future__ import annotations

from datetime import timedelta

from sqlalchemy.orm import Session

from app.models.tweet import Tweet
from app.models.twitter_source import TwitterSource
from app.repositories.post_repository import TwitterPostRepository
from app.utils.time import utc_now


def test_post_upsert_is_idempotent_by_tweet_id(db_session: Session) -> None:
    db_session.add(
        TwitterSource(
            id=1,
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


def test_due_metric_update_skips_expired_and_untracked(db_session: Session) -> None:
    now = utc_now()
    db_session.add(
        TwitterSource(
            id=1,
            source_type="account",
            twitter_id="12345",
            twitter_url="https://x.com/example",
            is_active=True,
            created_at=now,
        )
    )
    db_session.add_all(
        [
            Tweet(
                source_id=1,
                tweet_id="due",
                tweet_url="https://x.com/example/status/due",
                posted_at=now,
                is_tracked=True,
                metric_tier="warm",
                next_metric_update=now,
            ),
            Tweet(
                source_id=1,
                tweet_id="expired",
                tweet_url="https://x.com/example/status/expired",
                posted_at=now,
                is_tracked=True,
                metric_tier="expired",
                next_metric_update=now,
            ),
            Tweet(
                source_id=1,
                tweet_id="untracked",
                tweet_url="https://x.com/example/status/untracked",
                posted_at=now,
                is_tracked=False,
                metric_tier="warm",
                next_metric_update=now,
            ),
            Tweet(
                source_id=1,
                tweet_id="old-due",
                tweet_url="https://x.com/example/status/old-due",
                posted_at=now - timedelta(hours=24),
                is_tracked=True,
                metric_tier="warm",
                next_metric_update=now,
            ),
        ]
    )
    db_session.commit()

    due = TwitterPostRepository(db_session).due_for_metric_update(
        now,
        now - timedelta(hours=24),
        limit=10,
    )

    assert [tweet.tweet_id for tweet in due] == ["due"]


def test_expire_metric_tracking_older_than_marks_tracked_old_tweets(
    db_session: Session,
) -> None:
    now = utc_now()
    db_session.add(
        TwitterSource(
            id=1,
            source_type="account",
            twitter_id="12345",
            twitter_url="https://x.com/example",
            is_active=True,
            created_at=now,
        )
    )
    old_tweet = Tweet(
        source_id=1,
        tweet_id="old",
        tweet_url="https://x.com/example/status/old",
        posted_at=now - timedelta(hours=24),
        is_tracked=True,
        metric_tier="hot",
        next_metric_update=now,
    )
    recent_tweet = Tweet(
        source_id=1,
        tweet_id="recent",
        tweet_url="https://x.com/example/status/recent",
        posted_at=now - timedelta(hours=23, minutes=59),
        is_tracked=True,
        metric_tier="warm",
        next_metric_update=now,
    )
    db_session.add_all([old_tweet, recent_tweet])
    db_session.commit()

    expired_count = TwitterPostRepository(db_session).expire_metric_tracking_older_than(
        now - timedelta(hours=24)
    )

    assert expired_count == 1
    assert old_tweet.metric_tier == "expired"
    assert old_tweet.is_tracked is False
    assert old_tweet.next_metric_update is None
    assert recent_tweet.metric_tier == "warm"
    assert recent_tweet.is_tracked is True
