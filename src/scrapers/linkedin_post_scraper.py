"""
LinkedIn Post Scraper using Apify (supreme_coder/linkedin-post).

Scrapes regular LinkedIn feed posts where HRs, recruiters, and employees
share job openings as normal posts (not official job listings).

Three filtering layers:
  Layer 0 (pre-scrape): LLM-generated boolean keywords via KeywordGenerator
  Layer 1 (API level): Geo-filtered search URLs with date sorting
  Layer 2 (code level): Keyword-based job detection — only keeps posts
                         that contain hiring-related phrases

No cookies or LinkedIn login required.
"""

import re
from urllib.parse import quote

from apify_client import ApifyClient
from loguru import logger

from config.constants import Platform, PostingType
from config.settings import get_settings
from config.search_queries import SEARCH_QUERIES, LOCATIONS, LINKEDIN_GEO_IDS
from src.scrapers.base_scraper import BaseScraper
from src.scrapers.keyword_generator import KeywordGenerator
from src.scrapers.utils.html_cleaner import clean_html
from src.scrapers.utils.scraper_state import hours_since_last_run, save_last_run


# ---------------------------------------------------------------------------
# Actor config
# ---------------------------------------------------------------------------
ACTOR_ID = "Wpp1BZ6yGWjySadk3"

# LinkedIn content search base URL with geo + date + sort placeholders
SEARCH_URL_TEMPLATE = (
    "https://www.linkedin.com/search/results/content/"
    "?keywords={query}"
    "&origin=FACETED_SEARCH"
    "&sortBy=DD"
    "{geo_param}"
    "{date_param}"
)

# ---------------------------------------------------------------------------
# Job detection keywords (Layer 2) — posts must contain at least ONE to pass.
# Kept here (not in config) because these are internal detection logic,
# not user-facing search terms.
# ---------------------------------------------------------------------------
JOB_KEYWORDS_EN = [
    # Direct hiring signals
    "we're hiring", "we are hiring", "we're looking for", "we are looking for",
    "join our team", "join us", "job opening", "open position", "open role",
    "apply now", "apply here", "send your cv", "send your resume", "send cv",
    "submit your cv", "submit your resume", "drop your cv",
    "vacancy", "vacancies", "looking for a", "looking for an",
    "hiring alert", "urgent hiring", "immediate hiring", "hiring now",
    "now hiring", "career opportunity", "new opening",
    # Slightly weaker but common in Egypt
    "dm me", "dm for details", "interested comment",
]

JOB_KEYWORDS_AR = [
    # Arabic hiring phrases common in Egypt
    "مطلوب",          # "wanted/required"
    "وظائف",          # "jobs"
    "وظيفة",          # "job"
    "فرصة عمل",       # "job opportunity"
    "فرص عمل",        # "job opportunities"
    "نبحث عن",        # "we're looking for"
    "للتعيين",         # "for hiring"
    "للتوظيف",         # "for employment"
    "التقديم",         # "apply"
    "ابعت cv",        # "send cv" (franco-arabic)
    "ابعت ال cv",     # "send the cv"
    "انضم",           # "join"
    "شاغرة",          # "vacant"
    "نوظف",           # "we hire"
    "مطلوب للعمل",    # "wanted for work"
    "تقدم الان",      # "apply now"
]

# Combine all keywords into a single lowercase set for fast lookup
ALL_JOB_KEYWORDS = [kw.lower() for kw in JOB_KEYWORDS_EN + JOB_KEYWORDS_AR]


