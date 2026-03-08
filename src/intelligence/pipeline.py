"""
Intelligence extraction pipeline orchestrator for Phase 4.

Chains: raw_records → job_parser → field_normalizer → validation → DB save → JSON output

Input:  List of cleaned, deduplicated records from Phase 3 (data/processed/*.json)
Output: ParsedJob JSON array (data/intelligence/{date}/parsed_jobs.json)
        + Updates processed_jobs table in SQLite with scout/intelligence JSON

Rate limiting:
  Gemini free tier = 5 req/min for gemini-2.5-flash.
  _CALL_SLEEP_SECONDS (12s default) is inserted between calls to stay within quota.
  Set to 0 for paid/pro API tier. Adjust in config/settings.py or pass to IntelligencePipeline.

Record types:
  'job_posting'  → full parse + DB save + JSON output
  'non_posting'  → lightweight DB save (record_type only) so we skip re-processing next run
  'error'        → logged but not saved to DB
"""

import json
import time
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger

from src.db.db_manager import DBManager
from src.intelligence.job_parser import JobParser
from src.intelligence.field_normalizer import normalize
from src.intelligence.schemas import ParsedJob
from src.intelligence.uid_extractor import uid_from_url
from src.intelligence.validation import validate


# Seconds to sleep between Gemini calls to respect free-tier 5 req/min quota.
# Set to 0 if using a paid API tier.
_CALL_SLEEP_SECONDS = 12


