"""
Shared pytest fixtures.
"""

import pytest
from pathlib import Path


@pytest.fixture
def fixtures_dir() -> Path:
    """Path to the test fixtures directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_job() -> dict:
    """A sample normalized job dict for testing."""
    return {
        "platform": "linkedin",
        "posting_type": "Official_Job",
        "search_query": "AI Engineer",
        "search_location": "Egypt",
        "title": "AI Engineer",
        "company": "TechCorp",
        "company_url": "https://techcorp.com",
        "job_url": "https://linkedin.com/jobs/view/123",
        "city": "Cairo",
        "state": None,
        "country": "Egypt",
        "is_remote": False,
        "description": "We are looking for an AI Engineer with experience in LLMs and RAG.",
        "job_type": "fulltime",
        "job_level": "Entry level",
        "company_industry": "Technology",
        "min_amount": 15000.0,
        "max_amount": 25000.0,
        "currency": "EGP",
        "interval": "monthly",
        "date_posted": "2026-03-05",
        "emails": ["hr@techcorp.com"],
    }
