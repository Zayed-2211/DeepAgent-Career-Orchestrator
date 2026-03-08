"""
Tests for the scraper manager — focusing on filters and sorting logic.
These tests don't call live APIs (no network needed).
"""

import sys
from pathlib import Path

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pytest

from src.scrapers.scraper_manager import ScraperManager


# ---------------------------------------------------------------------------
# Test data
# ---------------------------------------------------------------------------
def _make_job(**overrides) -> dict:
    """Create a sample job dict with optional overrides."""
    base = {
        "platform": "linkedin",
        "posting_type": "Official_Job",
        "title": "AI Engineer",
        "company": "TechCorp",
        "city": "Cairo",
        "country": "Egypt",
        "is_remote": False,
        "description": "Looking for an AI engineer.",
        "job_type": "fulltime",
        "min_amount": 10000.0,
        "max_amount": 20000.0,
        "date_posted": "2026-03-05",
        "job_url": "https://example.com/job/1",
        "emails": [],
    }
    base.update(overrides)
    return base


SAMPLE_JOBS = [
    _make_job(title="AI Engineer", company="Google", max_amount=50000.0, date_posted="2026-03-05"),
    _make_job(title="Senior AI Engineer", company="Meta", max_amount=80000.0, date_posted="2026-03-04"),
    _make_job(title="ML Engineer", company="Amazon", max_amount=60000.0, date_posted="2026-03-03"),
    _make_job(title="Junior Data Scientist", company="Startup", max_amount=8000.0, date_posted="2026-03-02"),
    _make_job(title="AI Lead", company="Microsoft", is_remote=True, date_posted="2026-03-01"),
    _make_job(title="Python Developer", company="BadStaffing", description=None, date_posted="2026-03-06"),
    _make_job(title="Director of AI", company="Oracle", date_posted="2026-02-28"),
    _make_job(title="Machine Learning Engineer", company="Google", job_type="contract", date_posted="2026-03-04"),
]


# ---------------------------------------------------------------------------
# Filter tests
# ---------------------------------------------------------------------------
class TestFilters:
    """Tests for ScraperManager.apply_filters()."""

    def _make_manager_with_filters(self, **filter_overrides) -> ScraperManager:
        """Create a manager with custom filter config."""
        manager = ScraperManager()
        manager.filters_config = {
            "filters": {
                "job_type": [],
                "is_remote": None,
                "exclude_companies": [],
                "exclude_title_keywords": [],
                "include_title_keywords": [],
                "min_salary": None,
                "require_description": False,
                **filter_overrides,
            },
            "sorting": {"sort_by": "date_posted", "sort_order": "desc"},
        }
        return manager

    def test_no_filters_returns_all(self):
        manager = self._make_manager_with_filters()
        result = manager.apply_filters(SAMPLE_JOBS)
        assert len(result) == len(SAMPLE_JOBS)

    def test_exclude_title_keywords(self):
        manager = self._make_manager_with_filters(
            exclude_title_keywords=["Senior", "Director", "Lead"]
        )
        result = manager.apply_filters(SAMPLE_JOBS)
        titles = [j["title"] for j in result]
        assert "Senior AI Engineer" not in titles
        assert "Director of AI" not in titles
        assert "AI Lead" not in titles
        assert "AI Engineer" in titles

    def test_include_title_keywords(self):
        manager = self._make_manager_with_filters(
            include_title_keywords=["Machine Learning", "ML"]
        )
        result = manager.apply_filters(SAMPLE_JOBS)
        assert len(result) == 2  # "ML Engineer" and "Machine Learning Engineer"

    def test_exclude_companies(self):
        manager = self._make_manager_with_filters(
            exclude_companies=["BadStaffing"]
        )
        result = manager.apply_filters(SAMPLE_JOBS)
        companies = [j["company"] for j in result]
        assert "BadStaffing" not in companies

    def test_remote_filter_true(self):
        manager = self._make_manager_with_filters(is_remote=True)
        result = manager.apply_filters(SAMPLE_JOBS)
        assert all(j.get("is_remote") is True for j in result)
        assert len(result) == 1  # Only "AI Lead" is remote

    def test_min_salary(self):
        manager = self._make_manager_with_filters(min_salary=30000.0)
        result = manager.apply_filters(SAMPLE_JOBS)
        # Jobs with no salary (None) should pass, jobs below threshold should fail
        for j in result:
            if j.get("max_amount") is not None:
                assert j["max_amount"] >= 30000.0

    def test_require_description(self):
        manager = self._make_manager_with_filters(require_description=True)
        result = manager.apply_filters(SAMPLE_JOBS)
        assert all(j.get("description") is not None for j in result)
        # "Python Developer" has description=None, should be filtered out
        companies = [j["company"] for j in result]
        assert "BadStaffing" not in companies

    def test_job_type_filter(self):
        manager = self._make_manager_with_filters(job_type=["fulltime"])
        result = manager.apply_filters(SAMPLE_JOBS)
        for j in result:
            assert j.get("job_type", "").lower() == "fulltime"

    def test_combined_filters(self):
        manager = self._make_manager_with_filters(
            exclude_title_keywords=["Senior", "Director", "Lead"],
            require_description=True,
            min_salary=9000.0,
        )
        result = manager.apply_filters(SAMPLE_JOBS)
        for j in result:
            assert "senior" not in j["title"].lower()
            assert "director" not in j["title"].lower()
            assert j.get("description") is not None


