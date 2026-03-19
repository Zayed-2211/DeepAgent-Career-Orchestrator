"""
Abstract base class for all scrapers.
Every scraper (job boards, LinkedIn posts, Facebook) extends this.
"""

import json
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger

from config.settings import DATA_DIR


class BaseScraper(ABC):
    """
    Abstract scraper providing shared functionality:
    - Logging setup
    - Raw data saving
    - Retry skeleton
    - Timestamped output paths
    """

    def __init__(self, name: str):
        self.name = name
        self.raw_dir = DATA_DIR / "raw"
        self.raw_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def run(self, queries: list[str], locations: list[str], **kwargs) -> list[dict]:
        """
        Execute the scraper for the given queries and locations.
        Returns a list of raw job dicts.
        
        Respects 'max_results' kwarg as a global budget across all queries.
        """
        max_results = kwargs.get("max_results")
        logger.info(f"[{self.name}] Starting scrape — {len(queries)} queries × {len(locations)} locations")
        if max_results:
            logger.info(f"[{self.name}] Global budget: {max_results} records")
        
        all_results: list[dict] = []

        for query in queries:
            for location in locations:
                # Check budget before each query
                if max_results and len(all_results) >= max_results:
                    logger.info(f"[{self.name}] Budget reached ({max_results}). Stopping early.")
                    return all_results
                
                try:
                    results = self.scrape(query=query, location=location, **kwargs)
                    logger.info(f"[{self.name}] '{query}' in '{location}' → {len(results)} results")
                    all_results.extend(results)
                    
                    # Truncate if over budget
                    if max_results and len(all_results) > max_results:
                        logger.info(f"[{self.name}] Truncating {len(all_results)} → {max_results}")
                        all_results = all_results[:max_results]
                        return all_results
                        
                except Exception as e:
                    logger.error(f"[{self.name}] Failed: '{query}' in '{location}' — {e}")

        logger.info(f"[{self.name}] Total raw results: {len(all_results)}")
        return all_results

    def save_raw(self, results: list[dict], label: str = "") -> Path:
        """Save raw results to data/raw/{date}/{platform}_{label}.json."""
        date_str = datetime.now().strftime("%Y-%m-%d")
        out_dir = self.raw_dir / date_str
        out_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%H%M%S")
        suffix = f"_{label}" if label else ""
        filename = f"{self.name}{suffix}_{timestamp}.json"
        filepath = out_dir / filename

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False, default=str)

        logger.info(f"[{self.name}] Saved {len(results)} results → {filepath}")
        return filepath

    # ------------------------------------------------------------------
    # Abstract methods (subclasses must implement)
    # ------------------------------------------------------------------
    @abstractmethod
    def scrape(self, query: str, location: str, **kwargs) -> list[dict]:
        """Scrape jobs for a single query + location combo. Returns raw dicts."""
        ...

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _safe_str(value: Any) -> str | None:
        """Convert a value to string, returning None for NaN/None."""
        if value is None:
            return None
        s = str(value)
        if s.lower() in ("nan", "none", "nat", ""):
            return None
        return s.strip()
