"""
Project-level profile configuration — Phase 5.

This file controls HOW the pipeline handles your profile.
It does NOT contain personal identity data (GitHub URL, repo lists) —
those live in data/profile/my_github.py (gitignored).

──────────────────────────────────────────────
FILE LAYOUT
──────────────────────────────────────────────

  data/profile/
    my_cv.tex          → Your LaTeX CV (base template for Phase 7)
    my_github.py       → Your GitHub URL + include/exclude repo lists
    my_projects.json   → Manual projects not on GitHub

  data/profile.example/
    my_cv.example.tex          → Copy → data/profile/my_cv.tex
    my_github.example.py       → Copy → data/profile/my_github.py
    my_projects.example.json   → Copy → data/profile/my_projects.json
    cv_template.tex            → Default CV template (used as fallback)

──────────────────────────────────────────────
CV TEMPLATE TOGGLE
──────────────────────────────────────────────

  USE_DEFAULT_CV_TEMPLATE = False  (default)
    → Phase 7 uses data/profile/my_cv.tex as the base.
    → If my_cv.tex is missing, auto-falls back to cv_template.tex.

  USE_DEFAULT_CV_TEMPLATE = True
    → Always use cv_template.tex, even if my_cv.tex exists.
    → Useful for testing the template without touching your real CV.

──────────────────────────────────────────────
OUTPUTS (Phase 7)
──────────────────────────────────────────────

  data/outputs/{job_uid}/cv_tailored.tex    ← Tailored LaTeX CV
  data/outputs/{job_uid}/cv_tailored.pdf    ← Compiled PDF
  data/outputs/{job_uid}/cover_letter.tex   ← Cover letter (optional)
"""

import importlib.util
from pathlib import Path


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------
_ROOT = Path(__file__).resolve().parent.parent
_PROFILE_DIR = _ROOT / "data" / "profile"
_EXAMPLE_DIR = _ROOT / "data" / "profile.example"


# ===========================================================================
# YOUR CV
# ===========================================================================

# Path to your personal LaTeX CV.
# Paste your CV into data/profile/my_cv.tex.
# Phase 7 reads this and generates tailored copies — original never touched.
CV_FILE: Path = _PROFILE_DIR / "my_cv.tex"


# ===========================================================================
# CV TEMPLATE (fallback / default)
# ===========================================================================

# Default LaTeX CV template committed to the repo.
# Used when USE_DEFAULT_CV_TEMPLATE=True or when CV_FILE doesn't exist.
CV_TEMPLATE_FILE: Path = _EXAMPLE_DIR / "cv_template.tex"

# Toggle: set True to always use the template instead of your personal CV.
# If CV_FILE doesn't exist, the template is used automatically regardless.
USE_DEFAULT_CV_TEMPLATE: bool = False


# ===========================================================================
# MANUAL PROJECTS (not on GitHub)
# ===========================================================================

# JSON file listing projects not on GitHub (or manually described projects).
# Schema per entry: name, description, tech_stack, highlights, github_url, period.
MANUAL_PROJECTS_FILE: Path = _PROFILE_DIR / "my_projects.json"


# ===========================================================================
# PROFILE INDEX SETTINGS (Phase 5)
# ===========================================================================

# Where the ChromaDB profile vector index is stored (auto-created on first run).
PROFILE_INDEX_DIR: Path = _PROFILE_DIR / "vector_index"

# Max README chars to embed per GitHub repo (truncated if longer).
MAX_README_CHARS: int = 4000

# Max GitHub repos to include in the index.
# Agent ranks by star count + recency if you have more than this.
MAX_GITHUB_REPOS: int = 30


# ===========================================================================
# GitHub profile loader
# ===========================================================================

def load_github_profile() -> dict:
    """
    Load user-specific GitHub settings from data/profile/my_github.py.

    Returns a dict with keys:
        github_url      : str  — e.g. "https://github.com/Zayed-2211"
        include_repos   : list[str]
        exclude_repos   : list[str]

    Falls back to empty values if my_github.py doesn't exist yet.
    The priority logic (include → exclude → all) is applied by the caller.
    """
    profile_path = _PROFILE_DIR / "my_github.py"

    if not profile_path.exists():
        return {"github_url": "", "include_repos": [], "exclude_repos": []}

    spec = importlib.util.spec_from_file_location("my_github", profile_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    return {
        "github_url":    getattr(mod, "GITHUB_URL", ""),
        "include_repos": getattr(mod, "INCLUDE_REPOS", []),
        "exclude_repos": getattr(mod, "EXCLUDE_REPOS", []),
    }


def resolve_cv_path() -> Path:
    """
    Return the CV file to use for Phase 7 generation.

    Decision logic:
      1. If USE_DEFAULT_CV_TEMPLATE is True  → always use CV_TEMPLATE_FILE
      2. If CV_FILE exists                   → use CV_FILE (my_cv.tex)
      3. Otherwise                           → fall back to CV_TEMPLATE_FILE
    """
    if USE_DEFAULT_CV_TEMPLATE:
        return CV_TEMPLATE_FILE
    if CV_FILE.exists():
        return CV_FILE
    return CV_TEMPLATE_FILE
