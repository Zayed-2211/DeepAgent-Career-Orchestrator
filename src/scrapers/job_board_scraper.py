"""
Job board scraper using python-jobspy.
Wraps the `scrape_jobs()` function and normalizes output.
"""

import pandas as pd
from jobspy import scrape_jobs
from loguru import logger

from config.constants import Platform, PostingType
from src.scrapers.base_scraper import BaseScraper
from src.scrapers.utils.html_cleaner import clean_html


class JobBoardScraper(BaseScraper):
    """
    Scrapes official job listings from LinkedIn, Glassdoor,
    Indeed, and Google using python-jobspy.
    """

    # Map our Platform enum to python-jobspy site names
    PLATFORM_MAP = {
        Platform.LINKEDIN_JOBS: "linkedin",
        Platform.GLASSDOOR: "glassdoor",
        Platform.INDEED: "indeed",
        Platform.GOOGLE: "google",
    }

    def __init__(self, platform: Platform, platform_config: dict):
        super().__init__(name=platform.value)
        self.platform = platform
        self.site_name = self.PLATFORM_MAP[platform]
        self.config = platform_config

    def scrape(self, query: str, location: str, **kwargs) -> list[dict]:
        """
        Scrape jobs for a single query + location using python-jobspy.
        Returns a list of normalized job dicts.
        """
        results_wanted = self.config.get("results_per_query", 20)
        hours_old = self.config.get("hours_old", 72)
        distance = self.config.get("distance_miles", 50)
        fetch_desc = self.config.get("linkedin_fetch_description", False)
        country = self.config.get("country", None)

        scrape_kwargs = {
            "site_name": [self.site_name],
            "search_term": query,
            "location": location,
            "results_wanted": results_wanted,
            "hours_old": hours_old,
            "distance": distance,
            "verbose": 0,
            "description_format": "markdown",
        }

        # Platform-specific params
        if self.site_name == "linkedin" and fetch_desc:
            scrape_kwargs["linkedin_fetch_description"] = True

        if country and self.site_name in ("indeed", "glassdoor"):
            scrape_kwargs["country_indeed"] = country

        logger.debug(f"[{self.name}] scrape_jobs({query}, {location}, results={results_wanted})")

        try:
            df: pd.DataFrame = scrape_jobs(**scrape_kwargs)
        except Exception as e:
            logger.error(f"[{self.name}] python-jobspy error: {e}")
            return []

        if df.empty:
            return []

        return self._normalize_dataframe(df, query, location)

    def _normalize_dataframe(self, df: pd.DataFrame, query: str, location: str) -> list[dict]:
        """Convert a python-jobspy DataFrame to our standard dict format."""
        jobs = []

        for _, row in df.iterrows():
            job = {
                # --- Identifiers ---
                "platform": self.platform.value,
                "posting_type": PostingType.OFFICIAL_JOB.value,
                "search_query": query,
                "search_location": location,

                # --- Core fields ---
                "title": self._safe_str(row.get("title")),
                "company": self._safe_str(row.get("company")),
                "company_url": self._safe_str(row.get("company_url")),
                "job_url": self._safe_str(row.get("job_url")),

                # --- Location ---
                "city": self._safe_str(row.get("city")),
                "state": self._safe_str(row.get("state")),
                "country": self._safe_str(row.get("country")),
                "is_remote": row.get("is_remote") if pd.notna(row.get("is_remote")) else None,

                # --- Job details ---
                "description": clean_html(self._safe_str(row.get("description"))),
                "job_type": self._safe_str(row.get("job_type")),
                "job_level": self._safe_str(row.get("job_level")),
                "company_industry": self._safe_str(row.get("company_industry")),

                # --- Salary ---
                "min_amount": self._safe_float(row.get("min_amount")),
                "max_amount": self._safe_float(row.get("max_amount")),
                "currency": self._safe_str(row.get("currency")),
                "interval": self._safe_str(row.get("interval")),

                # --- Dates ---
                "date_posted": self._safe_str(row.get("date_posted")),

                # --- Contact ---
                "emails": row.get("emails") if isinstance(row.get("emails"), list) else [],
            }

            # Skip jobs with no title (invalid data)
            if not job["title"]:
                continue

            jobs.append(job)

        return jobs

    @staticmethod
    def _safe_float(value) -> float | None:
        """Convert to float, returning None for NaN/None."""
        if value is None:
            return None
        try:
            f = float(value)
            if pd.isna(f):
                return None
            return f
        except (ValueError, TypeError):
            return None
