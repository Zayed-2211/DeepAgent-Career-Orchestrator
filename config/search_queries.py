"""
Controls WHAT the scraper searches for — SINGLE SOURCE OF TRUTH for locations.
Edit anytime — no code changes needed.

Tips:
- Keep queries specific. 'AI Engineer' works better than just 'AI'.
- More queries = more results but slower scraping.
- Each query runs once per location (queries × locations = total searches).

Example search queries:
- "AI Engineer", "Machine Learning Engineer", "Data Scientist", "Python Developer",
  "NLP Engineer", "Computer Vision Engineer", "Full Stack Developer"

Example locations:
- "Egypt", "Cairo, Egypt", "Alexandria, Egypt", "Remote", "Dubai, UAE"
"""

# ---------------------------------------------------------------------------
# Search queries — used by job board scraper (Phase 1)
# ---------------------------------------------------------------------------
SEARCH_QUERIES = [
    "AI Engineer",
    "Artificial Intelligence Engineer",
    "Machine Learning Engineer",
    "Generative AI Engineer",
    "AI Automation Engineer",
    "AI Specialist"
]

# ---------------------------------------------------------------------------
# Locations — SINGLE SOURCE OF TRUTH shared by ALL scrapers
# Both job board scraper and LinkedIn post scraper read from here.
# ---------------------------------------------------------------------------
LOCATIONS = [
    "Egypt",
    "Cairo, Egypt"
]

# ---------------------------------------------------------------------------
# LinkedIn Geo IDs — used by the LinkedIn post scraper to build geo-filtered URLs.
# LinkedIn uses numeric IDs for location filtering. We map our LOCATIONS to these IDs.
# To find a geo ID: search on LinkedIn → apply location filter → check URL for geoUrn value.
#
# Common geo IDs:
#   Egypt (country):      101620260
#   Cairo:                100640489
#   Alexandria:           100786530
#   United Arab Emirates: 104305776
#   Saudi Arabia:         100459316
#   Remote:               (no geo ID — use keywords instead)
# ---------------------------------------------------------------------------
LINKEDIN_GEO_IDS = {
    "Egypt": "101620260",
    "Cairo, Egypt": "100640489",
}

# ---------------------------------------------------------------------------
# LinkedIn post search keywords
# ---------------------------------------------------------------------------
# REMOVED: POST_SEARCH_KEYWORDS was a static list of hiring-intent phrases.
# It has been replaced by the LLM KeywordGenerator (src/scrapers/keyword_generator.py)
# which generates 30 targeted boolean search queries using Gemini.
#
# The keyword generator reads SEARCH_QUERIES and LOCATIONS from this file
# and produces cached, optimized keywords automatically.
# See: scripts/generate_keywords.py for manual generation/preview.
# ---------------------------------------------------------------------------

