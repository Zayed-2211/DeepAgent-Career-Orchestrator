"""
CLI entry point for Phase 4 intelligence extraction.

Reads cleaned job records from Phase 3 output and runs the full intelligence
extraction pipeline, saving parsed results to data/intelligence/{date}/.

Usage:
    python scripts/run_intelligence.py
    python scripts/run_intelligence.py --input data/processed/2026-03-07/deduped_jobs.json
    python scripts/run_intelligence.py --limit 10
    python scripts/run_intelligence.py --limit 5 --output data/intelligence/test_run/

Arguments:
    --input  : Path to Phase 3 output JSON file or directory. Default: most recent.
    --output : Output directory override. Default: data/intelligence/{date}/
    --limit  : Process only the first N records (useful for testing with limited API quota).

Output structure (per date folder):
    data/intelligence/{date}/
    ├── run_{HH-MM-SS}_{uid_hash}.json   ← this run's output (written incrementally)
    ├── run_{HH-MM-SS}_{uid_hash}.json   ← a previous run on the same day
    ├── parsed_jobs.json                  ← merged daily view (auto-rebuilt each run)
    ├── run_status.json                   ← live progress (overwritten per record mid-run)
    └── run_log.txt                       ← append-only run log (written even on crash)

NOTE on uid_extractor.py:
    When adding support for a new scraping platform, update
    src/intelligence/uid_extractor.py with the new URL pattern.
    Each platform needs one (platform_key, regex) entry in _PLATFORM_PATTERNS.
    See the module docstring there for full instructions.
"""

import argparse
import json
import sys
import textwrap
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from loguru import logger

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.intelligence.pipeline import IntelligencePipeline
from config.settings import DATA_DIR


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def _resolve_input(input_path: str | None) -> list[dict]:
    """Load records from the given path or the most recent processed file."""
    processed_dir = DATA_DIR / "processed"

    if input_path:
        p = Path(input_path)
        if p.is_file():
            with open(p, encoding="utf-8") as f:
                return json.load(f)
        if p.is_dir():
            files = sorted(p.rglob("*.json"), reverse=True)
            if files:
                with open(files[0], encoding="utf-8") as f:
                    return json.load(f)
        logger.error(f"Input path not found: {p}")
        sys.exit(1)

    # Default: most recent processed file
    date_dirs = sorted([d for d in processed_dir.iterdir() if d.is_dir()], reverse=True)
    if not date_dirs:
        logger.error(f"No processed data directories found in {processed_dir}")
        sys.exit(1)

    files = sorted(date_dirs[0].rglob("*.json"), reverse=True)
    if not files:
        logger.error(f"No JSON files in {date_dirs[0]}")
        sys.exit(1)

    logger.info(f"[run_intelligence] Auto-selected input: {files[0]}")
    with open(files[0], encoding="utf-8") as f:
        return json.load(f)


def _resolve_day_dir(output_override: str | None) -> Path:
    """
    Return the day folder to write into.
    If --output is passed, use that directory.
    Otherwise default to data/intelligence/{YYYY-MM-DD}/.
    """
    if output_override:
        p = Path(output_override)
        # If caller passed a .json file path, use its parent as the dir
        if p.suffix == ".json":
            return p.parent
        return p
    date_str = datetime.now().strftime("%Y-%m-%d")
    return DATA_DIR / "intelligence" / date_str


def _run_file_path(day_dir: Path) -> Path:
    """
    Build a unique per-run file path inside the day_dir.
    Format: run_{HH-MM-SS}_{6-char-hash}.json
    Example: run_14-32-07_a3f91c.json
    """
    time_str = datetime.now().strftime("%H-%M-%S")
    uid_hash = uuid4().hex[:6]
    return day_dir / f"run_{time_str}_{uid_hash}.json"


# ---------------------------------------------------------------------------
# Daily merge
# ---------------------------------------------------------------------------

def _merge_daily(day_dir: Path) -> int:
    """
    Merge all run_*.json files in day_dir into parsed_jobs.json.

    Deduplication: by job_uid (if present). Later runs overwrite earlier
    ones for the same uid. Records without a uid are always included.

    Handles partially-written files (missing closing ']') transparently
    via _safe_load_json_array().

    Returns: total merged record count.
    """
    run_files = sorted(day_dir.glob("run_*.json"))
    if not run_files:
        return 0

    # uid → record dict (later files overwrite earlier same-uid records)
    uid_map: dict[str, dict] = {}
    no_uid: list[dict] = []

    for run_file in run_files:
        records = _safe_load_json_array(run_file)
        for r in records:
            uid = r.get("job_uid")
            if uid:
                uid_map[uid] = r
            else:
                no_uid.append(r)

    merged = list(uid_map.values()) + no_uid
    merged_path = day_dir / "parsed_jobs.json"
    with open(merged_path, "w", encoding="utf-8") as f:
        json.dump(merged, f, indent=2, ensure_ascii=False, default=str)

    return len(merged)


def _safe_load_json_array(path: Path) -> list[dict]:
    """
    Load a JSON array file, gracefully handling partial writes.

    If the file ends without a closing ']' (e.g. process was Ctrl+C'd
    mid-run), attempt to auto-repair it by appending ']' in memory before
    parsing. Returns an empty list if the file can't be read at all.
    """
    try:
        text = path.read_text(encoding="utf-8").rstrip()
        if not text:
            return []
        # Auto-repair: if last non-whitespace char is not ], add it
        if not text.endswith("]"):
            logger.warning(
                f"[merge] {path.name} looks partial (no closing ']') — auto-repairing"
            )
            text = text.rstrip(",") + "\n]"
        return json.loads(text)
    except Exception as e:
        logger.warning(f"[merge] Could not read {path.name}: {e}")
        return []


