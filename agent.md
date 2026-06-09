# Agent Navigation Map

## 1. DIRECTORY MAP

/app/                       -> Main FastAPI application package.
  main.py                   -> App construction, router registration, DB table creation, optional scheduler startup.
  config.py                 -> Env-backed runtime settings for DB, twscrape DB, scheduler, crawl limits.
  database.py               -> SQLAlchemy Base, engine, SessionLocal, SQLite FK pragma, FastAPI DB dependency.

/app/api/                   -> HTTP API layer.
  routers/accounts.py       -> `/accounts` list/get/create/deactivate crawler accounts.
  routers/sources.py        -> `/sources` list/get/create/deactivate tracked Twitter/X sources.
  routers/posts.py          -> `/posts` list/latest/get persisted tweets exposed as posts.
  routers/jobs.py           -> `/jobs` list/get/manual crawl/crawl-due endpoints.

/app/crawler/               -> Scraper integration boundary.
  twscrape_client.py        -> `twscrape.API` wrapper, account/search crawl dispatch, timeline filters.
  tweet_normalizer.py       -> Converts raw twscrape tweet objects/dicts into DB-ready payloads.

/app/services/              -> Business orchestration layer.
  account_service.py        -> Account API behavior, duplicate handling, sensitive field hiding.
  twitter_source_service.py -> Source validation, crawler account resolution, twscrape user enrichment, schedule math.
  twitter_post_service.py   -> Tweet-to-post API mapping and latest metric attachment.
  twitter_crawler_service.py-> Crawl job lifecycle, tweet normalization, upsert, metric snapshots, failure logs.
  scheduler_service.py      -> Async loop that crawls due sources when scheduler is enabled.

/app/repositories/          -> SQLAlchemy persistence layer.
  account_repository.py     -> Account list/get/first-active/create/deactivate.
  source_repository.py      -> Source list/get/create-or-update/deactivate/due-source query.
  post_repository.py        -> Tweet list/latest/get/get-by-tweet-id/upsert.
  metric_repository.py      -> Metric snapshot writes and latest metric lookup.
  job_repository.py         -> Pipeline job create/list/get/done/failed/log writes.

/app/models/                -> SQLAlchemy ORM models.
  account.py                -> `accounts` table and twscrape account/session fields.
  twitter_source.py         -> `twitter_sources` table and crawl schedule metadata.
  tweet.py                  -> `tweets` table, tweet identity/content/tracking fields.
  tweet_metric.py           -> `tweet_metrics` table for metric snapshots.
  pipeline_job.py           -> `twitter_pipeline_jobs` table for crawl lifecycle.
  pipeline_log.py           -> `twitter_pipeline_logs` table for job/source logs.

/app/schemas/               -> Pydantic request/response models.
  account.py                -> Account create/read/delete schemas; hides raw secrets in API reads.
  source.py                 -> Source create/read/delete schemas; source_type enum.
  post.py                   -> PostRead schema; maps DB tweet fields into API post fields.
  job.py                    -> JobRead and CrawlDueResponse schemas.

/app/utils/                 -> Shared helpers.
  time.py                   -> `utc_now()` naive UTC timestamp helper.

/data/                      -> Local database artifacts.
  schema_table_twitter.sql  -> Canonical SQLite DDL, including ORM tables plus SQL-only planned tables.
  twitter.db                -> Runtime SQLite DB [generated/runtime].

/tests/                     -> pytest coverage.
  conftest.py               -> In-memory SQLite fixtures and FastAPI DB dependency override.
  test_*.py                 -> API, repository, crawler, normalizer, and route behavior tests.

/README.md                  -> Setup, architecture, API list, scheduler notes, test command.
/requirements.txt           -> Python dependencies.

NOTE Current workspace implements Twitter/X only. Brotli/Facebook lazy-load logic is not present in this repo; keep those as cross-platform gotchas or planned scraper concerns.

## 2. CORE LOGIC MAP

