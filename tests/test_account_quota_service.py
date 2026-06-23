from __future__ import annotations

import sqlite3
from datetime import timedelta

from app.services.account_quota_service import AccountQuotaService
from app.utils.time import utc_now


def _create_accounts_db(path, rows: list[tuple[int, str]]) -> None:
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE accounts (active BOOLEAN, locks TEXT)")
        connection.executemany("INSERT INTO accounts (active, locks) VALUES (?, ?)", rows)


def test_queue_availability_uses_earliest_lock_and_queue(tmp_path) -> None:
    now = utc_now()
    early = now + timedelta(minutes=4)
    later = now + timedelta(minutes=9)
    db_path = tmp_path / "accounts.db"
    _create_accounts_db(
        db_path,
        [
            (1, f'{{"UserTweets": "{later.isoformat()}", "TweetDetail": "{early.isoformat()}"}}'),
            (1, f'{{"UserTweets": "{early.isoformat()}"}}'),
        ],
    )

    service = AccountQuotaService(str(db_path))

    user_tweets = service.availability("UserTweets", now)
    tweet_details = service.availability("TweetDetail", now)

    assert not user_tweets.available
    assert user_tweets.retry_at == early + timedelta(seconds=60)
    assert tweet_details.available


def test_queue_availability_uses_fallback_without_active_accounts(tmp_path) -> None:
    now = utc_now()
    db_path = tmp_path / "accounts.db"
    _create_accounts_db(db_path, [(0, "{}")])

    availability = AccountQuotaService(str(db_path)).availability("UserTweets", now)

    assert not availability.available
    assert availability.retry_at == now + timedelta(minutes=15)


def test_queue_availability_uses_fallback_for_invalid_lock_data(tmp_path) -> None:
    now = utc_now()
    db_path = tmp_path / "accounts.db"
    _create_accounts_db(db_path, [(1, "not-json")])

    availability = AccountQuotaService(str(db_path)).availability("UserTweets", now)

    assert not availability.available
    assert availability.retry_at == now + timedelta(minutes=15)
