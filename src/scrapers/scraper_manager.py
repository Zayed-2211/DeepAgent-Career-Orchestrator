"""
Scraper manager — orchestrates all scrapers, applies filters and sorting,
merges results, and saves to raw output.
"""

import copy
import os
from loguru import logger

from config.constants import Platform, SortBy, SortOrder
from config.settings import (
    load_search_queries,
    load_platforms_config,
    load_filters_config,
)
from src.scrapers.base_scraper import BaseScraper
from src.scrapers.job_board_scraper import JobBoardScraper
from src.scrapers.linkedin_post_scraper import LinkedInPostScraper


class ScraperManager:
    """
    Orchestrates all enabled scrapers:
    1. Reads config (platforms, queries, filters)
    2. Runs each enabled scraper
    3. Applies filters (title keywords, company exclusion, salary, etc.)
    4. Sorts results
    5. Saves raw output
    """

    # Map platform keys to their scraper classes
    SCRAPER_REGISTRY: dict[str, type[BaseScraper]] = {
        Platform.LINKEDIN_JOBS.value: JobBoardScraper,
        Platform.GLASSDOOR.value: JobBoardScraper,
        Platform.INDEED.value: JobBoardScraper,
        Platform.GOOGLE.value: JobBoardScraper,
        Platform.LINKEDIN_POSTS.value: LinkedInPostScraper,
    }

    # Map platform config keys to Platform enum values
    PLATFORM_KEY_MAP: dict[str, Platform] = {
        "linkedin": Platform.LINKEDIN_JOBS,
        "glassdoor": Platform.GLASSDOOR,
        "indeed": Platform.INDEED,
        "google": Platform.GOOGLE,
        "linkedin_posts": Platform.LINKEDIN_POSTS,
    }

    def __init__(self):
        self.queries_config = load_search_queries()
        # Defensive copy: run_all may inject runtime-only caps (dev mode).
        self.platforms_config = copy.deepcopy(load_platforms_config())
        self.filters_config = load_filters_config()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def run_all(self) -> list[dict]:
        """Run all enabled scrapers, apply filters/sorting, save raw output."""
        queries = self.queries_config.get("search_queries", [])
        locations = self.queries_config.get("locations", [])

        # ── Dev Mode Restrictions ──
        dev_limit_str = os.environ.get("DEV_MODE_LIMIT")
        dev_limit = int(dev_limit_str) if dev_limit_str else None

        if dev_limit is not None:
            logger.warning(
                f"[Manager] DEV MODE: Limiting to 1 query, 1 location, and global max {dev_limit} scraped records."
            )
            queries = queries[:1]
            locations = locations[:1]

        if not queries:
            logger.warning("No search queries defined in config/search_queries.json")
            return []

        all_results: list[dict] = []
        remaining_budget = dev_limit

        for platform_key, platform_config in self.platforms_config.items():
            # Skip _notes and other metadata keys
            if platform_key.startswith("_") or not isinstance(platform_config, dict):
                continue

            if not platform_config.get("enabled", False):
                logger.info(f"[{platform_key}] Skipped (disabled)")
                continue

            platform_enum = self.PLATFORM_KEY_MAP.get(platform_key)
            if not platform_enum:
                logger.debug(f"[{platform_key}] No scraper registered, skipping")
                continue

            if remaining_budget is not None and remaining_budget <= 0:
                logger.info("[Manager] DEV MODE: Budget exhausted; skipping remaining platforms.")
                break

            # Runtime config override (without mutating base config).
            effective_config = dict(platform_config)
            if remaining_budget is not None:
                effective_config["max_results"] = remaining_budget
                logger.info(
                    f"[{platform_key}] DEV MODE: Remaining global budget={remaining_budget}; "
                    f"platform cap={effective_config['max_results']}."
                )

            results = self._run_platform(platform_enum, effective_config, queries, locations)
            if remaining_budget is not None and len(results) > remaining_budget:
                logger.warning(
                    f"[{platform_key}] Returned {len(results)} results above remaining budget "
                    f"({remaining_budget}); truncating."
                )
                results = results[:remaining_budget]

            # ── SAVE IMMEDIATELY after each platform finishes ──────────────
            # This guarantees data is never lost even if a later step crashes.
            if results:
                _saver = _RawSaver()
                _saver.save_raw(results, label=platform_key)
            # ──────────────────────────────────────────────────────────────

            all_results.extend(results)
            if remaining_budget is not None:
                remaining_budget -= len(results)
                logger.info(f"[Manager] DEV MODE: Remaining budget after {platform_key}: {remaining_budget}")

        # Apply filters and sorting
        filtered = self.apply_filters(all_results)
        sorted_results = self.apply_sorting(filtered)

        # Safety net: never exceed global dev limit even if downstream behavior changes.
        if dev_limit is not None and len(sorted_results) > dev_limit:
            logger.warning(
                f"[Manager] DEV MODE safety cap: truncating final results from "
                f"{len(sorted_results)} to {dev_limit}."
            )
            sorted_results = sorted_results[:dev_limit]

        # Save merged filtered results
        if sorted_results:
            _saver = _RawSaver()
            _saver.save_raw(sorted_results, label="merged_filtered")

        logger.info(
            f"[Manager] Done — {len(all_results)} raw → "
            f"{len(filtered)} filtered → {len(sorted_results)} final"
        )
        return sorted_results

    def run_platform(self, platform_key: str) -> list[dict]:
        """Run a single platform scraper, apply filters/sorting."""
        queries = self.queries_config.get("search_queries", [])
        locations = self.queries_config.get("locations", [])

        platform_config = self.platforms_config.get(platform_key, {})
        platform_enum = self.PLATFORM_KEY_MAP.get(platform_key)

        if not platform_enum:
            logger.error(f"Unknown platform: {platform_key}")
            return []

        results = self._run_platform(platform_enum, platform_config, queries, locations)
        filtered = self.apply_filters(results)
        sorted_results = self.apply_sorting(filtered)

        # Save immediately — even if later steps fail
        if sorted_results:
            _saver = _RawSaver()
            _saver.save_raw(sorted_results, label=platform_key)

        return sorted_results

    # ------------------------------------------------------------------
    # Filtering
    # ------------------------------------------------------------------
    def apply_filters(self, jobs: list[dict]) -> list[dict]:
        """Apply all configured filters to a list of jobs."""
        filters = self.filters_config.get("filters", {})

        if not filters:
            return jobs

        filtered = jobs
        original_count = len(filtered)

        # 1. Job type filter
        job_types = _get_filter_value(filters, "job_type", [])
        if job_types:
            filtered = [
                j for j in filtered
                if j.get("job_type") and j["job_type"].lower() in [t.lower() for t in job_types]
            ]

        # 2. Remote filter
        is_remote = _get_filter_value(filters, "is_remote", None)
        if is_remote is not None:
            filtered = [j for j in filtered if j.get("is_remote") == is_remote]

        # 3. Exclude companies
        exclude_companies = [c.lower() for c in _get_filter_value(filters, "exclude_companies", [])]
        if exclude_companies:
            filtered = [
                j for j in filtered
                if not j.get("company") or j["company"].lower() not in exclude_companies
            ]

        # 4. Exclude title keywords
        exclude_keywords = [k.lower() for k in _get_filter_value(filters, "exclude_title_keywords", [])]
        if exclude_keywords:
            filtered = [
                j for j in filtered
                if not _title_contains_any(j.get("title", ""), exclude_keywords)
            ]

        # 5. Include title keywords (whitelist — if set, ONLY keep matching)
        include_keywords = [k.lower() for k in _get_filter_value(filters, "include_title_keywords", [])]
        if include_keywords:
            filtered = [
                j for j in filtered
                if _title_contains_any(j.get("title", ""), include_keywords)
            ]

        # 6. Minimum salary
        min_salary = _get_filter_value(filters, "min_salary", None)
        if min_salary is not None:
            filtered = [
                j for j in filtered
                if j.get("max_amount") is None or j["max_amount"] >= min_salary
            ]

        # 7. Require description
        if _get_filter_value(filters, "require_description", False):
            filtered = [j for j in filtered if j.get("description")]

        removed = original_count - len(filtered)
        if removed > 0:
            logger.info(f"[Filters] Removed {removed} jobs ({original_count} → {len(filtered)})")

        return filtered

    # ------------------------------------------------------------------
    # Sorting
    # ------------------------------------------------------------------
    def apply_sorting(self, jobs: list[dict]) -> list[dict]:
        """Sort jobs based on the sorting config."""
        sorting = self.filters_config.get("sorting", {})
        sort_by = _get_filter_value(sorting, "sort_by", SortBy.DATE_POSTED.value)
        sort_order = _get_filter_value(sorting, "sort_order", SortOrder.DESC.value)
        reverse = sort_order.lower() == "desc"

        def sort_key(job: dict):
            value = job.get(sort_by)
            if value is None:
                # Push None values to the end regardless of sort direction
                return (-1 if reverse else 1, "")
            return (0, value)

        return sorted(jobs, key=sort_key, reverse=reverse)

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------
    def _run_platform(
        self,
        platform: Platform,
        config: dict,
        queries: list[str],
        locations: list[str],
    ) -> list[dict]:
        """Run a single platform scraper."""
        scraper_cls = self.SCRAPER_REGISTRY.get(platform.value)
        if not scraper_cls:
            logger.warning(f"No scraper class for {platform.value}")
            return []

        # LinkedInPostScraper has a different constructor (no platform arg)
        if platform == Platform.LINKEDIN_POSTS:
            scraper = scraper_cls(platform_config=config)
        else:
            scraper = scraper_cls(platform=platform, platform_config=config)

        return scraper.run(queries=queries, locations=locations)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _get_filter_value(section: dict, key: str, default):
    """
    Extract a filter value from the config.
    Supports both flat format: {"key": value}
    and nested format: {"key": {"value": value, "_notes": "..."}}
    """
    raw = section.get(key, default)
    if isinstance(raw, dict) and "value" in raw:
        return raw["value"]
    return raw


def _title_contains_any(title: str, keywords: list[str]) -> bool:
    """Check if a job title contains any of the given keywords (case-insensitive)."""
    title_lower = title.lower()
    return any(kw in title_lower for kw in keywords)


class _RawSaver(BaseScraper):
    """Minimal scraper subclass used only for saving merged results."""

    def __init__(self):
        super().__init__(name="all_platforms")

    def scrape(self, query: str, location: str, **kwargs) -> list[dict]:
        return []
