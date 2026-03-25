# Database Tables

> Source: `src/db/models.py` | Current Schema Version: `5`

## seen_post_ids — Fast UID Dedup

| Column | Type | PK | Description |
|--------|------|-----|-------------|
| `job_uid` | TEXT | ✓ | LinkedIn activity ID (e.g. `7434578207858769920`) |
| `first_seen` | TEXT | | ISO-8601 UTC datetime |
| `source_url` | TEXT | | Post URL (debugging) |

## seen_fingerprints — Content Dedup Fallback

| Column | Type | PK | Description |
|--------|------|-----|-------------|
| `fingerprint` | TEXT | ✓ | SHA-256 of `(company_name_lower + title_lower + primary_contact)` |
| `first_seen` | TEXT | | ISO-8601 UTC datetime |
| `platform` | TEXT | | Source platform |
| `title` | TEXT | | Human-readable title (debugging) |

## raw_jobs — All Scraped Records

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK AUTO | Row ID |
| `job_uid` | TEXT UNIQUE | Platform-native UID (nullable) |
| `platform` | TEXT NOT NULL | Platform name |
| `posting_type` | TEXT | Post classification |
| `source_url` | TEXT | Original URL |
| `title` | TEXT | Post title |
| `description` | TEXT | Full text |
| `company` | TEXT | Company name |
| `author_name` | TEXT | Post author |
| `author_headline` | TEXT | Author headline |
| `author_url` | TEXT | Author profile URL |
| `company_url` | TEXT | Company page URL |
| `city` | TEXT | Location city |
| `state` | TEXT | Location state |
| `country` | TEXT | Location country |
| `is_remote` | INTEGER | 0=false, 1=true, NULL=unknown |
| `date_posted` | TEXT | YYYY-MM-DD |
| `reactions` | INTEGER | Default 0 |
| `comments` | INTEGER | Default 0 |
| `reposts` | INTEGER | Default 0 |
| `phones` | TEXT | JSON array |
| `emails` | TEXT | JSON array |
| `whatsapp` | TEXT | JSON array |
| `telegram` | TEXT | JSON array |
| `primary_contact` | TEXT | Strongest contact signal |
| `fingerprint` | TEXT | SHA-256 content hash |
| `scraped_at` | TEXT NOT NULL | ISO-8601 UTC |
| `raw_json` | TEXT | Full original record as JSON |

## processed_jobs — Cleaned + AI-Parsed Records

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK AUTO | Row ID |
| `job_uid` | TEXT UNIQUE | Linked to raw_jobs.job_uid |
| `fingerprint` | TEXT | Content hash fallback |
| `record_type` | TEXT | `"job_posting"`, `"non_posting"`, or `"error"` |
| `platform` | TEXT | Platform |
| `posting_type` | TEXT | Posting type |
| `source_url` | TEXT | URL |
| `parent_raw_id` | INTEGER | FK to raw_jobs.id (split tracking) |
| `split_index` | INTEGER | 0=only child, 1..N for splits |
| `title` | TEXT | Cleaned title |
| `description` | TEXT | Cleaned single-role text |
| `company` | TEXT | Company name |
| `city` | TEXT | City |
| `country` | TEXT | Country |
| `is_remote` | INTEGER | Remote flag |
| `date_posted` | TEXT | Date |
| `primary_contact` | TEXT | Contact |
| `scout_data` | TEXT | Group 1 JSON (ScoutData) |
| `intelligence` | TEXT | Group 2 JSON (IntelligenceData) |
| `parsed_at` | TEXT | When Phase 4 processed |
| `created_at` | TEXT NOT NULL | Row creation time |

## db_meta — Schema Version Tracking

| Column | Type | PK | Description |
|--------|------|-----|-------------|
| `key` | TEXT | ✓ | e.g. `"schema_version"` |
| `value` | TEXT | | e.g. `"5"` |

## Migrations History

- **v4**: Added `record_type` column to `processed_jobs`
- **v5a**: Deduplicated existing rows (keeping earliest per `job_uid`)
- **v5b**: Added unique index `idx_processed_jobs_uid` on `job_uid`
