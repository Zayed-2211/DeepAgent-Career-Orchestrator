"""
SQLite table schemas for the local database.

Tables:
  seen_post_ids      — Fast O(1) dedup for LinkedIn posts via job_uid
  seen_fingerprints  — SHA-256 content dedup fallback for non-LinkedIn posts
  raw_jobs           — All raw scraped records (pre-dedup)
  processed_jobs     — Cleaned, deduplicated, and AI-parsed records

Migration:
  Call initialize_db(conn) on startup. Safe to call multiple times
  (uses CREATE TABLE IF NOT EXISTS). Schema versioning is tracked in db_meta.

Phase 9 note:
  When migrating to Supabase (PostgreSQL), these DDL strings map 1:1.
  Replace `INTEGER PRIMARY KEY AUTOINCREMENT` with `BIGSERIAL PRIMARY KEY`
  and `TEXT` with `TEXT` (identical). BLOB columns become `BYTEA`.
"""


# ---------------------------------------------------------------------------
# DDL statements (CREATE TABLE IF NOT EXISTS — idempotent)
# ---------------------------------------------------------------------------

CREATE_SEEN_POST_IDS = """
CREATE TABLE IF NOT EXISTS seen_post_ids (
    -- LinkedIn activity ID (e.g. 7434578207858769920).
    -- Globally unique per LinkedIn post.
    -- Primary dedup key — checked before any other processing.
    job_uid     TEXT PRIMARY KEY,

    first_seen  TEXT NOT NULL,   -- ISO-8601 UTC datetime of first encounter
    source_url  TEXT             -- Optional: post URL for debugging
);
"""

CREATE_SEEN_FINGERPRINTS = """
CREATE TABLE IF NOT EXISTS seen_fingerprints (
    -- SHA-256 hash of (company_name_lower + title_lower + primary_contact).
    -- Fallback dedup for posts where job_uid is null (non-LinkedIn or unknown URL).
    fingerprint TEXT PRIMARY KEY,

    first_seen  TEXT NOT NULL,
    platform    TEXT,
    title       TEXT             -- For human-readable debugging
);
"""

CREATE_RAW_JOBS = """
CREATE TABLE IF NOT EXISTS raw_jobs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Platform-native unique ID (NULL if URL format unrecognized)
    job_uid         TEXT UNIQUE,

    platform        TEXT NOT NULL,
    posting_type    TEXT,
    source_url      TEXT,

    title           TEXT,
    description     TEXT,
    company         TEXT,
    author_name     TEXT,
    author_headline TEXT,
    author_url      TEXT,
    company_url     TEXT,

    city            TEXT,
    state           TEXT,
    country         TEXT,
    is_remote       INTEGER,     -- 0 = false, 1 = true, NULL = unknown

    date_posted     TEXT,        -- YYYY-MM-DD string or null
    reactions       INTEGER DEFAULT 0,
    comments        INTEGER DEFAULT 0,
    reposts         INTEGER DEFAULT 0,

    -- Extracted contact info (JSON array as TEXT)
    phones          TEXT DEFAULT '[]',
    emails          TEXT DEFAULT '[]',
    whatsapp        TEXT DEFAULT '[]',
    telegram        TEXT DEFAULT '[]',
    primary_contact TEXT,        -- Strongest signal (email > phone > etc.)

    fingerprint     TEXT,        -- SHA-256 content hash (dedup fallback)

    scraped_at      TEXT NOT NULL,  -- ISO-8601 UTC datetime
    raw_json        TEXT            -- Full original record as JSON (for debugging)
);
"""

CREATE_PROCESSED_JOBS = """
CREATE TABLE IF NOT EXISTS processed_jobs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Linked back to raw_jobs.job_uid (or fingerprint if uid is null)
    -- UNIQUE so that or_ignore=True on insert correctly skips duplicates.
    job_uid         TEXT UNIQUE,
    fingerprint     TEXT,

    -- Record classification: 'job_posting' | 'non_posting' | 'error'
    record_type     TEXT DEFAULT 'job_posting',

    platform        TEXT,
    posting_type    TEXT,
    source_url      TEXT,

    -- Split metadata: if a raw post had N roles, each becomes a separate processed_job
    parent_raw_id   INTEGER,     -- FK to raw_jobs.id
    split_index     INTEGER DEFAULT 0,  -- 0 = only child, 1..N for splits

    -- Cleaned fields
    title           TEXT,
    description     TEXT,        -- Cleaned text (1 role only)
    company         TEXT,
    city            TEXT,
    country         TEXT,
    is_remote       INTEGER,
    date_posted     TEXT,

    primary_contact TEXT,

    -- Phase 4: AI-parsed intelligence (stored as JSON)
    scout_data      TEXT,        -- Group 1 JSON (ScoutData Pydantic model)
    intelligence    TEXT,        -- Group 2 JSON (IntelligenceData Pydantic model)

    parsed_at       TEXT,        -- When Phase 4 processed this record
    created_at      TEXT NOT NULL
);
"""

CREATE_DB_META = """
CREATE TABLE IF NOT EXISTS db_meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""

# ---------------------------------------------------------------------------
# All tables in creation order (respects foreign key dependencies)
# ---------------------------------------------------------------------------
ALL_TABLES = [
    CREATE_DB_META,
    CREATE_SEEN_POST_IDS,
    CREATE_SEEN_FINGERPRINTS,
    CREATE_RAW_JOBS,
    CREATE_PROCESSED_JOBS,
]

# ---------------------------------------------------------------------------
# Incremental migrations (idempotent — safe to re-run on every startup)
# Each entry is a SQL statement that adds a missing column / index.
# ---------------------------------------------------------------------------
MIGRATIONS = [
    # v4: added record_type to processed_jobs
    "ALTER TABLE processed_jobs ADD COLUMN record_type TEXT DEFAULT 'job_posting'",
    # v5a: remove duplicate job_uid rows (keep earliest insert per uid) before adding unique index
    """
    DELETE FROM processed_jobs
    WHERE id NOT IN (
        SELECT MIN(id) FROM processed_jobs
        WHERE job_uid IS NOT NULL
        GROUP BY job_uid
    ) AND job_uid IS NOT NULL
    """,
    # v5b: unique index on processed_jobs.job_uid (prevents duplicate rows on re-run)
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_processed_jobs_uid ON processed_jobs (job_uid) WHERE job_uid IS NOT NULL",
]


def initialize_db(conn) -> None:
    """
    Create all tables if they don't exist and apply incremental migrations.
    Safe to call on every startup — fully idempotent.

    Args:
        conn: An open sqlite3 connection.
    """
    cursor = conn.cursor()
    for ddl in ALL_TABLES:
        cursor.execute(ddl)

    # Apply incremental migrations (silently skip if column already exists)
    for migration in MIGRATIONS:
        try:
            cursor.execute(migration)
        except Exception:
            pass  # Column already exists — safe to ignore

    # Seed schema version
    cursor.execute(
        "INSERT OR REPLACE INTO db_meta (key, value) VALUES (?, ?)",
        ("schema_version", "5"),
    )
    conn.commit()
