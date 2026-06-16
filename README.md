# Twitter Crawler MVP

Python MVP for crawling X/Twitter with `twscrape`, storing data in SQLite, and exposing read/write APIs with FastAPI.

## Architecture

```text
X / Twitter -> twscrape -> TwitterCrawlerService -> Repository -> SQLite -> FastAPI
```

The API exposes tweets as `posts`, while persistence keeps the existing schema and writes to `tweets`.

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
```

Default database path:

```text
data/twitter.db
```

Override it with:

```bash
set DATABASE_URL=sqlite:///./data/twitter.db
```

## Run API

```bash
uvicorn app.main:app --reload
```

Health check:

```text
GET /health
```

## Scheduler

The scheduler is disabled by default for local safety. Enable it with:

```bash
set TWITTER_SCHEDULER_ENABLED=1
uvicorn app.main:app --reload
```

It checks due sources every 5 minutes by default.

## API

Accounts:

- `GET /accounts`
- `GET /accounts/{user_id}`
- write operations are disabled; manage accounts with `twscrape`

Sources:

- `GET /sources`
- `GET /sources/{id}`
- `POST /sources`
- `DELETE /sources/{id}`

Posts:

- `GET /posts`
- `GET /posts/latest`
- `GET /posts/{id}`

Jobs:

- `GET /jobs`
- `GET /jobs/{id}`
- `POST /jobs/sources/{source_id}/crawl`
- `POST /jobs/crawl-due`

## twscrape Accounts

Twitter accounts are managed separately by `twscrape` in `data/accounts.db` by default. Override that path with:

```bash
set TWSCRAPE_DB_PATH=./data/accounts.db
```

Add and log in accounts with `twscrape` before running real crawl jobs. The app reads `/accounts` from `accounts.db` for visibility only; it does not create, update, delete, authenticate, or select crawler accounts itself. Source creation accepts a legacy `account_username` field for old clients, but ignores it because `twscrape` chooses an available account internally.

## Tests

```bash
python -m pytest
```
