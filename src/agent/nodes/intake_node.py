"""
Intake Node — Phase 6 / 6.5.

First node in the per-job processing chain. Responsible for:
  1. Accepting a raw job dict (from loop_controller or direct call)
  2. Extracting the job_uid for fast dedup
  3. Checking if this UID was already processed in the DB
  4. Routing to "skip" (duplicate → back to loop) or "continue" (new job)

Phase 6.5 change:
  - Skip routing now returns "loop" instead of END, so the batch loop
    continues processing the next job in the queue.

Design:
  - Reads `processed_jobs` table via DBManager — same DB all phases share.
  - Does NOT call any LLM — intentionally cheap and fast.
"""

from loguru import logger

from src.agent.state import AgentState
from src.db.db_manager import DBManager
from src.intelligence.uid_extractor import uid_from_url


def intake_node(state: AgentState) -> AgentState:
    """
    Validate and register an incoming job record.

    State in:  current_job (raw dict)
    State out: job_uid, routing ("loop" or "continue"), metadata

    Edge routing:
        "loop"     → duplicate job already processed → back to loop_controller
        "continue" → new job → proceed to analysis_node
    """
    record = state.get("current_job") or {}

    # --- Extract UID ---
    source_url = record.get("job_url") or record.get("source_url")
    platform = record.get("platform")
    job_uid = uid_from_url(source_url, platform) or record.get("job_uid")

    logger.info(f"[intake] Job UID: {job_uid}")
    logger.info(
        f"[intake] Title: {(record.get('raw_title') or record.get('title') or 'unknown')[:80]}"
    )

    # --- Dedup check against processed_jobs table ---
    if job_uid:
        db = DBManager()
        with db.connect() as conn:
            already_processed = db.exists(conn, "processed_jobs", "job_uid", job_uid)

        if already_processed:
            logger.info(f"[intake] SKIP — job_uid already in processed_jobs: {job_uid}")
            # Phase 6.5: route to "loop" so the batch continues, not to END.
            # In single-job mode, loop_controller is absent — graph.py maps
            # "loop" → END in that case.
            current_stats = state.get("pipeline_stats") or {}
            return {
                **state,
                "job_uid": job_uid,
                "routing": "loop",
                "pipeline_stats": {
                    **current_stats,
                    "skipped": current_stats.get("skipped", 0) + 1,
                },
                "metadata": {
                    **state.get("metadata", {}),
                    "skip_reason": "already_processed",
                },
            }

    # --- Attach metadata from the raw record ---
    metadata = {
        "platform": platform,
        "source_url": source_url,
        "date_posted": record.get("date_posted"),
        "author_name": record.get("author_name"),
        "reactions": record.get("reactions"),
    }

    logger.info(f"[intake] NEW job → continuing to analysis.")
    return {
        **state,
        "job_uid": job_uid,
        "routing": "continue",
        "metadata": {**state.get("metadata", {}), **metadata},
    }


def route_after_intake(state: AgentState) -> str:
    """Conditional edge function: returns 'loop' (skip) or 'continue' (new job)."""
    routing = state.get("routing", "continue")
    # Normalise legacy 'skip' to 'loop' for backward compatibility
    return "loop" if routing == "skip" else routing
