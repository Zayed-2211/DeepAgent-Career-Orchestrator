"""
Scout node for pipeline mode.

Runs the scraper manager and stores raw records in state for deduplication.
Mock mode still exists as a fallback path, but run_agent pipeline mode now
clears mock env vars so normal pipeline runs stay live.
"""

import json
import os
from pathlib import Path

from loguru import logger

from config.settings import DATA_DIR
from src.agent.intelligence_artifacts import append_run_log, update_run_status
from src.agent.state import AgentState


def _load_mock_records() -> list[dict]:
    """Load scraped records from a local JSON file for explicit mock runs only."""
    custom_path = os.environ.get("MOCK_SCRAPER_FILE")
    if custom_path:
        path = Path(custom_path)
    else:
        raw_dir = DATA_DIR / "raw"
        files = sorted(raw_dir.glob("**/*.json"), key=lambda f: f.stat().st_mtime, reverse=True)
        if not files:
            logger.warning("[scout] No raw JSON files found in data/raw/ for mock mode.")
            return []
        path = files[0]

    logger.info(f"[scout] MOCK MODE - loading from: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
        logger.warning(f"[scout] Mock file is not a JSON array: {path}")
        return []
    except (json.JSONDecodeError, OSError) as exc:
        logger.error(f"[scout] Failed to load mock file {path}: {exc}")
        return []


def scout_node(state: AgentState) -> AgentState:
    """
    Run scraping and populate state["raw_records"].

    State out: raw_records, routing ("success" or "error")
    """
    use_mock = os.environ.get("MOCK_SCRAPER", "0") == "1"

    if use_mock:
        logger.info("[scout] Running in MOCK mode (MOCK_SCRAPER=1).")
        records = _load_mock_records()
        if not records:
            logger.warning("[scout] Mock returned 0 records - treating as success with empty list.")
        logger.info(f"[scout] Mock loaded {len(records)} record(s).")
        append_run_log(f"scout complete | mode=mock | raw_records={len(records)}")
        update_run_status("running", {"stage": "scout", "raw_records": len(records), "source": "mock"})
        return {
            **state,
            "raw_records": records,
            "routing": "success",
        }

    try:
        # Import here to avoid loading optional scraping deps at module import time.
        from src.scrapers.scraper_manager import ScraperManager

        logger.info("[scout] Starting scraper pipeline...")
        manager = ScraperManager()
        records = manager.run_all()

        total = len(records)
        logger.info(f"[scout] Scrape complete - {total} raw record(s) collected.")
        append_run_log(f"scout complete | mode=live | raw_records={total}")
        update_run_status("running", {"stage": "scout", "raw_records": total, "source": "live"})

        return {
            **state,
            "raw_records": records,
            "routing": "success",
            "pipeline_stats": {
                **state.get("pipeline_stats", {}),
                "total": total,
            },
        }

    except Exception as exc:
        err = str(exc)[:300]
        logger.error(f"[scout] Scraper failed: {err}")
        append_run_log(f"scout failed | error={err}")
        update_run_status("error", {"stage": "scout", "error": err})
        return {
            **state,
            "raw_records": [],
            "routing": "error",
            "error": f"scout_node failed: {err}",
        }


def route_after_scout(state: AgentState) -> str:
    """Conditional edge: success or error."""
    return state.get("routing", "error")
