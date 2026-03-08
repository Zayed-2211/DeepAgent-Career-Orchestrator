"""
CLI script for running the deduplication pipeline.

Usage:
    python scripts/run_dedup.py
    python scripts/run_dedup.py --input data/raw/2026-03-07
    python scripts/run_dedup.py --input data/raw/ --output data/processed/
    python scripts/run_dedup.py --fuzzy-threshold 0.80

Arguments:
    --input   : Path to raw JSON file(s) or directory. Default: data/raw/ (latest date folder)
    --output  : Directory to save processed JSON. Default: data/processed/{date}/
    --fuzzy-threshold : MinHash LSH similarity threshold. Default: 0.75
    --dry-run : Run without writing to DB or disk (for testing pipeline logic)
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from loguru import logger

# Ensure project root is in path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.dedup.pipeline import DeduplicationPipeline
from config.settings import DATA_DIR


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_input(input_path: str | None) -> list[Path]:
    """
    Resolve --input to a list of JSON file paths.

    If a directory is given, finds all *.json files in it (recursively).
    If no input is given, uses the most recent date folder in data/raw/.
    """
    raw_dir = DATA_DIR / "raw"

    if input_path:
        p = Path(input_path)
        if p.is_file():
            return [p]
        if p.is_dir():
            files = sorted(p.rglob("*.json"))
            if not files:
                logger.error(f"No JSON files found in {p}")
                sys.exit(1)
            return files
        logger.error(f"Input path not found: {p}")
        sys.exit(1)

    # Default: most recent date folder in data/raw/
    date_dirs = sorted(
        [d for d in raw_dir.iterdir() if d.is_dir()],
        reverse=True,
    )
    if not date_dirs:
        logger.error(f"No date directories found in {raw_dir}")
        sys.exit(1)

    latest = date_dirs[0]
    files = sorted(latest.rglob("*.json"))
    logger.info(f"[run_dedup] Auto-selected input: {latest} ({len(files)} files)")
    return files


def _load_records(files: list[Path]) -> list[dict]:
    """Load and merge all JSON files into one flat list of records."""
    all_records: list[dict] = []
    for f in files:
        try:
            with open(f, encoding="utf-8") as fh:
                data = json.load(fh)
                if isinstance(data, list):
                    all_records.extend(data)
                elif isinstance(data, dict):
                    all_records.append(data)
        except Exception as e:
            logger.warning(f"[run_dedup] Could not load {f}: {e}")
    return all_records


def _resolve_output(output_path: str | None) -> Path:
    """Resolve --output to a single file path."""
    processed_dir = DATA_DIR / "processed"
    if output_path:
        p = Path(output_path)
        if p.suffix == ".json":
            return p
        # Directory given → auto-name the file
        date_str = datetime.now().strftime("%Y-%m-%d")
        return p / date_str / "deduped_jobs.json"

    date_str = datetime.now().strftime("%Y-%m-%d")
    return processed_dir / date_str / "deduped_jobs.json"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Run the deduplication pipeline on raw scraped job posts."
    )
    parser.add_argument(
        "--input",
        metavar="PATH",
        help=(
            "Path to a raw JSON file or directory. "
            "Default: most recent date folder in data/raw/"
        ),
    )
    parser.add_argument(
        "--output",
        metavar="PATH",
        help=(
            "Output file or directory path. "
            "Default: data/processed/{date}/deduped_jobs.json"
        ),
    )
    parser.add_argument(
        "--fuzzy-threshold",
        type=float,
        default=0.75,
        metavar="FLOAT",
        help=(
            "MinHash LSH similarity threshold for fuzzy dedup (0.0–1.0). "
            "Higher = stricter (fewer false positives). Default: 0.75"
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run pipeline without writing to DB or disk.",
    )
    args = parser.parse_args()

    # --- Validate fuzzy threshold ---
    if not 0.0 < args.fuzzy_threshold <= 1.0:
        logger.error("--fuzzy-threshold must be between 0.0 and 1.0")
        sys.exit(1)

    # --- Resolve paths ---
    input_files = _resolve_input(args.input)
    output_path = None if args.dry_run else _resolve_output(args.output)

    logger.info(f"[run_dedup] Loading {len(input_files)} file(s)…")
    records = _load_records(input_files)

    if not records:
        logger.error("[run_dedup] No records found. Exiting.")
        sys.exit(1)

    logger.info(f"[run_dedup] {len(records)} records loaded")
    if args.dry_run:
        logger.info("[run_dedup] DRY RUN — no DB writes, no file output")

    # --- Run pipeline ---
    pipeline = DeduplicationPipeline(fuzzy_threshold=args.fuzzy_threshold)
    stats = pipeline.run(records, output_path=output_path)

    logger.info(f"[run_dedup] Done — {stats['final_unique']} unique records")
    if output_path:
        logger.info(f"[run_dedup] Output: {output_path}")


if __name__ == "__main__":
    main()
