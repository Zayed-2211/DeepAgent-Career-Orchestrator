"""
Matching Node — Phase 6.

Finds the most relevant personal projects for the current job.
Uses the file-based keyword overlap scorer from `tools/search_tool.py`.

No ChromaDB / external DB required — works purely from my_projects.json.

State in:  current_job (with intelligence populated by analysis_node)
State out: matched_projects (top 3), match_score (overall 0.0–1.0)
"""

from loguru import logger

from src.agent.state import AgentState
from src.agent.tools.search_tool import overall_match_score, search_projects


def matching_node(state: AgentState) -> AgentState:
    """
    Score and rank personal projects against the current job.

    State in:  current_job
    State out: matched_projects, match_score
    """
    record = state.get("current_job") or {}
    title = (record.get("raw_title") or record.get("title") or "no title")[:60]
    logger.info(f"[matching] Searching projects for: {title}")

    # --- Run searcher ---
    matched = search_projects(record, top_k=3)

    if not matched:
        logger.warning("[matching] No projects found — match_score=0.0")
        return {
            **state,
            "matched_projects": [],
            "match_score": 0.0,
        }

    score = overall_match_score(matched)

    logger.info(
        f"[matching] Top matches: "
        + ", ".join(f"{p['name'][:30]}({p['_match_score']:.2f})" for p in matched)
    )
    logger.info(f"[matching] Overall match_score={score:.2f}")

    return {
        **state,
        "matched_projects": matched,
        "match_score": score,
    }
