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
- `POST /accounts`
- `DELETE /accounts/{user_id}`

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

The existing schema uses `accounts.user_id` as `twitter_sources.user_id`. Add and log in accounts with `twscrape` before running real crawl jobs. The app does not implement authentication in this MVP.

## Tests

```bash
python -m pytest
```
