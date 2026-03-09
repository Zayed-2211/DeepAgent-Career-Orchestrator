"""
File-based project search tool — Phase 6.

Searches `data/profile/my_projects.json` for projects relevant to a job.
Uses keyword overlap scoring (no external DB or embedding required):

  score = |job_keywords ∩ project_keywords| / |job_keywords|

Where keywords are extracted from tech_stack + technical_skills.
This is the simplest correct approach that:
  - Works offline (no ChromaDB/network needed)
  - Is testable with static fixtures
  - Produces reproducible results

Phase 5's vector store can be optionally used here once implemented.
For now, JSON-based search is sufficient for an MVP.
"""

import json
import re
from pathlib import Path

from loguru import logger

from config.projects_config import MANUAL_PROJECTS_FILE


# ---------------------------------------------------------------------------
# Keyword extraction
# ---------------------------------------------------------------------------

def _extract_keywords(job: dict) -> set[str]:
    """
    Extract a flat set of skill keywords from a parsed job dict.

    Combines tech_stack + technical_skills from the intelligence layer.
    Falls back to title words if intelligence is missing.
    """
    keywords: set[str] = set()

    intelligence = job.get("intelligence") or {}
    scout = job.get("scout") or {}

    for item in intelligence.get("tech_stack") or []:
        keywords.add(item.lower().strip())

    for item in intelligence.get("technical_skills") or []:
        keywords.add(item.lower().strip())

    for item in intelligence.get("specializations") or []:
        keywords.add(item.lower().strip())

    # Fallback: split title into words if no intelligence
    if not keywords:
        title = job.get("raw_title") or job.get("title") or ""
        keywords.update(re.sub(r"[^a-z\s]", "", title.lower()).split())

    return keywords - {"", "and", "or", "the", "of", "for", "in", "with"}


def _project_keywords(project: dict) -> set[str]:
    """Extract keyword fingerprint from a project dict."""
    keywords: set[str] = set()

    for item in project.get("tech_stack") or []:
        keywords.add(item.lower().strip())

    for item in project.get("domains") or []:
        keywords.add(item.lower().strip())

    # Pull tool words from highlights
    for highlight in project.get("highlights") or []:
        if isinstance(highlight, dict):
            for tool in highlight.get("tools") or []:
                keywords.add(tool.lower().strip())

    # Add description words as weak signals
    desc = project.get("description") or ""
    words = re.sub(r"[^a-z\s]", "", desc.lower()).split()
    keywords.update(words[:30])  # cap at first 30 words to stay fast

    return keywords - {"", "and", "or", "the", "of", "for", "in", "with", "a", "an"}


# ---------------------------------------------------------------------------
# Overlap scoring
# ---------------------------------------------------------------------------

def score_project(project: dict, job_keywords: set[str]) -> float:
    """
    Score a project's relevance to a job using keyword overlap.

    Returns a float in [0.0, 1.0]:
      0.0 → no keywords in common
      1.0 → all job keywords found in the project

    The denominator is capped at 1 to avoid division-by-zero.
    """
    if not job_keywords:
        return 0.0

    proj_keywords = _project_keywords(project)
    intersection = job_keywords & proj_keywords
    return len(intersection) / max(len(job_keywords), 1)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def search_projects(
    job: dict,
    top_k: int = 3,
    projects_file: Path = MANUAL_PROJECTS_FILE,
) -> list[dict]:
    """
    Find the top-K most relevant projects for a given job.

    Args:
        job:           ParsedJob dict (with `intelligence` and `scout` sub-dicts).
        top_k:         Maximum number of projects to return.
        projects_file: Path to my_projects.json.

    Returns:
        List of project dicts sorted by relevance (highest first).
        Each project dict includes an added `_match_score` field.
    """
    if not projects_file.exists():
        logger.warning(f"[search_tool] Projects file not found: {projects_file}")
        return []

    try:
        raw = json.loads(projects_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        logger.error(f"[search_tool] Failed to read projects file: {e}")
        return []

    if not isinstance(raw, list):
        return []

    # Filter out metadata entries (those with _comment or _instructions)
    projects = [
        entry for entry in raw
        if isinstance(entry, dict)
        and "name" in entry
        and "_comment" not in entry
        and "_instructions" not in entry
    ]

    if not projects:
        logger.info("[search_tool] No real projects found in file.")
        return []

    job_keywords = _extract_keywords(job)
    logger.debug(f"[search_tool] Job keywords ({len(job_keywords)}): {sorted(job_keywords)[:10]}...")

    # Score every project
    scored = []
    for project in projects:
        score = score_project(project, job_keywords)
        scored.append({**project, "_match_score": round(score, 3)})

    # Sort by score descending
    scored.sort(key=lambda p: p["_match_score"], reverse=True)
    top = scored[:top_k]

    for p in top:
        logger.info(
            f"[search_tool] ✓ {p.get('name', '?')[:50]:<50} "
            f"score={p['_match_score']:.2f}"
        )

    return top


def overall_match_score(matched_projects: list[dict]) -> float:
    """
    Compute the overall job match score from the top matched projects.

    Uses a weighted average: top project gets 60%, 2nd gets 30%, 3rd gets 10%.
    Returns 0.0 if no projects are matched.
    """
    weights = [0.6, 0.3, 0.1]
    score = 0.0
    for i, project in enumerate(matched_projects[:3]):
        score += project.get("_match_score", 0.0) * weights[i]
    return round(score, 3)
