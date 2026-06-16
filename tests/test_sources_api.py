from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.crawler.twscrape_client import TwscrapeClient
from app.models.topic import Topic
from app.models.twitter_source import TwitterSource
from app.utils.time import utc_now
from twscrape.accounts_pool import NoAccountError


def _fake_user(**overrides):
    data = {
        "id_str": "12345",
        "url": "https://x.com/example",
        "username": "example",
        "rawDescription": "Example profile",
        "followersCount": 100,
        "friendsCount": 20,
        "statusesCount": 300,
        "protected": False,
        "verified": True,
        "blue": False,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def test_create_list_get_and_delete_source(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_get_user_by_login(self: TwscrapeClient, username: str):
        assert username == "example"
        return _fake_user()

    monkeypatch.setattr(TwscrapeClient, "get_user_by_login", fake_get_user_by_login)

    db_session.add(Topic(id=1, slug="sports", display_name="Sports"))
    db_session.commit()

    create_response = client.post(
        "/sources",
        json={
            "source_type": "account",
            "topic_id": 1,
            "source_name": " @example ",
        },
    )
    assert create_response.status_code == 201
    source = create_response.json()
    assert source["id"] == 1
    assert "account_username" not in source
    assert source["is_active"] is True
    assert source["topic_id"] == 1
    assert source["twitter_id"] == "12345"
    assert source["twitter_url"] == "https://x.com/example"
    assert source["source_name"] == "example"
    assert source["max_days_old"] == 1
    assert source["description"] == "Example profile"
    assert source["followers_count"] == 100
    assert source["following_count"] == 20
    assert source["tweet_count"] == 300
    assert source["daily_views"] is None
    assert source["daily_engagement"] is None
    assert source["engagement_rate"] is None
    assert source["source_score"] is None
    assert source["protected"] is False
    assert source["verified"] is True
    assert db_session.get(TwitterSource, source["id"]).topic_id == 1

    list_response = client.get("/sources")
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    get_response = client.get(f"/sources/{source['id']}")
    assert get_response.status_code == 200
    assert get_response.json()["twitter_id"] == "12345"

    delete_response = client.delete(f"/sources/{source['id']}")
    assert delete_response.status_code == 200
    assert delete_response.json() == {"deleted": True}

    active_response = client.get("/sources", params={"active": True})
    assert active_response.status_code == 200
    assert active_response.json() == []


def test_create_source_rejects_unknown_username(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_get_user_by_login(self: TwscrapeClient, username: str):
        return None

    monkeypatch.setattr(TwscrapeClient, "get_user_by_login", fake_get_user_by_login)

    response = client.post(
        "/sources",
        json={
            "account_username": "crawler",
            "source_type": "account",
            "source_name": "missing",
        },
    )

    assert response.status_code == 404
    assert db_session.query(TwitterSource).count() == 0


def test_create_source_ignores_deprecated_account_username(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_get_user_by_login(self: TwscrapeClient, username: str):
        assert username == "elonmusk"
        return _fake_user(username="elonmusk", id_str="999")

    monkeypatch.setattr(TwscrapeClient, "get_user_by_login", fake_get_user_by_login)

    response = client.post(
        "/sources",
        json={
            "account_username": "elonmusk",
            "source_type": "account",
            "source_name": "elonmusk",
        },
    )

    assert response.status_code == 201
    assert response.json()["source_name"] == "elonmusk"
    assert db_session.query(TwitterSource).count() == 1


def test_create_source_verified_ignores_blue(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_get_user_by_login(self: TwscrapeClient, username: str):
        return _fake_user(verified=False, blue=True)

    monkeypatch.setattr(TwscrapeClient, "get_user_by_login", fake_get_user_by_login)

    response = client.post(
        "/sources",
        json={
            "account_username": "crawler",
            "source_type": "account",
            "source_name": "example",
        },
    )

    assert response.status_code == 201
    assert response.json()["verified"] is False


def test_create_source_updates_existing_account_source(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    followers = iter([100, 250])

    async def fake_get_user_by_login(self: TwscrapeClient, username: str):
        return _fake_user(followersCount=next(followers))

    monkeypatch.setattr(TwscrapeClient, "get_user_by_login", fake_get_user_by_login)

    first_response = client.post(
        "/sources",
        json={
            "source_type": "account",
            "source_name": "example",
        },
    )
    second_response = client.post(
        "/sources",
        json={
            "source_type": "account",
            "source_name": "example",
        },
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 201
    assert second_response.json()["id"] == first_response.json()["id"]
    assert second_response.json()["followers_count"] == 250
    assert db_session.query(TwitterSource).count() == 1


def test_update_source_config_fields(
    client: TestClient,
    db_session: Session,
) -> None:
    now = utc_now()
    db_session.add(Topic(id=1, slug="sports", display_name="Sports"))
    source = TwitterSource(
        source_type="account",
        twitter_id="12345",
        twitter_url="https://x.com/example",
        source_name="example",
        include_replies=False,
        max_days_old=1,
        is_active=True,
        created_at=now,
        next_scrape=now,
        schedule_tier=1,
    )
    db_session.add(source)
    db_session.commit()

    response = client.patch(
        f"/sources/{source.id}",
        json={
            "topic_id": 1,
            "include_replies": True,
            "max_days_old": 3,
            "is_active": False,
            "schedule_override_minutes": 15,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["topic_id"] == 1
    assert body["include_replies"] is True
    assert body["max_days_old"] == 3
    assert body["is_active"] is False
    assert body["schedule_override_minutes"] == 15

    db_session.refresh(source)
    assert source.topic_id == 1
    assert source.include_replies is True
    assert source.max_days_old == 3
    assert source.is_active is False
    assert source.schedule_override_minutes == 15
    assert source.next_scrape == now
    assert source.schedule_tier == 1
    assert source.twitter_url == "https://x.com/example"
    assert source.source_name == "example"
    assert source.twitter_id == "12345"


def test_update_source_clears_schedule_override(
    client: TestClient,
    db_session: Session,
) -> None:
    source = TwitterSource(
        source_type="account",
        twitter_id="12345",
        twitter_url="https://x.com/example",
        source_name="example",
        is_active=True,
        schedule_override_minutes=15,
    )
    db_session.add(source)
    db_session.commit()

    response = client.patch(
        f"/sources/{source.id}",
        json={"schedule_override_minutes": None},
    )

    assert response.status_code == 200
    assert response.json()["schedule_override_minutes"] is None
    db_session.refresh(source)
    assert source.schedule_override_minutes is None


def test_update_source_empty_body_returns_existing_source(
    client: TestClient,
    db_session: Session,
) -> None:
    source = TwitterSource(
        source_type="account",
        twitter_id="12345",
        twitter_url="https://x.com/example",
        source_name="example",
        is_active=True,
        schedule_override_minutes=15,
    )
    db_session.add(source)
    db_session.commit()

    response = client.patch(f"/sources/{source.id}", json={})

    assert response.status_code == 200
    assert response.json()["schedule_override_minutes"] == 15
    db_session.refresh(source)
    assert source.schedule_override_minutes == 15


def test_update_source_reports_not_found(
    client: TestClient,
) -> None:
    response = client.patch(
        "/sources/999",
        json={"schedule_override_minutes": 15},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Source not found"


def test_update_source_validates_positive_intervals(
    client: TestClient,
) -> None:
    override_response = client.patch(
        "/sources/1",
        json={"schedule_override_minutes": 0},
    )
    max_days_response = client.patch(
        "/sources/1",
        json={"max_days_old": 0},
    )

    assert override_response.status_code == 422
    assert max_days_response.status_code == 422


def test_create_keyword_source_from_source_name(
    client: TestClient,
    db_session: Session,
) -> None:
    payload = {
        "source_type": "keyword",
        "source_name": " world cup ",
        "include_replies": False,
        "max_days_old": 1,
    }

    first_response = client.post("/sources", json=payload)
    second_response = client.post("/sources", json=payload)

    assert first_response.status_code == 201
    assert second_response.status_code == 201
    source = first_response.json()
    assert source["source_type"] == "keyword"
    assert source["source_name"] == "world cup"
    assert source["twitter_url"] == "https://x.com/search?q=world%20cup&src=typed_query"
    assert second_response.json()["id"] == source["id"]
    assert db_session.query(TwitterSource).count() == 1


def test_create_source_reports_unavailable_twscrape_account(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_get_user_by_login(self: TwscrapeClient, username: str):
        raise NoAccountError(
            'No account available for queue "UserByScreenName". Next available at 09:34:32'
        )

    monkeypatch.setattr(TwscrapeClient, "get_user_by_login", fake_get_user_by_login)

    response = client.post(
        "/sources",
        json={
            "account_username": "crawler",
            "source_type": "account",
            "source_name": "example",
        },
    )

    assert response.status_code == 503
    assert "No twscrape account available" in response.json()["detail"]
    assert db_session.query(TwitterSource).count() == 0


def test_create_source_reports_unavailable_twscrape_account_by_message(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_get_user_by_login(self: TwscrapeClient, username: str):
        raise ValueError(
            'No account available for queue "UserByScreenName". Next available at 09:34:32'
        )

    monkeypatch.setattr(TwscrapeClient, "get_user_by_login", fake_get_user_by_login)

    response = client.post(
        "/sources",
        json={
            "account_username": "crawler",
            "source_type": "account",
            "source_name": "example",
        },
    )

    assert response.status_code == 503
    assert "No account available" in response.json()["detail"]
    assert db_session.query(TwitterSource).count() == 0
