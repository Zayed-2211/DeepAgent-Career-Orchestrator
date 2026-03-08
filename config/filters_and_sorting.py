"""
Controls HOW scraped results are filtered and sorted AFTER scraping. Edit anytime — no code changes needed.

How it works:
Scraper fetches raw jobs → filters remove unwanted ones → sorting orders what remains → results saved.

Tip:
Filters are applied in order: job_type → is_remote → exclude_companies → exclude_title_keywords → include_title_keywords → min_salary → require_description.
All filters are AND-combined. A job must pass ALL active filters to appear in results.
"""

FILTERS = {
    # Filter by employment type. [] = accept all types.
    # Options: "fulltime", "parttime", "internship", "contract"
    # Example: ["fulltime", "contract"]
    "job_type": [],

    # Filter by remote status. None = show all, True = remote only, False = onsite/hybrid only.
    "is_remote": None,

    # Skip jobs from these companies (case-insensitive). Good for blocking staffing agencies.
    # Example: ["Randstad", "ManpowerGroup", "Adecco", "TEKsystems"]
    "exclude_companies": [],

    # Skip jobs whose title contains ANY of these words (case-insensitive). Great for filtering out senior roles.
    # Currently set to skipping all senior/management titles.
    "exclude_title_keywords": [
        "Senior",
        "Sr.",
        "Staff",
        "Principal",
        "Director",
        "VP",
        "Lead",
        "Manager",
        "Head of"
    ],

    # If NOT empty, ONLY keep jobs whose title contains at least one of these words. Leave [] to accept all titles.
    # Example (AI focus): ["AI", "Machine Learning", "ML", "Deep Learning"]
    "include_title_keywords": [],

    # Minimum salary to accept. Jobs with salary below this are filtered out. 
    # Jobs with NO salary listed are kept (not filtered). Set None to disable.
    # Example: 10000 (EGP monthly), 50000 (USD yearly)
    "min_salary": None,

    # Skip jobs requiring more than N years of experience. None = no filter. 
    # (Phase 4 — parsed from description by AI)
    # Example: 2 (entry level), 5 (mid level)
    "max_experience_years": None,

    # If True, skip jobs that have no description text. Recommended: True (jobs without descriptions are useless).
    "require_description": True,
}

SORTING = {
    # How to order the final results. Only one sort field at a time.
    # Jobs with missing values for the sort field are pushed to the end.
    
    # Which field to sort results by. 
    # Options: "date_posted", "company", "title", "min_amount", "max_amount"
    "sort_by": "date_posted",

    # Sort direction. "desc" = newest/highest first, "asc" = oldest/lowest first.
    # Options: "desc", "asc"
    "sort_order": "desc"
}