# ---------------------------------------------------------------------------
# Run log
# ---------------------------------------------------------------------------

def _append_run_log(day_dir: Path, run_file: Path, stats: dict, started_at: datetime) -> None:
    """
    Append a plain-text block to data/intelligence/{date}/run_log.txt.

    Each block contains:
      - timestamp and run file name
      - full stats (total, job postings, non-postings, errors, warnings, saved to DB)

    Called in a finally block so the log is always written, even on crash.
    """
    finished_at = datetime.now(timezone.utc)
    duration_s = (finished_at - started_at).total_seconds()

    block = textwrap.dedent(f"""
    ══════════════════════════════════════════════════
    Run  : {run_file.name}
    Start: {started_at.strftime("%Y-%m-%d %H:%M:%S UTC")}
    End  : {finished_at.strftime("%Y-%m-%d %H:%M:%S UTC")}
    Time : {duration_s:.1f}s
    ──────────────────────────────────────────────────
    Input records      : {stats.get('total_input', '?')}
    Skipped (known UID): {stats.get('skipped_known', '?')}
    Processed          : {stats.get('processed', '?')}
    ├─ Job postings    : {stats.get('job_postings', '?')}
    ├─ Non-postings    : {stats.get('non_postings', '?')}
    └─ Parse errors    : {stats.get('parse_errors', '?')}
    Quality warnings   : {stats.get('quality_warnings', '?')}
    Saved to DB        : {stats.get('saved_to_db', '?')}
    ══════════════════════════════════════════════════
    """).lstrip()

    log_path = day_dir / "run_log.txt"
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(block)

    logger.info(f"[run_intelligence] Run log updated → {log_path}")


def _make_status_updater(day_dir: Path, run_file: Path, started_at: datetime):
    """
    Returns a callback that overwrites run_status.json after every parsed record.

    The file is human-readable mid-run — you can open it anytime to see
    live progress without waiting for the run to finish.
    """
    status_path = day_dir / "run_status.json"

    def _update(stats: dict) -> None:
        elapsed = (datetime.now(timezone.utc) - started_at).total_seconds()
        status = {
            "run_file": run_file.name,
            "started_at": started_at.strftime("%Y-%m-%d %H:%M:%S UTC"),
            "elapsed_seconds": round(elapsed, 1),
            "status": "running",
            **stats,
        }
        try:
            with open(status_path, "w", encoding="utf-8") as f:
                json.dump(status, f, indent=2)
        except Exception:  # never crash the pipeline over a status write
            pass

    return _update, status_path


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Run Phase 4 intelligence extraction on processed job posts."
    )
    parser.add_argument(
        "--input",
        metavar="PATH",
        help="Path to Phase 3 output JSON file or directory. Default: most recent processed file.",
    )
    parser.add_argument(
        "--output",
        metavar="DIR",
        help=(
            "Output directory override. Default: data/intelligence/{date}/. "
            "Each run writes a unique run_*.json inside — never overwrites existing files."
        ),
    )
    parser.add_argument(
        "--limit",
        type=int,
        metavar="N",
        help="Process only the first N records (e.g. 5 for API quota testing).",
    )
    args = parser.parse_args()

    started_at = datetime.now(timezone.utc)

    logger.info("[run_intelligence] Loading records…")
    records = _resolve_input(args.input)

    if not records:
        logger.error("[run_intelligence] No records found. Exiting.")
        sys.exit(1)

    logger.info(f"[run_intelligence] {len(records)} records loaded")

    # Determine output paths
    day_dir = _resolve_day_dir(args.output)
    day_dir.mkdir(parents=True, exist_ok=True)
    run_path = _run_file_path(day_dir)

    logger.info(f"[run_intelligence] Run output → {run_path}")

    # Live status writer — overwrites run_status.json after every record
    on_stats_update, status_path = _make_status_updater(day_dir, run_path, started_at)
    logger.info(f"[run_intelligence] Live status → {status_path}")

    stats = {}
    try:
        # Run the pipeline (writes each record to file immediately)
        pipeline = IntelligencePipeline()
        stats = pipeline.run(
            records,
            output_path=run_path,
            limit=args.limit,
            on_stats_update=on_stats_update,
        )
    finally:
        # Mark status file as finished (or interrupted) — always runs
        elapsed = (datetime.now(timezone.utc) - started_at).total_seconds()
        final_status = {
            "run_file": run_path.name,
            "started_at": started_at.strftime("%Y-%m-%d %H:%M:%S UTC"),
            "elapsed_seconds": round(elapsed, 1),
            "status": "done" if stats.get("processed") else "interrupted",
            **stats,
        }
        try:
            with open(status_path, "w", encoding="utf-8") as f:
                json.dump(final_status, f, indent=2)
        except Exception:
            pass

        # Rebuild merged daily view (handles partial files from crashes)
        total_merged = _merge_daily(day_dir)
        logger.info(
            f"[run_intelligence] Daily merged view rebuilt → "
            f"{day_dir / 'parsed_jobs.json'} ({total_merged} total unique records)"
        )

        # Append to run log — always, even on crash
        _append_run_log(day_dir, run_path, stats, started_at)

    logger.info(
        f"[run_intelligence] Done — "
        f"{stats.get('job_postings', 0)} job postings | "
        f"{stats.get('non_postings', 0)} non-postings | "
        f"{stats.get('parse_errors', 0)} errors"
    )


if __name__ == "__main__":
    main()
