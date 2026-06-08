-- ============================================================
-- TWITTER SCHEMA
-- Generated from the current accounts.db Twitter tables.
-- ============================================================


-- ============================================================
-- accounts: Twitter/X scraper accounts managed by twscrape
-- ============================================================
CREATE TABLE accounts (
        user_id         INTEGER NOT NULL,

        username        VARCHAR(255) NOT NULL UNIQUE,
        password        VARCHAR(255),
        email           VARCHAR(255),
        email_password  VARCHAR(255),
        user_agent      VARCHAR(512),

        active          BOOLEAN DEFAULT TRUE,
        locks           TEXT,
        headers         TEXT,
        cookies         TEXT,
        proxy           VARCHAR(255),
        error_msg       TEXT,
        stats           TEXT,

        last_used       DATETIME,
        _tx             TEXT,
        mfa_code        VARCHAR(50),

        PRIMARY KEY (user_id)
);


-- ============================================================
-- twitter_sources: Twitter/X accounts, hashtags, or keywords to track
-- ============================================================
CREATE TABLE twitter_sources (
        id              INTEGER NOT NULL,
        user_id         INTEGER NOT NULL,

        -- 'account' : track tweets from one account
        -- 'hashtag' : track a hashtag
        -- 'keyword' : track a search keyword
        source_type     VARCHAR(10) NOT NULL CHECK (source_type IN ('account', 'hashtag', 'keyword')),

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

        protected        BOOLEAN DEFAULT FALSE,
        verified         BOOLEAN DEFAULT FALSE,

        PRIMARY KEY (id),
        UNIQUE (user_id, twitter_id, source_type),
        FOREIGN KEY(user_id) REFERENCES accounts (user_id)
);
CREATE INDEX idx_tw_source_user_active ON twitter_sources (user_id, is_active);
CREATE INDEX idx_tw_source_next_scrape ON twitter_sources (next_scrape);


-- ============================================================
-- tweets: collected tweets
-- ============================================================
CREATE TABLE tweets (
        id              INTEGER NOT NULL,
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
        last_engagement_velocity  FLOAT,
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
        bookmark_count  INTEGER DEFAULT 0,

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
        session_id      INTEGER REFERENCES accounts(user_id) ON DELETE SET NULL,

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