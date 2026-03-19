"""
Hybrid project search tool — Phase 5 & 6.

Searches projects using TWO methods (hybrid approach):
  1. Keyword overlap (fast, deterministic)
  2. Vector similarity (semantic, optional)

The hybrid score combines both approaches for best results.

Usage:
  - Without ChromaDB: Pure keyword matching (fallback)
  - With ChromaDB: Hybrid keyword + vector search
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
    use_vector_search: bool = True,
) -> list[dict]:
    """
    Find the top-K most relevant projects for a given job.
    
    Hybrid approach:
      1. Keyword overlap scoring (always)
      2. Vector similarity (if ChromaDB available and use_vector_search=True)
      3. Combined score = 0.6 * keyword + 0.4 * vector

    Args:
        job:               ParsedJob dict (with `intelligence` and `scout` sub-dicts).
        top_k:             Maximum number of projects to return.
        projects_file:     Path to my_projects.json.
        use_vector_search: Enable ChromaDB semantic search (default True).

    Returns:
        List of project dicts sorted by relevance (highest first).
        Each project dict includes `_match_score` and `_keyword_score` fields.
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

    # Filter out metadata entries
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

    # --- Keyword scoring (always) ---
    keyword_scores = {}
    for project in projects:
        score = score_project(project, job_keywords)
        keyword_scores[project["name"]] = score

    # --- Vector scoring (optional) ---
    vector_scores = {}
    if use_vector_search:
        try:
            from src.profile.vector_store import VectorStore
            
            store = VectorStore()
            
            # Build query from job intelligence
            query_text = _build_query_text(job)
            
            # Semantic search
            matches = store.search_projects(query_text, top_k=len(projects))
            
            # Normalize vector distances to scores (lower distance = higher score)
            # ChromaDB returns cosine distance [0, 2]; convert to score [0, 1]
            for match in matches:
                name = match["name"]
                distance = match.get("distance", 1.0)
                # Score = 1 - (distance / 2) → perfect match = 1.0, no match = 0.0
                vector_scores[name] = max(0, 1 - (distance / 2))
            
            logger.debug(f"[search_tool] Vector search returned {len(vector_scores)} scores")
            
        except Exception as e:
            logger.debug(f"[search_tool] Vector search unavailable: {e}")
            use_vector_search = False

    # --- Combine scores ---
    scored = []
    for project in projects:
        name = project["name"]
        kw_score = keyword_scores.get(name, 0.0)
        vec_score = vector_scores.get(name, 0.0) if use_vector_search else 0.0
        
        if use_vector_search:
            # Hybrid: 60% keyword, 40% vector
            final_score = 0.6 * kw_score + 0.4 * vec_score
        else:
            # Keyword only
            final_score = kw_score
        
        scored.append({
            **project,
            "_match_score": round(final_score, 3),
            "_keyword_score": round(kw_score, 3),
            "_vector_score": round(vec_score, 3) if use_vector_search else None,
        })

    # Sort by combined score
    scored.sort(key=lambda p: p["_match_score"], reverse=True)
    top = scored[:top_k]

    for p in top:
        mode = "hybrid" if use_vector_search else "keyword"
        logger.info(
            f"[search_tool] ✓ {p.get('name', '?')[:50]:<50} "
            f"score={p['_match_score']:.2f} ({mode})"
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


def _build_query_text(job: dict) -> str:
    """
    Build a natural language query from job for vector search.
    
    Combines title, description snippet, tech stack, and skills
    into a searchable document.
    """
    parts = []
    
    title = job.get("raw_title") or job.get("title")
    if title:
        parts.append(f"Job: {title}")
    
    intelligence = job.get("intelligence") or {}
    
    role_summary = intelligence.get("role_summary")
    if role_summary:
        parts.append(f"Description: {role_summary}")
    
    tech_stack = intelligence.get("tech_stack") or []
    if tech_stack:
        parts.append(f"Technologies: {', '.join(tech_stack[:10])}")
    
    technical_skills = intelligence.get("technical_skills") or []
    if technical_skills:
        parts.append(f"Skills: {', '.join(technical_skills[:10])}")
    
    specializations = intelligence.get("specializations") or []
    if specializations:
        parts.append(f"Specializations: {', '.join(specializations[:5])}")
    
    return "\n".join(parts) if parts else "General software engineering"
