-- ============================================================
-- TWITTER SCHEMA
-- Generated from the current accounts.db Twitter tables.
-- ============================================================


-- ============================================================
-- accounts: Twitter/X scraper accounts managed by twscrape
-- ============================================================
CREATE TABLE accounts (
        username        TEXT PRIMARY KEY NOT NULL COLLATE NOCASE,
        password        TEXT NOT NULL,
        email           TEXT NOT NULL COLLATE NOCASE,
        email_password  TEXT NOT NULL,
        user_agent      TEXT NOT NULL,

        active          BOOLEAN DEFAULT FALSE NOT NULL,
        locks           TEXT DEFAULT '{}' NOT NULL,
        headers         TEXT DEFAULT '{}' NOT NULL,
        cookies         TEXT DEFAULT '{}' NOT NULL,
        proxy           TEXT DEFAULT NULL,
        error_msg       TEXT DEFAULT NULL,
        stats           TEXT DEFAULT '{}' NOT NULL,
        last_used       TEXT DEFAULT NULL,
        _tx             TEXT DEFAULT NULL,
        mfa_code        TEXT DEFAULT NULL
);


-- ============================================================
-- twitter_sources: Twitter/X accounts, hashtags, or keywords to track
-- ============================================================
CREATE TABLE twitter_sources (
        id              INTEGER PRIMARY KEY,
        account_username TEXT NOT NULL,

        -- 'account' : track tweets from one account
        -- 'hashtag' : track a hashtag
        -- 'keyword' : track a search keyword
        source_type     VARCHAR(10) NOT NULL CHECK (source_type IN ('account', 'hashtag', 'keyword')),
        topic_id        INTEGER REFERENCES topics(id),

        -- For source_type = 'account', this is the Twitter/X user id.
        twitter_id      VARCHAR(50),
        twitter_url     VARCHAR(255) NOT NULL,
        source_name     VARCHAR(255),
        description     TEXT,

        -- Account stats
        followers_count INTEGER,
        following_count INTEGER,
        tweet_count     INTEGER,

        is_active       BOOLEAN,
        include_replies BOOLEAN DEFAULT FALSE,
        max_days_old    INTEGER,

        created_at      DATETIME,
        last_scraped    DATETIME,
        next_scrape     DATETIME,

        -- Scheduling
        schedule_tier             INTEGER DEFAULT NULL,
        schedule_override_minutes INTEGER DEFAULT NULL,
        daily_views               INTEGER,
        daily_engagement          INTEGER,
        engagement_rate           FLOAT,
        source_score              INTEGER,

        protected        BOOLEAN DEFAULT FALSE,
        verified         BOOLEAN DEFAULT FALSE,

        UNIQUE (account_username, twitter_id, source_type),
        FOREIGN KEY(account_username) REFERENCES accounts (username)
);
CREATE INDEX idx_tw_source_account_active ON twitter_sources (account_username, is_active);
CREATE INDEX idx_tw_source_next_scrape ON twitter_sources (next_scrape);


-- tweets_topic
CREATE TABLE topics (
    id            INTEGER PRIMARY KEY,
    slug          VARCHAR(50)  UNIQUE NOT NULL,
    display_name  VARCHAR(100) NOT NULL,
    display_order INTEGER DEFAULT 0,
    is_active     BOOLEAN DEFAULT TRUE
);


-- ============================================================
-- tweets: collected tweets
-- ============================================================
CREATE TABLE tweets (
        id              INTEGER PRIMARY KEY,
        source_id       INTEGER NOT NULL,

        tweet_id        VARCHAR(50) NOT NULL,
        tweet_url       VARCHAR(500) NOT NULL,

        content         TEXT,
        conversation_id VARCHAR(50),

        quoted_tweet_id VARCHAR(50),
        is_quote_tweet  BOOLEAN DEFAULT FALSE,

        in_reply_to_tweet_id VARCHAR(50),
        is_reply             BOOLEAN DEFAULT FALSE,

        lang            VARCHAR(10),

        author_id       VARCHAR(50),
        author_username VARCHAR(100),

        mentions        TEXT,
        urls            TEXT,

        posted_at       DATETIME NOT NULL,
        created_at      DATETIME,

        is_tracked                BOOLEAN DEFAULT TRUE,
        tracking_until            DATETIME,
        is_deleted                BOOLEAN DEFAULT FALSE,
        last_metric_update        DATETIME,
        metric_tier               VARCHAR(20) NOT NULL DEFAULT 'bootstrap'
                                  CHECK (metric_tier IN ('bootstrap', 'hot', 'warm', 'cold', 'expired')),
        next_metric_update        DATETIME,
        weighted_engagement       INTEGER,
        last_engagement_velocity  FLOAT,
        engagement_rate           FLOAT,
        cold_check_count          INTEGER NOT NULL DEFAULT 0,
        metric_scan_miss_count    INTEGER NOT NULL DEFAULT 0,

        view_count          INTEGER,
        possibly_sensitive  BOOLEAN DEFAULT FALSE,
        hashtags            TEXT,
        media               TEXT,

        PRIMARY KEY (id),
        UNIQUE (tweet_id),
        FOREIGN KEY(source_id) REFERENCES twitter_sources (id)
);
CREATE INDEX idx_tweet_source       ON tweets (source_id);
CREATE INDEX idx_tweet_tweet_id     ON tweets (tweet_id);
CREATE INDEX idx_tweet_posted_at    ON tweets (posted_at);
CREATE INDEX idx_tweet_last_update  ON tweets (last_metric_update);
CREATE INDEX idx_tweet_metric_due   ON tweets (is_tracked, next_metric_update);
CREATE INDEX idx_tweet_conversation ON tweets (conversation_id);
CREATE INDEX idx_tweet_author       ON tweets (author_id);


