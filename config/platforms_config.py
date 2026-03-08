"""
Controls WHICH platforms are active and HOW each one behaves.

Global Options:
- enabled: True = scraper runs for this platform, False = skipped entirely.
- results_per_query: Max jobs returned per search query. Higher = slower but more results. Range: 1-100.
- hours_old: Only return jobs posted within the last N hours. 24 = last day, 72 = last 3 days, 168 = last week.
- distance_miles: Radius around the location in miles. 10 = very local, 50 = regional, 100 = wide area.
- country: Country filter for Indeed/Glassdoor. Must match exactly: "Egypt", "USA", "UK", etc.

Tips:
- Start with only LinkedIn enabled. Add others once the pipeline is working well.
"""

PLATFORMS_CONFIG = {
    "linkedin": {
        # Main job board scraper. Best results for tech jobs.
        # linkedin_fetch_description: If true, fetches full job description from LinkedIn (slower but much better data).
        "enabled": True,
        "results_per_query": 20,
        "hours_old": 72,
        "distance_miles": 20,
        "linkedin_fetch_description": True,
        "country": "Egypt"
    },
    
    "glassdoor": {
        # Good for salary data and company reviews. May have fewer Egyptian listings than LinkedIn.
        "enabled": False,
        "results_per_query": 15,
        "hours_old": 72,
        "distance_miles": 20,
        "country": "Egypt"
    },
    
    "indeed": {
        # Large job board. Has limitations: can only filter by ONE of: hours_old, job_type, or easy_apply.
        "enabled": False,
        "results_per_query": 15,
        "hours_old": 72,
        "distance_miles": 20,
        "country": "Egypt"
    },
    
    "google": {
        # Google Jobs aggregator. No distance/country filter — uses google_search_term for filtering instead.
        "enabled": False,
        "results_per_query": 15,
        "hours_old": 72
    },
    
    "linkedin_posts": {
        # Phase 2 — Scrapes regular LinkedIn feed posts (not job listings) using Apify.
        # Uses the actor: supreme_coder/linkedin-post ($1 per 1000 posts, no cookies needed).
        #
        # Keywords come from the LLM KeywordGenerator (not static config).
        # Geo IDs and job titles come from config/search_queries.py (single source of truth).
        # This config only controls actor behavior and post-scrape filtering.
        #
        # actor_id:
        #   Apify actor identifier. Do NOT change unless you switch actors.
        #
        # hours_old:
        #   Default time window sent to LinkedIn search. LinkedIn only supports these fixed buckets:
        #     24  → datePosted=past-24h   (real-time, sparse results)
        #     168 → datePosted=past-week  (up to 7 days, best balance)
        #     720 → datePosted=past-month (30 days, broad but may include stale posts)
        #   NOTE: This is only used if smart_time_window is disabled.
        #
        # smart_time_window_hours:
        #   If the last scrape was LESS than this many hours ago, the scraper
        #   automatically switches to past-24h to avoid re-scraping the same posts.
        #   If the last scrape was OLDER than this threshold (or never ran), it
        #   falls back to hours_old above (past-week by default).
        #   Set to 0 to disable smart switching entirely (always use hours_old).
        #   Recommended: 48 hours — gives a buffer for daily runs.
        #
        # min_post_length:
        #   Skip posts shorter than this many characters. Filters "Congratulations!" noise.
        #   Range: 30 (loose) to 200 (strict, may miss short posts like "We're hiring! DM me")
        #
        # exclude_reshares:
        #   If True, drops reshared content. Keeps only original posts.
        #   Recommended: True (reshares rarely have new job info)
        #
        # require_job_keywords:
        #   If True, Layer 2 filter — only keeps posts that contain at least one
        #   hiring-related keyword (defined in linkedin_post_scraper.py).
        #   Recommended: False during initial testing, True for production runs.
        "enabled": True,
        "actor_id": "Wpp1BZ6yGWjySadk3",
        "hours_old": 168,
        "smart_time_window_hours": 48,
        "min_post_length": 30,
        "exclude_reshares": True,
        "require_job_keywords": False
    }
}
