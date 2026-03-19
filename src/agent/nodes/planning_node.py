"""
Planning Node — Phase 6.

Creates the agent's structured todo list based on the current job analysis.
This is a lightweight LLM call that produces a human-readable action plan.

The plan reflects what has already been done vs. what remains:
  Done:  Intake ✓, Analysis ✓, Matching ✓
  TODO:  Write CV, Research Company, Write Cover Letter

State in:  current_job, matched_projects, match_score
State out: todo_list
"""

from loguru import logger

from src.agent.state import AgentState
from src.agent.tools.todo_tool import create_todo, mark_done


def planning_node(state: AgentState) -> AgentState:
    """
    Build the agent's action plan for the current job.

    State in:  current_job, matched_projects, match_score
    State out: todo_list

    The todo list is simple and deterministic — no LLM needed here.
    The human review node and dispatch node update it as tasks complete.
    """
    record = state.get("current_job") or {}
    scout = record.get("scout") or {}

    is_job = scout.get("is_job_posting", True)
    company = scout.get("company_name") or "unknown company"
    match_score = state.get("match_score", 0.0)
    matched = state.get("matched_projects") or []

    # --- Build the canonical todo list ---
    items = [
        f"Validate & ingest job posting",
        f"Extract intelligence from JD",
        f"Match projects (top {min(len(matched), 3)} found, score={match_score:.0%})",
        f"Human review & approval",
        f"Generate tailored CV for {company}",
        f"Research {company} (Glassdoor + LinkedIn)",
        f"Generate cover letter",
    ]

    todo = create_todo(items)

    # Mark completed steps (done by earlier nodes in this run)
    todo = mark_done(todo, "Validate")
    todo = mark_done(todo, "Extract intelligence")
    todo = mark_done(todo, "Match projects")

    # If the record is not a job posting, some steps don't apply
    if not is_job:
        logger.info("[planning] Non-posting — simplified plan.")
        todo = [
            "✓ Validate & ingest (non-posting — archived)",
        ]

    logger.info(f"[planning] Plan ready — {len(todo)} steps.")
    for item in todo:
        logger.debug(f"  {item}")

    return {**state, "todo_list": todo}