-- ============================================================
-- tweet_metrics: metric history for tweets
-- ============================================================
CREATE TABLE tweet_metrics (
        id              INTEGER NOT NULL,
        tweet_id        INTEGER NOT NULL,
        job_id          INTEGER,

        like_count      INTEGER DEFAULT 0,
        reply_count     INTEGER DEFAULT 0,
        retweet_count   INTEGER DEFAULT 0,
        quote_count     INTEGER DEFAULT 0,

        recorded_at     DATETIME,

        PRIMARY KEY (id),
        FOREIGN KEY(tweet_id) REFERENCES tweets (id),
        FOREIGN KEY(job_id) REFERENCES twitter_pipeline_jobs (id) ON DELETE SET NULL
);
CREATE INDEX idx_tw_metrics_recorded_at ON tweet_metrics (recorded_at);
CREATE INDEX idx_tw_metric_tweet_date   ON tweet_metrics (tweet_id, recorded_at);
CREATE INDEX idx_tw_metrics_job_time    ON tweet_metrics (job_id, recorded_at);


-- ============================================================
-- tweet_replies: stored replies
-- ============================================================
CREATE TABLE tweet_replies (
        id              INTEGER NOT NULL,
        tweet_id        INTEGER NOT NULL,
        parent_reply_id INTEGER,

        reply_tweet_id  VARCHAR(50) NOT NULL,

        author_id       VARCHAR(50),
        author_username VARCHAR(100),

        content         TEXT,

        like_count      INTEGER DEFAULT 0,
        reply_count     INTEGER DEFAULT 0,

        depth_level     INTEGER DEFAULT 1,

        posted_at       DATETIME,
        created_at      DATETIME,
        last_updated    DATETIME NOT NULL,

        PRIMARY KEY (id),
        UNIQUE (reply_tweet_id),
        FOREIGN KEY(tweet_id) REFERENCES tweets (id),
        FOREIGN KEY(parent_reply_id) REFERENCES tweet_replies (id)
);
CREATE INDEX idx_tw_reply_tweet_id  ON tweet_replies (tweet_id);
CREATE INDEX idx_tw_reply_tweet_ref ON tweet_replies (reply_tweet_id);


-- ============================================================
-- twitter_analytics_cache: daily source aggregates
-- ============================================================
CREATE TABLE twitter_analytics_cache (
        id              INTEGER NOT NULL,
        source_id       INTEGER NOT NULL,
        date            DATETIME NOT NULL,

        total_tweets    INTEGER DEFAULT 0,
        total_likes     INTEGER DEFAULT 0,
        total_replies   INTEGER DEFAULT 0,
        total_retweets  INTEGER DEFAULT 0,
        total_quotes    INTEGER DEFAULT 0,
        total_bookmarks INTEGER DEFAULT 0,

        avg_likes_per_tweet FLOAT,
        top_tweet_id        VARCHAR(50),
        growth_rate         FLOAT,

        cached_at       DATETIME,

        PRIMARY KEY (id),
        UNIQUE (source_id, date),
        FOREIGN KEY(source_id) REFERENCES twitter_sources (id)
);
CREATE INDEX idx_tw_analytics_source_date ON twitter_analytics_cache (source_id, date);


-- ============================================================
-- twitter_pipeline_jobs: Twitter pipeline job tracking
-- ============================================================
CREATE TABLE twitter_pipeline_jobs (
        id              INTEGER PRIMARY KEY,

        job_type        VARCHAR(20) NOT NULL DEFAULT 'scraper_job'
                        CHECK (job_type IN ('scrape_timeline', 'scraper_job', 'update_metric', 'analytics')),

        source_id       INTEGER REFERENCES twitter_sources(id) ON DELETE SET NULL,
        session_username TEXT REFERENCES accounts(username) ON DELETE SET NULL,

        status          VARCHAR(10) NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending', 'running', 'done', 'failed')),

        tweets_found    INTEGER NOT NULL DEFAULT 0,
        tweets_new      INTEGER NOT NULL DEFAULT 0,
        items_total     INTEGER NOT NULL DEFAULT 0,
        items_updated   INTEGER NOT NULL DEFAULT 0,
        items_failed    INTEGER NOT NULL DEFAULT 0,

        rate_limit_hits INTEGER NOT NULL DEFAULT 0,

        error_message   TEXT,
        started_at      DATETIME,
        finished_at     DATETIME
);
CREATE INDEX idx_tw_pipeline_jobs_source_time ON twitter_pipeline_jobs (source_id, started_at DESC);
CREATE INDEX idx_tw_pipeline_jobs_type_status ON twitter_pipeline_jobs (job_type, status, started_at DESC);


-- ============================================================
-- twitter_pipeline_logs: Twitter pipeline logs
-- ============================================================
CREATE TABLE twitter_pipeline_logs (
        id              INTEGER PRIMARY KEY,

        job_id          INTEGER REFERENCES twitter_pipeline_jobs(id) ON DELETE SET NULL,
        source_id       INTEGER REFERENCES twitter_sources(id),

        log_level       VARCHAR(20),
        message         TEXT NOT NULL,
        error_type      VARCHAR(100),
        error_details   TEXT,

        created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_tw_pipeline_logs_job    ON twitter_pipeline_logs (job_id, created_at);
CREATE INDEX idx_tw_pipeline_logs_source ON twitter_pipeline_logs (source_id, created_at);
CREATE INDEX idx_tw_pipeline_logs_level  ON twitter_pipeline_logs (log_level, created_at);
