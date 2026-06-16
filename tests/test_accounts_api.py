from __future__ import annotations

import sqlite3

import pytest
from fastapi.testclient import TestClient


def _create_accounts_db(path: str) -> None:
    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            CREATE TABLE accounts (
                username TEXT PRIMARY KEY NOT NULL COLLATE NOCASE,
                password TEXT NOT NULL,
                email TEXT NOT NULL COLLATE NOCASE,
                email_password TEXT NOT NULL,
                user_agent TEXT NOT NULL,
                active BOOLEAN DEFAULT FALSE NOT NULL,
                locks TEXT DEFAULT '{}' NOT NULL,
                headers TEXT DEFAULT '{}' NOT NULL,
                cookies TEXT DEFAULT '{}' NOT NULL,
                proxy TEXT DEFAULT NULL,
                error_msg TEXT DEFAULT NULL,
                stats TEXT DEFAULT '{}' NOT NULL,
                last_used TEXT DEFAULT NULL,
                _tx TEXT DEFAULT NULL,
                mfa_code TEXT DEFAULT NULL
            )
            """
        )
        connection.executemany(
            """
            INSERT INTO accounts (
                username, password, email, email_password, user_agent, active,
                locks, headers, cookies, proxy, error_msg, stats, last_used, _tx, mfa_code
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "crawler",
                    "password",
                    "crawler@example.com",
                    "email-password",
                    "Mozilla/5.0",
                    1,
                    "{}",
                    '{"x-csrf-token": "secret-ct0"}',
                    '{"auth_token": "secret-token"}',
                    None,
                    None,
                    "{}",
                    "2026-06-16T00:00:00",
                    None,
                    "123456",
                ),
                (
                    "inactive",
                    "",
                    "",
                    "",
                    "Mozilla/5.0",
                    0,
                    "{}",
                    "{}",
                    "{}",
                    None,
                    "disabled",
                    "{}",
                    None,
                    None,
                    None,
                ),
            ],
        )


def test_list_and_get_accounts_read_from_twscrape_db(
    client: TestClient,
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    accounts_db = tmp_path / "accounts.db"
    _create_accounts_db(str(accounts_db))
    monkeypatch.setenv("TWSCRAPE_DB_PATH", str(accounts_db))

    list_response = client.get("/accounts")
    assert list_response.status_code == 200
    accounts = list_response.json()
    assert [account["username"] for account in accounts] == ["crawler", "inactive"]
    assert "cookies" not in accounts[0]
    assert accounts[0]["has_password"] is True
    assert accounts[0]["has_email_password"] is True
    assert accounts[0]["has_headers"] is True
    assert accounts[0]["has_cookies"] is True
    assert accounts[0]["has_mfa_code"] is True

    active_response = client.get("/accounts", params={"active": True})
    assert active_response.status_code == 200
    assert [account["username"] for account in active_response.json()] == ["crawler"]

    get_response = client.get("/accounts/crawler")
    assert get_response.status_code == 200
    assert get_response.json()["email"] == "crawler@example.com"


def test_get_account_not_found_when_missing_from_twscrape_db(
    client: TestClient,
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    accounts_db = tmp_path / "accounts.db"
    _create_accounts_db(str(accounts_db))
    monkeypatch.setenv("TWSCRAPE_DB_PATH", str(accounts_db))

    response = client.get("/accounts/missing")

    assert response.status_code == 404
    assert response.json()["detail"] == "Account not found"


def test_account_write_endpoints_are_removed_from_openapi(client: TestClient) -> None:
    paths = client.get("/openapi.json").json()["paths"]

    assert set(paths["/accounts"].keys()) == {"get"}
    assert set(paths["/accounts/{username}"].keys()) == {"get"}
