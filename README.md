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

The scheduler is enabled by default. Disable it for local work with:

```bash
set TWITTER_SCHEDULER_ENABLED=0
```

It checks due sources every 120 seconds by default. Configure this with
`TWITTER_SCHEDULER_INTERVAL_SECONDS`.

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

When every account is locked for a twscrape queue, crawl and metric jobs are marked
`deferred` rather than `failed`. The app reads the earliest queue unlock from
`accounts.db`, adds a 60-second buffer, and retries then. If no usable lock is
available, it uses `TWITTER_NO_ACCOUNT_RETRY_FALLBACK_MINUTES` (15 by default).
Set `TWITTER_NO_ACCOUNT_UNLOCK_BUFFER_SECONDS` to tune the buffer.
Timeline crawls fetch at most 100 tweets by default; set
`TWITTER_ACCOUNT_CRAWL_LIMIT` for a different per-crawl cap.

## Tests

```bash
python -m pytest
```
