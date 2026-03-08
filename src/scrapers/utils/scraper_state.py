"""
Scraper run state persistence.

Saves and loads the last successful scrape timestamp for each platform
to/from disk (data/state/last_run.json).

Used by the LinkedIn post scraper to decide the time window:
  - If last scrape < 48 hours ago  → use past-24h (avoid re-scraping)
  - If last scrape >= 48 hours ago → use past-week (catch up on missed posts)
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from config.settings import DATA_DIR
from loguru import logger


# State file location
STATE_FILE = DATA_DIR / "state" / "last_run.json"


def load_last_run(platform: str) -> datetime | None:
    """
    Load the last successful run timestamp for a platform.

    Returns:
        A timezone-aware UTC datetime, or None if no record exists.
    """
    if not STATE_FILE.exists():
        return None
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        raw = data.get(platform)
        if raw:
            return datetime.fromisoformat(raw)
    except (json.JSONDecodeError, ValueError, OSError) as e:
        logger.warning(f"[scraper_state] Failed to read state file: {e}")
    return None


def save_last_run(platform: str) -> None:
    """
    Save the current UTC timestamp as the last successful run for a platform.
    Creates the state directory and file if they don't exist.
    """
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)

    # Load current state (all platforms)
    data: dict = {}
    if STATE_FILE.exists():
        try:
            data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            data = {}

    # Update this platform's timestamp
    data[platform] = datetime.now(timezone.utc).isoformat()

    STATE_FILE.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    logger.debug(f"[scraper_state] Saved last run for '{platform}'")


def hours_since_last_run(platform: str) -> float | None:
    """
    Return how many hours have passed since the last run for a platform.
    Returns None if there is no recorded run.
    """
    last = load_last_run(platform)
    if last is None:
        return None
    now = datetime.now(timezone.utc)
    diff = now - last
    return diff.total_seconds() / 3600
