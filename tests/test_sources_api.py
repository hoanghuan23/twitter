from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.account import Account


def test_create_list_get_and_delete_source(client: TestClient, db_session: Session) -> None:
    db_session.add(Account(user_id=1, username="crawler"))
    db_session.commit()

    create_response = client.post(
        "/sources",
        json={
            "user_id": 1,
            "source_type": "account",
            "twitter_id": "12345",
            "twitter_url": "https://x.com/example",
            "source_name": "example",
        },
    )
    assert create_response.status_code == 201
    source = create_response.json()
    assert source["id"] == 1
    assert source["is_active"] is True

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