API app startup                              -> app/main.py:lifespan()
Router registration                          -> app/main.py:app.include_router(...)
Scheduler enable switch                      -> app/config.py:Settings.scheduler_enabled
Scheduler interval                           -> app/config.py:Settings.scheduler_interval_seconds
Due crawl batch size                         -> app/config.py:Settings.crawl_due_limit
Default hashtag/keyword crawl limit          -> app/config.py:Settings.default_crawl_limit
Default account crawl limit                  -> app/config.py:Settings.account_crawl_limit
Database sessions                            -> app/database.py:SessionLocal, app/database.py:get_db()

Manual crawl endpoint                        -> app/api/routers/jobs.py:crawl_source()
Crawl due endpoint                           -> app/api/routers/jobs.py:crawl_due_sources()
Scheduler service                            -> app/services/scheduler_service.py:SchedulerService
Scheduler loop                               -> app/services/scheduler_service.py:SchedulerService._run_loop()
Scheduled due-source crawl                   -> app/services/scheduler_service.py:SchedulerService.crawl_due_sources()
Due source lookup                            -> app/services/twitter_source_service.py:TwitterSourceService.due_sources()
Due source SQL query                         -> app/repositories/source_repository.py:TwitterSourceRepository.due_sources()
Source schedule interval                     -> app/services/twitter_source_service.py:TwitterSourceService.scrape_interval_minutes()
Source next_scrape update                    -> app/services/twitter_source_service.py:TwitterSourceService.mark_scraped()

Crawl orchestration                          -> app/services/twitter_crawler_service.py:TwitterCrawlerService.crawl_source()
Running job creation                         -> app/repositories/job_repository.py:TwitterPipelineJobRepository.create_running()
Job done transition                          -> app/repositories/job_repository.py:TwitterPipelineJobRepository.mark_done()
Job failed transition                        -> app/repositories/job_repository.py:TwitterPipelineJobRepository.mark_failed()
Pipeline error logging                       -> app/repositories/job_repository.py:TwitterPipelineJobRepository.log()
Raw tweet normalization                      -> app/crawler/tweet_normalizer.py:normalize_tweet()
Tweet upsert                                 -> app/repositories/post_repository.py:TwitterPostRepository.upsert()
Metric snapshot creation                     -> app/repositories/metric_repository.py:TweetMetricRepository.create_snapshot()

twscrape lazy initialization                 -> app/crawler/twscrape_client.py:TwscrapeClient.api
Source crawl dispatch                        -> app/crawler/twscrape_client.py:TwscrapeClient.crawl_source()
Account timeline crawl                       -> app/crawler/twscrape_client.py:TwscrapeClient._crawl_account()
Hashtag/keyword search query                 -> app/crawler/twscrape_client.py:TwscrapeClient._search_query()
Twitter user lookup                          -> app/crawler/twscrape_client.py:TwscrapeClient.get_user_by_login()
Author filter                                -> app/crawler/twscrape_client.py:TwscrapeClient._tweet_matches_author()
Repost filter                                -> app/crawler/twscrape_client.py:TwscrapeClient._is_repost()
Account age cutoff                           -> app/crawler/twscrape_client.py:TwscrapeClient._account_cutoff()
Tweet oldness check                          -> app/crawler/twscrape_client.py:TwscrapeClient._tweet_is_older_than()

Source creation                              -> app/services/twitter_source_service.py:TwitterSourceService.create_source()
Crawler account resolution                   -> app/services/twitter_source_service.py:TwitterSourceService._resolve_account_username()
Account source enrichment                    -> app/services/twitter_source_service.py:TwitterSourceService._account_enriched_fields()
Non-account source validation                -> app/services/twitter_source_service.py:TwitterSourceService._source_enriched_fields()
Source create-or-update                      -> app/repositories/source_repository.py:TwitterSourceRepository.create()
Existing source match                        -> app/repositories/source_repository.py:TwitterSourceRepository._get_existing()

Post API mapping                             -> app/services/twitter_post_service.py:TwitterPostService._to_post_reads()
Latest metric attachment                     -> app/repositories/metric_repository.py:TweetMetricRepository.latest_by_tweet_ids()
Media response parsing                       -> app/services/twitter_post_service.py:TwitterPostService._media_urls()
Tweet media extraction                       -> app/crawler/tweet_normalizer.py:_media_urls()
Best video variant selection                 -> app/crawler/tweet_normalizer.py:_best_video_url()

