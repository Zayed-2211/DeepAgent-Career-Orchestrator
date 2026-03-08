"""
Profile Configuration — Phase 5.

This is the SINGLE SOURCE OF TRUTH for everything about your profile:
  - Your CV file location
  - Your GitHub profile
  - Which repos to include or exclude from the profile index
  - Where to find your manually-written projects

No GitHub token is required. All GitHub data is fetched from the public API.

──────────────────────────────────────────────
HOW GITHUB PROJECT SELECTION WORKS
──────────────────────────────────────────────

Priority order (checked top-to-bottom):

  1. GITHUB_INCLUDE_REPOS   ← If this is non-empty, ONLY these repos are used.
                              Everything else on GitHub is ignored.

  2. GITHUB_EXCLUDE_REPOS   ← If INCLUDE is empty and EXCLUDE is non-empty,
                              take ALL public repos EXCEPT the ones listed here.

  3. (Both empty)           ← Take ALL public repos from your GitHub account.
                              The agent then picks the most relevant ones per job.

All selected GitHub repos are combined with MANUAL_PROJECTS_FILE.
The agent decides which projects are most relevant for each specific job.

──────────────────────────────────────────────
YOUR FILES
──────────────────────────────────────────────

  data/profile/my_cv.tex
    → Paste your full LaTeX CV here. This is the base template.
      Phase 7 reads it and generates a tailored copy per job.
      Your original is NEVER overwritten.

  data/profile/my_projects.json
    → Projects that are NOT on GitHub (or that you want to describe manually).
      No GitHub link needed for these.
      Each entry: name, description, tech_stack, highlights, period.

──────────────────────────────────────────────
OUTPUTS (Phase 7)
──────────────────────────────────────────────

  data/outputs/{job_uid}/cv_tailored.tex    ← Tailored LaTeX CV
  data/outputs/{job_uid}/cv_tailored.pdf    ← Compiled PDF
  data/outputs/{job_uid}/cover_letter.tex   ← Cover letter (optional)
"""

from pathlib import Path


# ---------------------------------------------------------------------------
# Project root helpers
# ---------------------------------------------------------------------------
_ROOT = Path(__file__).resolve().parent.parent
_PROFILE_DIR = _ROOT / "data" / "profile"


# ===========================================================================
# YOUR CV
# ===========================================================================

# Path to your LaTeX CV file.
# Paste your full LaTeX code inside data/profile/my_cv.tex.
# Phase 7 reads this and generates tailored copies per job.
CV_FILE: Path = _PROFILE_DIR / "my_cv.tex"


# ===========================================================================
# MANUAL PROJECTS (not on GitHub)
# ===========================================================================

# JSON file listing projects you want to include in your profile
# that are NOT on GitHub — or any project you want to describe manually
# (the agent will use your descriptions instead of scraping the repo).
# Each entry can optionally have a github_url if it IS on GitHub.
MANUAL_PROJECTS_FILE: Path = _PROFILE_DIR / "my_projects.json"


# ===========================================================================
# GITHUB — PUBLIC API (no token required)
# ===========================================================================

# Your GitHub profile URL.
# The agent will fetch your public repos from this account.
# Set to "" or None to skip GitHub entirely (use only MANUAL_PROJECTS_FILE).
GITHUB_PROFILE_URL: str = "https://github.com/YOUR_GITHUB_USERNAME"

# ---------------------------------------------------------------------------
# INCLUDE list — the main list
# ---------------------------------------------------------------------------
# If non-empty: ONLY these repos are fetched from GitHub (by repo name).
# Anything not listed here is ignored.
# Use exact repo names as they appear on GitHub.
#
# Example:
#   GITHUB_INCLUDE_REPOS = [
#       "my-rag-chatbot",
#       "arabic-nlp-toolkit",
#       "fastapi-job-board",
#   ]
GITHUB_INCLUDE_REPOS: list[str] = [
    # ← Add repo names here to whitelist specific repos
]

# ---------------------------------------------------------------------------
# EXCLUDE list — checked only when INCLUDE is empty
# ---------------------------------------------------------------------------
# If INCLUDE is empty AND EXCLUDE is non-empty:
#   → all public repos are fetched EXCEPT the ones listed here.
# Common use: exclude forks, course assignments, toy experiments.
#
# Example:
#   GITHUB_EXCLUDE_REPOS = [
#       "old-university-assignments",
#       "forked-library",
#       "test-repo",
#   ]
GITHUB_EXCLUDE_REPOS: list[str] = [
    # ← Add repo names here to blacklist repos you want hidden
]

# ---------------------------------------------------------------------------
# If BOTH lists are empty → fetch ALL public repos from GITHUB_PROFILE_URL.
# The agent picks the most relevant ones per job automatically.
# ---------------------------------------------------------------------------


# ===========================================================================
# PROFILE INDEX SETTINGS (Phase 5)
# ===========================================================================

# Where the profile vector index (ChromaDB) is stored.
# Auto-created on first run — no manual setup needed.
PROFILE_INDEX_DIR: Path = _ROOT / "data" / "profile" / "vector_index"

# Max README length to embed per repo (characters).
# Longer READMEs are truncated to this before embedding.
MAX_README_CHARS: int = 4000

# Max number of GitHub repos to include in the index.
# If you have many repos, the agent ranks by star count and recency.
MAX_GITHUB_REPOS: int = 30
