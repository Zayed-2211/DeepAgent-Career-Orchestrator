"""
Dev-mode budget tests for ScraperManager.run_all().
"""

import sys
import types

import pytest

# Allow importing scrapers package in environments without optional scraper deps.
if "jobspy" not in sys.modules:
    sys.modules["jobspy"] = types.SimpleNamespace(scrape_jobs=lambda **kwargs: None)
if "apify_client" not in sys.modules:
    sys.modules["apify_client"] = types.SimpleNamespace(ApifyClient=object)

from src.scrapers.scraper_manager import ScraperManager


def _job(i: int, platform: str) -> dict:
    return {
        "platform": platform,
        "title": f"Job {i}",
        "company": "ACME",
        "date_posted": f"2026-03-{(i % 28) + 1:02d}",
    }


def _manager_with_platforms(platforms: dict) -> ScraperManager:
    manager = ScraperManager()
    manager.queries_config = {
        "search_queries": ["AI Engineer", "ML Engineer"],
        "locations": ["Egypt", "Cairo, Egypt"],
    }
    manager.platforms_config = platforms
    manager.filters_config = {
        "filters": {},
        "sorting": {"sort_by": "date_posted", "sort_order": "desc"},
    }
    return manager


def test_dev_budget_skips_remaining_platforms_when_exhausted(monkeypatch):
    monkeypatch.setenv("DEV_MODE_LIMIT", "5")
    monkeypatch.setattr("src.scrapers.scraper_manager._RawSaver.save_raw", lambda self, rows, label: None)

    manager = _manager_with_platforms(
        {
            "linkedin": {"enabled": True},
            "google": {"enabled": True},
        }
    )

    calls = []

    def _fake_run(self, platform, config, queries, locations):
        calls.append((platform.value, config.get("max_results"), list(queries), list(locations)))
        if platform.value == "linkedin":
            return [_job(i, platform.value) for i in range(7)]  # intentionally exceeds cap
        return [_job(100 + i, platform.value) for i in range(2)]

    monkeypatch.setattr(ScraperManager, "_run_platform", _fake_run)

    result = manager.run_all()

    assert len(result) == 5
    assert [c[0] for c in calls] == ["linkedin"]  # google skipped after budget is exhausted
    assert calls[0][1] == 5
    assert calls[0][2] == ["AI Engineer"]
    assert calls[0][3] == ["Egypt"]


def test_dev_budget_passes_remaining_cap_to_next_platform(monkeypatch):
    monkeypatch.setenv("DEV_MODE_LIMIT", "5")
    monkeypatch.setattr("src.scrapers.scraper_manager._RawSaver.save_raw", lambda self, rows, label: None)

    manager = _manager_with_platforms(
        {
            "linkedin": {"enabled": True},
            "google": {"enabled": True},
        }
    )

    calls = []

    def _fake_run(self, platform, config, queries, locations):
        calls.append((platform.value, config.get("max_results")))
        if platform.value == "linkedin":
            return [_job(i, platform.value) for i in range(3)]
        return [_job(100 + i, platform.value) for i in range(4)]  # should be truncated to remaining=2

    monkeypatch.setattr(ScraperManager, "_run_platform", _fake_run)

    result = manager.run_all()

    assert len(result) == 5
    assert calls == [("linkedin", 5), ("google", 2)]