class IntelligencePipeline:
    """
    Phase 4 extraction pipeline.

    Usage:
        pipeline = IntelligencePipeline()
        stats = pipeline.run(records, output_path)
    """

    def __init__(self, db: DBManager | None = None, sleep_seconds: float = _CALL_SLEEP_SECONDS):
        self.db = db or DBManager()
        self.parser = JobParser()
        self.sleep_seconds = sleep_seconds

    # ------------------------------------------------------------------
    # UID pre-filter helpers
    # ------------------------------------------------------------------

    def _load_known_uids(self, conn) -> set[str]:
        """
        Load all job_uids already in the processed_jobs table.
        Returns a set for O(1) lookups.
        """
        rows = self.db.fetch_all(
            conn,
            "SELECT job_uid FROM processed_jobs WHERE job_uid IS NOT NULL",
        )
        return {row["job_uid"] for row in rows}

    @staticmethod
    def _extract_uid(record: dict) -> str | None:
        """
        Extract the job_uid from a raw record BEFORE any LLM call.
        Uses the code-based uid_extractor (no API cost).
        """
        source_url = record.get("job_url")
        platform = record.get("platform")
        return uid_from_url(source_url, platform) or record.get("job_uid")

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def run(
        self,
        records: list[dict],
        output_path: Path | None = None,
        limit: int | None = None,
        on_stats_update: "Callable[[dict], None] | None" = None,
    ) -> dict:
        """
        Run the full intelligence extraction pipeline.

        Args:
            records:          Deduplicated records from Phase 3.
            output_path:      If provided, write ParsedJob records here INCREMENTALLY
                              (each record written immediately after parsing).
            limit:            If set, stop after processing N new records (skipped
                              known UIDs do NOT count toward this limit).
            on_stats_update:  Optional callback called after every processed record
                              with the current stats dict. Use to write a live
                              run_status.json so progress is visible mid-run.

        Returns:
            Final stats dict.
        """
        stats = {
            "total_input": len(records),
            "skipped_known": 0,
            "processed": 0,
            "job_postings": 0,
            "non_postings": 0,
            "parse_errors": 0,
            "quality_warnings": 0,
            "saved_to_db": 0,
        }

        if limit:
            logger.info(f"[intelligence] --limit {limit}: will process up to {limit} NEW records")

        gemini_call_count = 0

        # Open the output file now (if requested) so we can write incrementally.
        # _JsonArrayWriter handles [ prefix, , separators, and ] closing in finally.
        writer = _JsonArrayWriter(output_path) if output_path else None

        try:
            with self.db.connect() as conn:
                # Pre-filter: load already-processed UIDs from DB
                known_uids = self._load_known_uids(conn)
                if known_uids:
                    logger.info(
                        f"[intelligence] {len(known_uids)} UIDs already in DB — will skip if seen"
                    )

                for i, record in enumerate(records, 1):
                    title_preview = record.get("title", "no title")[:60]

                    # 0. Check if UID is already in DB → skip entirely (no LLM call)
                    uid = self._extract_uid(record)
                    if uid and uid in known_uids:
                        stats["skipped_known"] += 1
                        logger.debug(
                            f"[intelligence] {i}/{len(records)} — SKIP (known UID) {title_preview}"
                        )
                        continue

                    # Check limit AFTER skipping known UIDs (limit = new records to process)
                    if limit and gemini_call_count >= limit:
                        logger.info(
                            f"[intelligence] Reached --limit {limit} new records, stopping"
                        )
                        break

                    logger.info(f"[intelligence] {i}/{len(records)} — {title_preview}")

                    # 1. Parse with Gemini
                    parsed = self.parser.parse(record)
                    stats["processed"] += 1
                    gemini_call_count += 1

                    # 2. Handle parse errors — write immediately, continue
                    if parsed.parse_error:
                        stats["parse_errors"] += 1
                        logger.warning(
                            f"[intelligence] Parse error: {parsed.parse_error[:80]}"
                        )
                        if writer:
                            writer.write(parsed.model_dump())
                        if on_stats_update:
                            on_stats_update(stats)
                        # Rate-limit sleep still applies
                        if gemini_call_count > 0 and i < len(records) and self.sleep_seconds > 0:
                            time.sleep(self.sleep_seconds)
                        continue

                    # 3. Non-job-postings: lightweight DB save + write immediately
                    if parsed.record_type == "non_posting":
                        stats["non_postings"] += 1
                        logger.debug(
                            f"[intelligence] Non-posting: {record.get('title', '')[:50]}"
                        )
                        self._save_non_posting(conn, parsed)
                        if writer:
                            writer.write(parsed.model_dump())
                        if on_stats_update:
                            on_stats_update(stats)
                        if gemini_call_count > 0 and i < len(records) and self.sleep_seconds > 0:
                            time.sleep(self.sleep_seconds)
                        continue

                    stats["job_postings"] += 1

                    # 4. Normalize
                    parsed = normalize(parsed)

                    # 5. Validate
                    validation_result = validate(parsed)
                    if not validation_result.is_acceptable:
                        logger.warning(
                            f"[intelligence] Low quality parse "
                            f"(score={validation_result.quality_score:.2f}): "
                            f"{record.get('title', '')[:50]}"
                        )
                    if validation_result.issues:
                        stats["quality_warnings"] += len(validation_result.issues)

                    # 6. Save to DB
                    self._save_to_db(conn, parsed, validation_result.quality_score)
                    stats["saved_to_db"] += 1

                    # 7. Write to file IMMEDIATELY after saving to DB
                    if writer:
                        writer.write(parsed.model_dump())

                    # 8. Notify caller so they can update run_status.json
                    if on_stats_update:
                        on_stats_update(stats)

                    # Rate-limit sleep (between Gemini calls only)
                    if gemini_call_count > 0 and i < len(records) and self.sleep_seconds > 0:
                        time.sleep(self.sleep_seconds)

        finally:
            # Always close the JSON array — even on crash or KeyboardInterrupt.
            # This leaves a valid (possibly partial) JSON file.
            if writer:
                count = writer.close()
                logger.info(
                    f"[intelligence] Written {count} records → {output_path}"
                )

        self._log_stats(stats)
        return stats

    # ------------------------------------------------------------------
    # DB save
    # ------------------------------------------------------------------

    def _save_to_db(self, conn, job: ParsedJob, quality_score: float) -> None:
        """Save a fully parsed job posting to processed_jobs table."""
        now = datetime.now(timezone.utc).isoformat()
        self.db.insert(
            conn,
            "processed_jobs",
            {
                "job_uid": job.job_uid,
                "record_type": job.record_type or "job_posting",
                "platform": job.platform,
                "posting_type": job.posting_type,
                "source_url": job.source_url,
                "title": (job.raw_title or "")[:500],
                "company": job.scout.company_name if job.scout else None,
                "city": job.scout.city if job.scout else None,
                "country": job.scout.country if job.scout else None,
                "is_remote": int(job.scout.is_remote) if job.scout and job.scout.is_remote is not None else None,
                "date_posted": job.date_posted,
                "primary_contact": job.primary_contact,
                "scout_data": self.db.to_json(job.scout.model_dump() if job.scout else None),
                "intelligence": self.db.to_json(
                    job.intelligence.model_dump() if job.intelligence else None
                ),
                "parsed_at": now,
                "created_at": now,
            },
            or_ignore=True,
        )

    def _save_non_posting(self, conn, job: ParsedJob) -> None:
        """Save a lightweight record for non-postings to prevent re-processing."""
        now = datetime.now(timezone.utc).isoformat()
        self.db.insert(
            conn,
            "processed_jobs",
            {
                "job_uid": job.job_uid,
                "record_type": "non_posting",
                "platform": job.platform,
                "source_url": job.source_url,
                "title": (job.raw_title or "")[:500],
                "parsed_at": now,
                "created_at": now,
            },
            or_ignore=True,
        )

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------

    @staticmethod
    def _log_stats(stats: dict) -> None:
        logger.info("=" * 55)
        logger.info("[intelligence] Extraction complete")
        logger.info(f"  Total input          : {stats['total_input']}")
        logger.info(f"  Skipped (known UID)  : {stats['skipped_known']}")
        logger.info(f"  Processed            : {stats['processed']}")
        logger.info(f"  Job postings found   : {stats['job_postings']}")
        logger.info(f"  Non-postings skipped : {stats['non_postings']}")
        logger.info(f"  Parse errors         : {stats['parse_errors']}")
        logger.info(f"  Quality warnings     : {stats['quality_warnings']}")
        logger.info(f"  Saved to DB          : {stats['saved_to_db']}")
        logger.info("=" * 55)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _JsonArrayWriter:
    """
    Writes a JSON array file incrementally — one record at a time.

    Guarantees the file is valid JSON at every point:
    - After open:  ``[``
    - After each write: ``[{...},\\n{...}``   (no trailing comma)
    - After close: ``[{...},\\n{...}\\n]``

    If the process crashes before close(), the file ends without ``]``.
    run_intelligence.py's ``_safe_load_json_array()`` auto-repairs this
    by appending the missing ``]`` before reading.
    """

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._path = path
        self._file = open(path, "w", encoding="utf-8")  # noqa: SIM115
        self._file.write("[")
        self._file.flush()
        self._count = 0

    def write(self, record: dict) -> None:
        """Append one record to the JSON array and flush to disk immediately."""
        separator = "\n" if self._count == 0 else ",\n"
        self._file.write(separator)
        json.dump(record, self._file, indent=2, ensure_ascii=False, default=str)
        self._file.flush()
        self._count += 1

    def close(self) -> int:
        """Close the JSON array. Returns number of records written."""
        try:
            self._file.write("\n]" if self._count > 0 else "]")
            self._file.flush()
        finally:
            self._file.close()
        return self._count