Account creation                             -> app/services/account_service.py:AccountService.create_account()
Account response sanitization                -> app/services/account_service.py:AccountService.to_read()
First active crawler account                 -> app/repositories/account_repository.py:AccountRepository.first_active()

## 3. KNOWN ISSUES & GOTCHAS

WARNING Brotli decode handling is not implemented in this repo
  -> `rg` finds no Brotli/Content-Encoding helper in the current Twitter-only workspace.
  -> If adding HTTP scrapers, create one central decoder such as [PLANNED] app/utils/http.py:safe_decode_response().
  -> Do not scatter ad hoc `response.text`/manual decompression across scraper modules.

WARNING Facebook lazy-loaded metrics are not implemented in this repo
  -> No Facebook scraper/page/group module exists in the current workspace.
  -> If reintroducing multi-platform scraping, document Page vs Group metric behavior beside that scraper.
  -> Planned location: [PLANNED] app/crawler/facebook_client.py or [PLANNED] app/services/facebook_crawler_service.py.

WARNING Tweet writes must use upsert by external `tweet_id`
  -> Raw inserts can hit UNIQUE violations on `tweets.tweet_id`.
  -> Use app/repositories/post_repository.py:TwitterPostRepository.upsert().
  -> Covered by tests/test_repositories.py:test_post_upsert_is_idempotent_by_tweet_id().

WARNING Source creation is create-or-update for existing account sources
  -> Match key is `(account_username, twitter_id, source_type)`.
  -> See: app/repositories/source_repository.py:TwitterSourceRepository._get_existing().
  -> Re-posting the same account source refreshes metadata instead of creating a duplicate.

WARNING Scheduler and scraper logic are intentionally split across files
  -> Startup toggle: app/main.py:lifespan().
  -> Loop/batch execution: app/services/scheduler_service.py:SchedulerService.
  -> Due-source selection/schedule math: app/services/twitter_source_service.py and app/repositories/source_repository.py.
  -> Actual crawl/write lifecycle: app/services/twitter_crawler_service.py:TwitterCrawlerService.crawl_source().

WARNING Scheduler is disabled by default
  -> Enable with env:TWITTER_SCHEDULER_ENABLED=1.
  -> Interval is env:TWITTER_SCHEDULER_INTERVAL_SECONDS, default `300`.
  -> Due batch size is env:TWITTER_CRAWL_DUE_LIMIT, default `10`.

WARNING Account timeline crawl filters replies by default
  -> Set `TwitterSource.include_replies=True` to include replies.
  -> See: app/crawler/twscrape_client.py:TwscrapeClient._crawl_account().

WARNING Account timeline crawl filters retweets/reposts
  -> Repost detection checks `retweetedTweet` and content starting with `RT @`.
  -> See: app/crawler/twscrape_client.py:TwscrapeClient._is_repost().

WARNING Account timeline crawl only accepts tweets from expected author id
  -> Prevents quote-original/foreign-author timeline items from being stored.
  -> See: app/crawler/twscrape_client.py:TwscrapeClient._tweet_matches_author().

WARNING First old timeline item is skipped once before cutoff stops crawl
  -> Preserves behavior for pinned/foreign old items near top of timeline.
  -> See: app/crawler/twscrape_client.py:TwscrapeClient._crawl_account().

WARNING Quote tweet normalization stores the crawled quote tweet, not the quoted original
  -> `quoted_tweet_id` is retained; content/author/media come from the source tweet.
  -> See: app/crawler/tweet_normalizer.py:normalize_tweet().

WARNING Media storage is a JSON array of URLs only
  -> Photos use `url`, videos use highest bitrate variant, animated media uses `videoUrl`.
  -> See: app/crawler/tweet_normalizer.py:_media_urls().

WARNING Metrics are snapshots, not embedded counters on Tweet
  -> Post reads attach latest metric by tweet DB id.
  -> See: app/repositories/metric_repository.py:TweetMetricRepository.create_snapshot().

WARNING `/jobs/crawl-due` must stay before `/{job_id}`
  -> Prevents FastAPI dynamic route capture.
  -> See: app/api/routers/jobs.py.
