from __future__ import annotations

import json

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.account import Account


def test_create_list_get_and_deactivate_account(
    client: TestClient,
    db_session: Session,
) -> None:
    response = client.post(
        "/accounts",
        json={
            "username": "crawler",
            "user_agent": "Mozilla/5.0",
            "cookies": {"auth_token": "secret-token", "ct0": "secret-ct0"},
            "headers": {"x-csrf-token": "secret-ct0"},
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["user_id"] == 1
    assert body["username"] == "crawler"
    assert body["has_cookies"] is True
    assert body["has_headers"] is True
    assert "cookies" not in body
    assert "headers" not in body

    account = db_session.get(Account, body["user_id"])
    assert account is not None
    assert json.loads(account.cookies)["auth_token"] == "secret-token"
    assert json.loads(account.stats) == {"UserByScreenName": 1}

    list_response = client.get("/accounts")
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1
    assert "cookies" not in list_response.json()[0]

    get_response = client.get(f"/accounts/{body['user_id']}")
    assert get_response.status_code == 200
    assert get_response.json()["has_cookies"] is True

    delete_response = client.delete(f"/accounts/{body['user_id']}")
    assert delete_response.status_code == 200
    assert delete_response.json() == {"deleted": True}

    active_response = client.get("/accounts", params={"active": True})
    assert active_response.status_code == 200
    assert active_response.json() == []

