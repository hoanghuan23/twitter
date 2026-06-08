from __future__ import annotations

from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.tweet import Tweet
from app.models.tweet_metric import TweetMetric
from app.models.twitter_source import TwitterSource
from app.utils.time import utc_now


def test_list_latest_and_get_posts(client: TestClient, db_session: Session) -> None:
    now = utc_now()
    db_session.add(Account(user_id=1, username="crawler"))
    source = TwitterSource(
        id=1,
        user_id=1,
        source_type="account",
        twitter_id="12345",
        twitter_url="https://x.com/example",
        source_name="example",
        is_active=True,
        created_at=now,
    )
    db_session.add(source)
    older = Tweet(
        source_id=1,
        tweet_id="tweet-1",
        tweet_url="https://x.com/example/status/tweet-1",
        content="older",
        author_username="example",
        posted_at=now - timedelta(hours=1),
        created_at=now,
    )
    newer = Tweet(
        source_id=1,
        tweet_id="tweet-2",
        tweet_url="https://x.com/example/status/tweet-2",
        content="newer",
        author_username="example",
        posted_at=now,
        created_at=now,
        view_count=100,
    )
    db_session.add_all([older, newer])
    db_session.flush()
    db_session.add(TweetMetric(tweet_id=newer.id, like_count=5, recorded_at=now))
    db_session.commit()

    latest_response = client.get("/posts/latest")
    assert latest_response.status_code == 200
    latest = latest_response.json()
    assert latest[0]["post_id"] == "tweet-2"
    assert latest[0]["like_count"] == 5

    list_response = client.get("/posts", params={"author_username": "example"})
    assert list_response.status_code == 200
    assert [item["post_id"] for item in list_response.json()] == ["tweet-2", "tweet-1"]

    get_response = client.get(f"/posts/{newer.id}")
    assert get_response.status_code == 200
    assert get_response.json()["post_url"] == "https://x.com/example/status/tweet-2"
