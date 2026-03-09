"""
Centralized configuration for all LLM model names used across the system.
If a model is deprecated or needs to be changed, do it here.

Only use models confirmed available via `client.models.list()`.
To check: python -c "from google import genai; c = genai.Client(api_key='...')[print(m.name) for m in c.models.list()]"
"""

# ---------------------------------------------------------------------------
# Phase 2: LinkedIn Keyword Generation
# ---------------------------------------------------------------------------
KEYWORD_GENERATION_PRIMARY  = "gemini-2.5-flash"
KEYWORD_GENERATION_FALLBACK = "gemini-3.1-flash-lite-preview"

# ---------------------------------------------------------------------------
# Phase 3: Multi-Job Post Splitting
# ---------------------------------------------------------------------------
JOB_SPLITTING_PRIMARY  = "gemini-2.5-flash"
JOB_SPLITTING_FALLBACK = "gemini-3.1-flash-lite-preview"

# ---------------------------------------------------------------------------
# Phase 4: Intelligence Extraction (Job Parsing)
# ---------------------------------------------------------------------------
JOB_PARSING_PRIMARY  = "gemini-2.5-flash"
JOB_PARSING_FALLBACK = "gemini-3.1-flash-lite-preview"

# ---------------------------------------------------------------------------
# Phase 5: CV Project Extraction
# ---------------------------------------------------------------------------
CV_EXTRACTION_PRIMARY  = "gemini-2.5-flash"
CV_EXTRACTION_FALLBACK = "gemini-3.1-flash-lite-preview"
