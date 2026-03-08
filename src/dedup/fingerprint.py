"""
Deduplication fingerprinting — two-tier approach:

Tier 1 (fast path): LinkedIn job_uid
  Every LinkedIn post has a unique activity ID embedded in its URL
  (e.g. 7434578207858769920). We check this first — O(1) DB lookup.
  If found → skip immediately with zero further computation.

Tier 2 (fallback): SHA-256 content hash
  For posts where job_uid is null (other platforms or unrecognized URL),
  we compute a SHA-256 hash from the contact info + normalized title +
  normalized company name. Stored in seen_fingerprints table.

This combination handles:
  - LinkedIn dedup across runs (Tier 1)
  - Same job reshared under different URLs (Tier 1 catches different uid,
    Tier 2 catches via contact info match)
  - Non-LinkedIn platforms (Tier 2 only)
"""

import hashlib
import re
from datetime import datetime, timezone

from loguru import logger

from src.db.db_manager import DBManager


# ---------------------------------------------------------------------------
# Text normalization helpers
# ---------------------------------------------------------------------------

def _normalize(text: str | None) -> str:
    """Lowercase, collapse whitespace, strip punctuation for hashing."""
    if not text:
        return ""
    text = text.lower().strip()
    text = re.sub(r"[\s\-_.,!?]+", " ", text)
    return text


# ---------------------------------------------------------------------------
# Fingerprint computation
# ---------------------------------------------------------------------------

def compute_fingerprint(record: dict) -> str:
    """
    Compute a SHA-256 fingerprint for a raw job record.

    The fingerprint is built from the most stable, distinctive fields:
      1. primary_contact (email or phone) — strongest signal
      2. Normalized company name
      3. Normalized title (first 60 chars)

    Two posts with the same contact info, company, and similar title
    are almost certainly the same job.

    Returns: hex SHA-256 string (64 chars).
    """
    contact = _normalize(record.get("primary_contact") or "")
    company = _normalize(record.get("company") or record.get("author_name") or "")
    title = _normalize((record.get("title") or "")[:60])

    raw = f"{contact}|{company}|{title}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Deduplication checks (with DB)
# ---------------------------------------------------------------------------

class DedupChecker:
    """
    Stateful deduplication checker backed by SQLite.

    Usage:
        checker = DedupChecker(db_manager)
        with db_manager.connect() as conn:
            is_dup = checker.is_duplicate(conn, record)
            if not is_dup:
                checker.mark_seen(conn, record)
    """

    def __init__(self, db: DBManager):
        self.db = db

    def is_duplicate(self, conn, record: dict) -> bool:
        """
        Check if a record has already been seen.

        Tier 1: job_uid check (LinkedIn posts, O(1))
        Tier 2: fingerprint check (all platforms, fallback)

        Returns True if duplicate (should be skipped).
        """
        job_uid = record.get("job_uid")

        # --- Tier 1: job_uid ---
        if job_uid:
            if self.db.exists(conn, "seen_post_ids", "job_uid", job_uid):
                logger.debug(f"[dedup] Tier 1 HIT — job_uid {job_uid}")
                return True

        # --- Tier 2: content fingerprint ---
        fingerprint = compute_fingerprint(record)
        if self.db.exists(conn, "seen_fingerprints", "fingerprint", fingerprint):
            logger.debug(f"[dedup] Tier 2 HIT — fingerprint {fingerprint[:16]}…")
            return True

        return False

    def mark_seen(self, conn, record: dict) -> None:
        """
        Record a newly-processed post in both dedup tables.

        Should only be called AFTER confirming it's not a duplicate
        and AFTER successfully saving to raw_jobs.
        """
        now = datetime.now(timezone.utc).isoformat()
        job_uid = record.get("job_uid")

        # --- Tier 1: record job_uid ---
        if job_uid:
            self.db.insert(
                conn,
                "seen_post_ids",
                {
                    "job_uid": job_uid,
                    "first_seen": now,
                    "source_url": record.get("job_url"),
                },
                or_ignore=True,
            )

        # --- Tier 2: record fingerprint ---
        fingerprint = compute_fingerprint(record)
        self.db.insert(
            conn,
            "seen_fingerprints",
            {
                "fingerprint": fingerprint,
                "first_seen": now,
                "platform": record.get("platform"),
                "title": (record.get("title") or "")[:200],
            },
            or_ignore=True,
        )
