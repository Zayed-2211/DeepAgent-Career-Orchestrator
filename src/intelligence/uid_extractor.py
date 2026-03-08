"""
URL-based job UID extractor for each supported scraping platform.

This is deliberately code-based (not LLM) — each platform has a stable,
parseable URL pattern that gives us a platform-native unique identifier.

Supported platforms (current):
  - LinkedIn Posts (linkedin_posts):
      URL pattern: .../activity-7434510034866294785-xxxx...
      → job_uid = "linkedin_posts:7434510034866294785"

  - LinkedIn Jobs (linkedin_jobs):
      URL pattern: .../jobs/view/4152348234/...
      → job_uid = "linkedin_jobs:4152348234"

  - Wuzzuf (planned):
      URL pattern: wuzzuf.net/jobs/p/xxxxxx-slug
      → job_uid = "wuzzuf:xxxxxx"

Adding a new platform:
  1. Add an entry to PLATFORM_PATTERNS with a (platform_key, regex) pair.
  2. uid_from_url() will auto-pick it up.

Fallback (any platform):
  If no regex matches, uid_from_url() falls back to stripping tracking
  query params (utm_*, rcm, etc.) from the URL and using the clean base URL.
  This produces a stable UID for any platform with zero extra code.
  See url_as_uid_fallback() for the exact stripping logic.
"""

import re
from urllib.parse import parse_qs, urlencode, urlparse

# ---------------------------------------------------------------------------
# Platform pattern registry
# Each entry: (platform_key, compiled_regex_with_one capture group)
# ---------------------------------------------------------------------------

_PLATFORM_PATTERNS: list[tuple[str, re.Pattern]] = [
    # LinkedIn Posts — the 19-digit activity ID in the URL
    (
        "linkedin_posts",
        re.compile(r"activity-(\d{15,22})", re.IGNORECASE),
    ),
    # LinkedIn Group Posts — groupPost:GroupID-PostID format
    (
        "linkedin_posts",
        re.compile(r"groupPost:\d+-(\d{15,22})", re.IGNORECASE),
    ),
    # LinkedIn UGC Posts — ugcPost:PostID format
    (
        "linkedin_posts",
        re.compile(r"ugcPost:(\d{15,22})", re.IGNORECASE),
    ),
    # LinkedIn Jobs — the job listing numeric ID
    (
        "linkedin_jobs",
        re.compile(r"linkedin\.com/jobs(?:/view)?/(\d{7,15})", re.IGNORECASE),
    ),
    # Wuzzuf — slug/token part after /p/
    (
        "wuzzuf",
        re.compile(r"wuzzuf\.net/jobs/p/([a-zA-Z0-9\-]+)", re.IGNORECASE),
    ),
    # Indeed Egypt
    (
        "indeed",
        re.compile(r"indeed\.com/(?:viewjob|rc/clk)\?.*?jk=([a-f0-9]+)", re.IGNORECASE),
    ),
]

# Query params that are per-viewer tracking noise — strip these before using
# a URL as a fallback UID. The base URL path is stable across scrapers.
_STRIP_PARAMS = {"utm_source", "utm_medium", "utm_campaign", "rcm", "trk", "trkInfo"}


def url_as_uid_fallback(url: str, platform: str) -> str:
    """
    Build a stable UID from a URL when no named regex pattern matches.

    Strips per-viewer tracking query params (utm_*, rcm, etc.) so that
    two scrapers hitting the same post get the same UID even if their
    tracking tokens differ.

    Returns a string like "linkedin_posts:https://linkedin.com/feed/update/urn:li:..."
    """
    parsed = urlparse(url)
    # Keep only non-tracking query params
    filtered_qs = {
        k: v for k, v in parse_qs(parsed.query).items()
        if k.lower() not in _STRIP_PARAMS
    }
    clean_query = urlencode(filtered_qs, doseq=True)
    clean_url = parsed._replace(query=clean_query, fragment="").geturl()
    return f"{platform}:{clean_url}"


def uid_from_url(url: str | None, platform: str | None = None) -> str | None:
    """
    Extract a unique platform-prefixed ID from a job/post URL.

    Strategy:
      1. Try platform-specific regex patterns first (most precise).
      2. If none match, fall back to a stripped URL-based UID (always works).

    Returns a string like "linkedin_posts:7434510034866294785" or
    "linkedin_posts:https://linkedin.com/feed/update/urn:li:groupPost:..." (fallback).
    Returns None only if url is empty/None.

    Args:
        url:      The full source URL.
        platform: Hint for which platform to try first (optional).
    """
    if not url:
        return None

    platform = platform or "unknown"

    # Try platform-specific pattern first if hinted
    def _try(pat_key: str, pat: re.Pattern) -> str | None:
        m = pat.search(url)
        if m:
            return f"{pat_key}:{m.group(1)}"
        return None

    if platform:
        for key, pat in _PLATFORM_PATTERNS:
            if key == platform:
                result = _try(key, pat)
                if result:
                    return result

    # Try all patterns
    for key, pat in _PLATFORM_PATTERNS:
        result = _try(key, pat)
        if result:
            return result

    # Fallback: use cleaned URL as UID (stable across scrapers)
    return url_as_uid_fallback(url, platform)
