from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.crawler.twscrape_client import TwscrapeClient
from app.models.account import Account
from app.models.twitter_source import TwitterSource
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

    db_session.add(Account(username="crawler"))
    db_session.commit()

    create_response = client.post(
        "/sources",
        json={
            "source_type": "account",
            "source_name": " @example ",
        },
    )
    assert create_response.status_code == 201
    source = create_response.json()
    assert source["id"] == 1
    assert source["account_username"] == "crawler"
    assert source["is_active"] is True
    assert source["twitter_id"] == "12345"
    assert source["twitter_url"] == "https://x.com/example"
    assert source["source_name"] == "example"
    assert source["max_days_old"] == 1
    assert source["description"] == "Example profile"
    assert source["followers_count"] == 100
    assert source["following_count"] == 20
    assert source["tweet_count"] == 300
    assert source["protected"] is False
    assert source["verified"] is True

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

    db_session.add(Account(username="crawler"))
    db_session.commit()

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


def test_create_source_reports_unknown_crawler_account(
    client: TestClient,
    db_session: Session,
) -> None:
    db_session.add(Account(username="crawler"))
    db_session.commit()

    response = client.post(
        "/sources",
        json={
            "account_username": "elonmusk",
            "source_type": "account",
            "source_name": "elonmusk",
        },
    )

    assert response.status_code == 404
    assert "Crawler account not found: elonmusk" in response.json()["detail"]
    assert db_session.query(TwitterSource).count() == 0


def test_create_source_verified_ignores_blue(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_get_user_by_login(self: TwscrapeClient, username: str):
        return _fake_user(verified=False, blue=True)

    monkeypatch.setattr(TwscrapeClient, "get_user_by_login", fake_get_user_by_login)

    db_session.add(Account(username="crawler"))
    db_session.commit()

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

    db_session.add(Account(username="crawler"))
    db_session.commit()

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


def test_create_keyword_source_from_source_name(
    client: TestClient,
    db_session: Session,
) -> None:
    db_session.add(Account(username="crawler"))
    db_session.commit()

    payload = {
        "source_type": "keyword",
        "source_name": " world cup ",
        "include_replies": False,
        "max_days_old": 1,
        "schedule_tier": 1,
        "schedule_override_minutes": 15,
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

    db_session.add(Account(username="crawler"))
    db_session.commit()

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

    db_session.add(Account(username="crawler"))
    db_session.commit()

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