def _ts_to_iso(ts_ms: int | float | None) -> str | None:
    """Convert a Unix-millisecond timestamp to 'YYYY-MM-DD' string, or None."""
    if ts_ms is None:
        return None
    try:
        from datetime import datetime, timezone
        return datetime.fromtimestamp(int(ts_ms) / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
    except Exception:
        return None


class LinkedInPostScraper(BaseScraper):
    """
    Scrapes LinkedIn feed posts via Apify with two filtering layers:
    - Layer 1: Geo-filtered URLs (Egypt only) with date + sort
    - Layer 2: Keyword-based job detection after scraping
    """

    def __init__(self, platform_config: dict):
        super().__init__(name=Platform.LINKEDIN_POSTS.value)
        self.config = platform_config
        self._client = self._init_client()

    # ------------------------------------------------------------------
    # Client init
    # ------------------------------------------------------------------
    def _init_client(self) -> ApifyClient | None:
        """Initialize the Apify client with the API token from .env."""
        token = get_settings().apify_api_token
        if not token:
            logger.error("[linkedin_posts] APIFY_API_TOKEN not set in .env")
            return None
        return ApifyClient(token)

    # ------------------------------------------------------------------
    # Main entry point (overrides base run)
    # ------------------------------------------------------------------
    def run(self, queries: list[str], locations: list[str], **kwargs) -> list[dict]:
        """
        Override base run() because post search uses LLM-generated keywords
        and geo IDs from LINKEDIN_GEO_IDS.

        Layer 0: Generate boolean keywords via KeywordGenerator (cached).
        Layer 1: Build geo-filtered search URLs from those keywords.
        Layer 2: Post-scrape keyword filter for job detection.
        """
        if not self._client:
            logger.error("[linkedin_posts] No Apify client — skipping")
            return []

        # Layer 0: Get LLM-generated boolean keywords (cached if available)
        keyword_gen = KeywordGenerator()
        location = locations[-1] if locations else "Egypt"
        country, city = self._parse_location(location)
        keywords = keyword_gen.get_or_generate(queries, country, city)

        if not keywords:
            logger.warning("[linkedin_posts] No keywords generated — skipping")
            return []

        # Layer 1: Build geo-filtered search URLs
        search_urls = self._build_search_urls(keywords, locations)
        logger.info(
            f"[linkedin_posts] Starting Apify run — "
            f"{len(search_urls)} search URLs "
            f"(from {len(keywords)} LLM keywords × {len(locations)} locations)"
        )

        # Run Apify actor
        try:
            raw_items = self._run_actor(search_urls)
            logger.info(f"[linkedin_posts] Apify returned {len(raw_items)} raw items")
            # Save successful run timestamp (used by smart time window next run)
            save_last_run("linkedin_posts")
        except Exception as e:
            logger.error(f"[linkedin_posts] Apify run failed: {e}")
            return []

        # Normalize raw results
        normalized = []
        for item in raw_items:
            result = self._normalize_post(item)
            if result:
                normalized.append(result)

        # Layer 2: Filter by job keywords + post length
        filtered = self._filter_posts(normalized)

        logger.info(
            f"[linkedin_posts] Pipeline: {len(raw_items)} raw → "
            f"{len(normalized)} normalized → {len(filtered)} job-related"
        )
        return filtered

    # ------------------------------------------------------------------
    # Scrape (required by ABC — not used directly)
    # ------------------------------------------------------------------
    def scrape(self, query: str, location: str, **kwargs) -> list[dict]:
        """Not used directly — see run() override."""
        return []

    # ------------------------------------------------------------------
    # Layer 1: Geo-filtered URL building
    # ------------------------------------------------------------------
    def _build_search_urls(
        self, keywords: list[str], locations: list[str]
    ) -> list[str]:
        """
        Build LinkedIn search URLs with geo filters, date sorting, and recency.
        Each keyword × each geo location = one URL.
        """
        # Smart time window: if the last run was recent, use past-24h to avoid
        # re-scraping older posts and wasting Apify credits.
        date_posted = self._get_smart_date_param()
        date_param = f"&datePosted={date_posted}"

        # Collect unique geo IDs from locations
        geo_ids = set()
        for loc in locations:
            geo_id = LINKEDIN_GEO_IDS.get(loc)
            if geo_id:
                geo_ids.add(geo_id)

        # Build geo param — combine all IDs
        if geo_ids:
            ids_str = ",".join(f'"{gid}"' for gid in geo_ids)
            geo_param = f"&geoUrn=%5B{ids_str}%5D"
        else:
            geo_param = ""
            logger.warning("[linkedin_posts] No geo IDs found — searching globally")

        urls = []
        for keyword in keywords:
            encoded_kw = quote(keyword)
            url = SEARCH_URL_TEMPLATE.format(
                query=encoded_kw,
                geo_param=geo_param,
                date_param=date_param,
            )
            urls.append(url)

        return urls

    def _get_smart_date_param(self) -> str:
        """
        Decide whether to use past-24h or past-week based on when we last ran.

        Logic:
          - smart_time_window_hours = 0  → always use hours_old (manual override)
          - last run < smart_time_window_hours ago → past-24h (avoid re-scraping)
          - last run >= smart_time_window_hours ago (or never ran) → use hours_old
        """
        smart_hours = self.config.get("smart_time_window_hours", 48)
        hours_old = self.config.get("hours_old", 168)

        if smart_hours > 0:
            elapsed = hours_since_last_run("linkedin_posts")
            if elapsed is not None and elapsed < smart_hours:
                logger.info(
                    f"[linkedin_posts] Smart window: last run was {elapsed:.1f}h ago "
                    f"(< {smart_hours}h threshold) → using past-24h"
                )
                return "past-24h"
            elif elapsed is not None:
                logger.info(
                    f"[linkedin_posts] Smart window: last run was {elapsed:.1f}h ago "
                    f"(>= {smart_hours}h threshold) → using default window"
                )
            else:
                logger.info("[linkedin_posts] Smart window: no previous run found → using default window")

        # Fall back to hours_old → LinkedIn bucket
        if hours_old <= 24:
            return "past-24h"
        elif hours_old <= 168:
            return "past-week"
        else:
            return "past-month"

    @staticmethod
    def _parse_location(location: str) -> tuple[str, str | None]:
        """Parse 'Cairo, Egypt' → ('Egypt', 'Cairo')."""
        parts = [p.strip() for p in location.split(",")]
        if len(parts) >= 2:
            return parts[-1], parts[0]
        return parts[0], None

    # ------------------------------------------------------------------
    # Apify actor execution
    # ------------------------------------------------------------------
    def _run_actor(self, search_urls: list[str]) -> list[dict]:
        """Start the Apify actor, wait for completion, download results."""
        run_input = {
            "urls": search_urls,
            "maxResults": 100,   # Max posts to collect across all URLs
        }
        logger.debug(f"[linkedin_posts] Sending {len(search_urls)} URLs to actor")

        run = self._client.actor(ACTOR_ID).call(run_input=run_input)
        if not run:
            logger.error("[linkedin_posts] Actor run returned None")
            return []

        dataset_id = run.get("defaultDatasetId")
        if not dataset_id:
            logger.error("[linkedin_posts] No dataset ID in run result")
            return []

        items = list(self._client.dataset(dataset_id).iterate_items())
        return items

    # ------------------------------------------------------------------
    # Normalization
    # ------------------------------------------------------------------
    def _normalize_post(self, raw: dict) -> dict | None:
        """
        Convert a raw Apify result to our standard format.
        Handles multiple possible field names from the actor output.
        """
        text = raw.get("text") or raw.get("postText") or raw.get("content") or ""
        author = raw.get("authorName") or raw.get("author") or raw.get("authorFullName") or ""
        headline = raw.get("authorHeadline") or raw.get("authorTitle") or ""
        post_url = raw.get("postUrl") or raw.get("url") or raw.get("profileUrl") or ""
        posted_at = (
            raw.get("postedAtISO")          # Apify supreme_coder/linkedin-post: ISO datetime string
            or raw.get("postedAt")          # other actor variants
            or raw.get("postedDate")
            or raw.get("date_posted")
            or raw.get("date")
            or _ts_to_iso(raw.get("postedAtTimestamp"))  # unix ms fallback
            or ""
        )

        author_url = raw.get("authorProfileUrl") or raw.get("authorUrl") or ""

        # Skip empty/tiny posts
        if not text or len(text.strip()) < 20:
            return None

        posting_type = self._classify_posting_type(headline, text)

        # Extract unique post ID from LinkedIn activity URL
        # URL format: .../activity-7434578207858769920-xxxx?...
        # job_uid is stable, globally unique per post, used as DB primary key
        job_uid = self._extract_post_id(post_url)

        return {
            "platform": Platform.LINKEDIN_POSTS.value,
            "posting_type": posting_type.value,
            "search_query": "",
            "search_location": "",

            # Unique identifier — LinkedIn activity URN extracted from post URL.
            # Used as DB primary key to prevent storing the same post twice.
            "job_uid": job_uid,

            "title": self._extract_title(text),
            "description": clean_html(text),
            "company": self._extract_company(headline),

            "author_name": author,
            "author_headline": headline,
            "author_url": author_url,

            "job_url": post_url,
            "company_url": None,

            "city": None,
            "state": None,
            "country": None,
            "is_remote": self._check_remote(text),

            "job_type": None,
            "job_level": None,
            "company_industry": None,

            "min_amount": None,
            "max_amount": None,
            "currency": None,
            "interval": None,

            "date_posted": str(posted_at)[:10] if posted_at else None,

            "reactions": raw.get("reactionCount") or raw.get("numLikes") or 0,
            "comments": raw.get("commentCount") or raw.get("numComments") or 0,
            "reposts": raw.get("repostCount") or raw.get("numShares") or 0,

            "emails": [],
        }

    # ------------------------------------------------------------------
    # Layer 2: Job keyword detection + post filters
    # ------------------------------------------------------------------
    def _filter_posts(self, posts: list[dict]) -> list[dict]:
        """
        Apply post-specific filters:
        1. Minimum text length
        2. Job keyword detection (Layer 2) — only keep actual job posts
        """
        min_length = self.config.get("min_post_length", 50)
        require_job_kw = self.config.get("require_job_keywords", True)

        filtered = []
        for p in posts:
            desc = p.get("description", "")

            # Filter: minimum length
            if len(desc) < min_length:
                continue

            # Filter: must contain at least one hiring keyword
            if require_job_kw and not self._contains_job_keyword(desc):
                continue

            filtered.append(p)

        return filtered

    @staticmethod
    def _contains_job_keyword(text: str) -> bool:
        """Check if text contains at least one known hiring/job keyword."""
        text_lower = text.lower()
        return any(kw in text_lower for kw in ALL_JOB_KEYWORDS)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _classify_posting_type(headline: str, text: str) -> PostingType:
        """Guess the posting type based on author headline and text content."""
        headline_lower = headline.lower()
        text_lower = text.lower()

        hr_keywords = ["recruiter", "talent", "hr ", "human resource", "hiring", "people"]
        if any(kw in headline_lower for kw in hr_keywords):
            return PostingType.MANUAL_POST

        shoutout_keywords = ["my company", "our team", "we're hiring", "we are hiring", "join us"]
        if any(kw in text_lower for kw in shoutout_keywords):
            return PostingType.EMPLOYEE_SHOUTOUT

        return PostingType.MANUAL_POST

    @staticmethod
    def _extract_title(text: str) -> str:
        """Extract a title from the first line of the post text."""
        first_line = text.strip().split("\n")[0]
        if len(first_line) > 100:
            return first_line[:97] + "..."
        return first_line

    @staticmethod
    def _extract_company(headline: str) -> str | None:
        """Try to extract company name from author headline."""
        if not headline:
            return None
        for separator in [" at ", " @ ", " - "]:
            if separator in headline:
                return headline.split(separator)[-1].strip()
        return None

    @staticmethod
    def _check_remote(text: str) -> bool | None:
        """Check if the post mentions remote work."""
        text_lower = text.lower()
        remote_keywords = ["remote", "work from home", "wfh", "عن بعد"]
        if any(kw in text_lower for kw in remote_keywords):
            return True
        return None

    @staticmethod
    def _extract_post_id(url: str) -> str | None:
        """
        Extract the LinkedIn activity ID from a post URL.

        LinkedIn post URLs contain a globally unique numeric activity ID:
          https://www.linkedin.com/posts/username_...-activity-7434578207858769920-xxxx
          https://www.linkedin.com/feed/update/urn:li:groupPost:xxx-7434578207858769920

        This ID is used as the DB primary key (job_uid) to prevent duplicates.
        Returns None if no ID can be extracted (group posts or unknown URL formats).
        """
        if not url:
            return None
        # Most post URLs: activity-<numeric_id>-xxxx
        match = re.search(r"activity-([0-9]{15,20})", url)
        if match:
            return match.group(1)
        # Group posts: urn:li:groupPost:group_id-<numeric_id>
        match = re.search(r"urn:li:groupPost:[^-]+-([0-9]{15,20})", url)
        if match:
            return match.group(1)
        return None
