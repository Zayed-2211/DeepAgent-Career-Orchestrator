"""
Deduplication pipeline orchestrator.

Chains all dedup steps in order:

  1. Contact extraction (phones, emails, WhatsApp, Telegram)
  2. Tier 1 dedup: job_uid fast path (LinkedIn activity ID)
  3. Tier 2 dedup: SHA-256 content fingerprint
  4. Multi-role splitting (Gemini Flash — only for multi-role posts)
  5. Fuzzy near-duplicate detection (MinHash LSH — per-run in-memory)
  6. Save unique records to DB (raw_jobs + processed_jobs)

Input:  List of raw post dicts (from data/raw/*.json)
Output: List of clean, unique, split post dicts (saved to data/processed/)
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger

from src.db.db_manager import DBManager
from src.dedup.contact_extractor import extract_all, primary_contact
from src.dedup.fingerprint import DedupChecker, compute_fingerprint
from src.dedup.fuzzy_dedup import FuzzyDedup
from src.dedup.multi_job_splitter import MultiJobSplitter


class DeduplicationPipeline:
    """
    Full deduplication and cleaning pipeline for raw scraped records.

    Usage:
        pipeline = DeduplicationPipeline()
        stats = pipeline.run(raw_records, output_path)
    """

    def __init__(self, db: DBManager | None = None, fuzzy_threshold: float = 0.75):
        self.db = db or DBManager()
        self.splitter = MultiJobSplitter()
        self.fuzzy_threshold = fuzzy_threshold

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def run(self, records: list[dict], output_path: Path | None = None) -> dict:
        """
        Run the full dedup pipeline on a list of raw records.

        Args:
            records:     Raw scraped post dicts.
            output_path: If provided, save clean output as JSON here.

        Returns:
            Stats dict with counts for each pipeline stage.
        """
        stats = {
            "total_input": len(records),
            "uid_dupes_skipped": 0,
            "fingerprint_dupes_skipped": 0,
            "splits_generated": 0,
            "fuzzy_dupes_skipped": 0,
            "saved_to_db": 0,
            "final_unique": 0,
        }

        fuzzy = FuzzyDedup(threshold=self.fuzzy_threshold)
        output_records: list[dict] = []

        with self.db.connect() as conn:
            checker = DedupChecker(self.db)

            for record in records:
                # -- Step 1: Extract contact info ---------------------------
                text = record.get("description") or ""
                contacts = extract_all(text)
                record["phones"] = contacts["phones"]
                record["emails"] = contacts["emails"] or record.get("emails", [])
                record["whatsapp"] = contacts["whatsapp"]
                record["telegram"] = contacts["telegram"]
                record["primary_contact"] = primary_contact(contacts)

                # -- Step 2 & 3: Tier 1 + Tier 2 dedup ---------------------
                if checker.is_duplicate(conn, record):
                    uid = record.get("job_uid")
                    if uid and self.db.exists(conn, "seen_post_ids", "job_uid", uid):
                        stats["uid_dupes_skipped"] += 1
                    else:
                        stats["fingerprint_dupes_skipped"] += 1
                    continue

                # Mark as seen (both tiers)
                checker.mark_seen(conn, record)

                # -- Step 4: Multi-role splitting ---------------------------
                split_records = self.splitter.split(record)
                if len(split_records) > 1:
                    stats["splits_generated"] += len(split_records) - 1

                # -- Step 5 & 6: Fuzzy dedup + save for each split ----------
                for split in split_records:
                    if fuzzy.is_near_duplicate(split):
                        stats["fuzzy_dupes_skipped"] += 1
                        continue

                    fuzzy.add(split)

                    # Save to raw_jobs table
                    self._save_raw(conn, split)
                    stats["saved_to_db"] += 1
                    output_records.append(split)

        stats["final_unique"] = len(output_records)

        # Save output JSON if requested
        if output_path and output_records:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(output_records, f, indent=2, ensure_ascii=False, default=str)
            logger.info(f"[pipeline] Saved {len(output_records)} records → {output_path}")

        self._log_stats(stats)
        return stats

    # ------------------------------------------------------------------
    # DB helpers
    # ------------------------------------------------------------------

    def _save_raw(self, conn, record: dict) -> None:
        """Save a single cleaned record to the raw_jobs table."""
        now = datetime.now(timezone.utc).isoformat()
        self.db.insert(
            conn,
            "raw_jobs",
            {
                "job_uid": record.get("job_uid"),
                "platform": record.get("platform", "unknown"),
                "posting_type": record.get("posting_type"),
                "source_url": record.get("job_url"),
                "title": (record.get("title") or "")[:500],
                "description": record.get("description"),
                "company": record.get("company"),
                "author_name": record.get("author_name"),
                "author_headline": record.get("author_headline"),
                "author_url": record.get("author_url"),
                "city": record.get("city"),
                "state": record.get("state"),
                "country": record.get("country"),
                "is_remote": int(record["is_remote"]) if record.get("is_remote") is not None else None,
                "date_posted": record.get("date_posted"),
                "reactions": record.get("reactions", 0) or 0,
                "comments": record.get("comments", 0) or 0,
                "reposts": record.get("reposts", 0) or 0,
                "phones": self.db.to_json(record.get("phones", [])),
                "emails": self.db.to_json(record.get("emails", [])),
                "whatsapp": self.db.to_json(record.get("whatsapp", [])),
                "telegram": self.db.to_json(record.get("telegram", [])),
                "primary_contact": record.get("primary_contact"),
                "fingerprint": compute_fingerprint(record),
                "scraped_at": now,
                "raw_json": self.db.to_json(record),
            },
            or_ignore=True,
        )

    @staticmethod
    def _log_stats(stats: dict) -> None:
        """Print a clean stats summary."""
        logger.info("=" * 50)
        logger.info("[pipeline] Deduplication complete")
        logger.info(f"  Input records         : {stats['total_input']}")
        logger.info(f"  job_uid dupes skipped : {stats['uid_dupes_skipped']}")
        logger.info(f"  fingerprint dupes     : {stats['fingerprint_dupes_skipped']}")
        logger.info(f"  multi-role splits     : +{stats['splits_generated']}")
        logger.info(f"  fuzzy dupes skipped   : {stats['fuzzy_dupes_skipped']}")
        logger.info(f"  Saved to DB           : {stats['saved_to_db']}")
        logger.info(f"  Final unique records  : {stats['final_unique']}")
        logger.info("=" * 50)