# ---------------------------------------------------------------------------
# Sorting tests
# ---------------------------------------------------------------------------
class TestSorting:
    """Tests for ScraperManager.apply_sorting()."""

    def _make_manager_with_sorting(self, sort_by: str, sort_order: str) -> ScraperManager:
        manager = ScraperManager()
        manager.filters_config = {
            "filters": {},
            "sorting": {"sort_by": sort_by, "sort_order": sort_order},
        }
        return manager

    def test_sort_by_date_desc(self):
        manager = self._make_manager_with_sorting("date_posted", "desc")
        result = manager.apply_sorting(SAMPLE_JOBS)
        dates = [j["date_posted"] for j in result if j.get("date_posted")]
        assert dates == sorted(dates, reverse=True)

    def test_sort_by_company_asc(self):
        manager = self._make_manager_with_sorting("company", "asc")
        result = manager.apply_sorting(SAMPLE_JOBS)
        companies = [j["company"] for j in result]
        assert companies == sorted(companies)

    def test_sort_by_max_salary_desc(self):
        manager = self._make_manager_with_sorting("max_amount", "desc")
        result = manager.apply_sorting(SAMPLE_JOBS)
        # None salaries go to end
        salaries = [j.get("max_amount") for j in result if j.get("max_amount") is not None]
        assert salaries == sorted(salaries, reverse=True)


# ---------------------------------------------------------------------------
# HTML cleaner tests
# ---------------------------------------------------------------------------
class TestHTMLCleaner:
    """Tests for the HTML cleaning utility."""

    def test_strips_html_tags(self):
        from src.scrapers.utils.html_cleaner import clean_html
        assert clean_html("<b>Hello</b> <i>world</i>") == "Hello world"

    def test_preserves_line_breaks(self):
        from src.scrapers.utils.html_cleaner import clean_html
        result = clean_html("Line 1<br>Line 2<br/>Line 3")
        assert "Line 1" in result
        assert "Line 2" in result

    def test_returns_none_for_empty(self):
        from src.scrapers.utils.html_cleaner import clean_html
        assert clean_html(None) is None
        assert clean_html("") is None
        assert clean_html("   ") is None

    def test_decodes_entities(self):
        from src.scrapers.utils.html_cleaner import clean_html
        assert clean_html("Tom &amp; Jerry") == "Tom & Jerry"
