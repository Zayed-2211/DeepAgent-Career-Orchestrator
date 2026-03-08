"""
Shared enums and constants used across the project.
"""

from enum import Enum


# ---------------------------------------------------------------------------
# Platform identifiers
# ---------------------------------------------------------------------------
class Platform(str, Enum):
    """Supported job scraping platforms."""
    LINKEDIN_JOBS = "linkedin"
    GLASSDOOR = "glassdoor"
    INDEED = "indeed"
    GOOGLE = "google"
    LINKEDIN_POSTS = "linkedin_posts"  # Phase 2 — Apify
    WUZZUF = "wuzzuf"                  # Future — custom scraper


# ---------------------------------------------------------------------------
# Posting type tags
# ---------------------------------------------------------------------------
class PostingType(str, Enum):
    """How the job was originally posted."""
    OFFICIAL_JOB = "Official_Job"            # From job board listing
    MANUAL_POST = "Manual_Post"              # HR posted on LinkedIn feed
    EMPLOYEE_SHOUTOUT = "Employee_Shoutout"  # Employee shared a referral
    UNKNOWN = "Unknown"


# ---------------------------------------------------------------------------
# Job type filters
# ---------------------------------------------------------------------------
class JobType(str, Enum):
    """Standard job types from python-jobspy."""
    FULL_TIME = "fulltime"
    PART_TIME = "parttime"
    INTERNSHIP = "internship"
    CONTRACT = "contract"


# ---------------------------------------------------------------------------
# Sort options
# ---------------------------------------------------------------------------
class SortBy(str, Enum):
    """Available sorting options for scraped results."""
    DATE_POSTED = "date_posted"
    COMPANY = "company"
    TITLE = "title"
    MIN_SALARY = "min_amount"
    MAX_SALARY = "max_amount"


class SortOrder(str, Enum):
    """Sort direction."""
    ASC = "asc"
    DESC = "desc"


# ---------------------------------------------------------------------------
# Application method
# ---------------------------------------------------------------------------
class ApplicationMethod(str, Enum):
    """How to apply for the job."""
    URL = "url"
    EMAIL = "email"
    WHATSAPP = "whatsapp"
    PHONE = "phone"
    DM = "dm"
    UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# Default values
# ---------------------------------------------------------------------------
DEFAULT_RESULTS_PER_QUERY = 20
DEFAULT_HOURS_OLD = 72
DEFAULT_DISTANCE_MILES = 50
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 2
