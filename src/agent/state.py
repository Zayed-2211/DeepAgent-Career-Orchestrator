"""
LangGraph Agent State — Phase 6 / 6.5.

Defines the shared `AgentState` TypedDict that flows through every node
in the graph. All mutable data must live here.

Design rules:
  - Store references/UIDs, not large blobs — keep state small.
  - All fields are Optional with defaults so nodes can be run individually.
  - `schema_version` lets us detect stale checkpoints after state changes.

Phase 6 state flow (single-job mode):
  intake_node       → sets current_job, routing edge
  analysis_node     → enriches current_job with intelligence data
  matching_node     → sets matched_projects, match_score
  planning_node     → sets todo_list
  review_node       → sets human_decision
  dispatch_node     → sets generated_docs (paths only)

Phase 6.5 additions (full-pipeline mode):
  scout_node        → sets raw_records (unclean scraped batch)
  dedup_node        → reads raw_records, sets job_queue (clean batch)
  loop_controller   → pops from job_queue into current_job each iteration
                      accumulates pipeline_stats across the loop
"""

from typing import Any, TypedDict


# Bump this whenever fields are added/removed.
# Old checkpoints with a lower version are considered stale —
# clear data/state/checkpoints/ before using a new schema.
CURRENT_SCHEMA_VERSION = 2


class AgentState(TypedDict, total=False):
    """
    Shared state flowing through every node in the LangGraph agent.

    All fields are optional (total=False) so nodes can be unit-tested
    in isolation without initialising the full graph.
    """

    # -------------------------------------------------------------------------
    # Schema versioning — detect stale checkpoints
    # -------------------------------------------------------------------------
    schema_version: int  # Must equal CURRENT_SCHEMA_VERSION

    # =========================================================================
    # Phase 6.5 — Pipeline batch fields
    # =========================================================================

    # Raw scraped records — filled by scout_node, consumed by dedup_node
    raw_records: list[dict]

    # Cleaned, deduplicated, split records — filled by dedup_node.
    # loop_controller pops from this queue one record per iteration.
    job_queue: list[dict]

    # Index of the job currently being processed (0-based, for display only).
    current_job_index: int

    # Accumulated stats across all loop iterations.
    # Keys: "total", "skipped", "approved", "rejected", "errors"
    pipeline_stats: dict[str, int]

    # =========================================================================
    # Phase 6 — Per-job processing fields
    # =========================================================================

    # Current job being processed
    current_job: dict  # Serialised ParsedJob (or raw record pre-Phase 4)
    job_uid: str | None  # Extracted early for fast dedup checks

    # Matching results
    matched_projects: list[dict]  # Top-N project dicts from my_projects.json
    match_score: float  # Overall relevance 0.0–1.0

    # Agent planning
    todo_list: list[str]  # Human-readable task items (some pre-checked ✓)

    # Human-in-the-loop decision
    human_decision: str  # "approve" | "reject" | "pending"

    # Phase 8 — Company research data
    company_research: dict  # Glassdoor insights, LinkedIn data, prep pack path

    # Output paths (assigned by dispatch_node, consumed by Phase 7/8)
    generated_docs: dict[str, str]  # {"cv": "data/outputs/.../cv.tex", ...}

    # Error tracking
    error: str | None  # Non-null if any node encountered an unrecoverable error

    # Internal routing hints (used by conditional edges)
    # Values: "skip" | "continue" | "approve" | "reject" | "loop" |
    #         "success" | "error" | "next_job" | "done"
    routing: str

    # Miscellaneous metadata from the raw record
    metadata: dict[str, Any]  # Platform, source URL, scraped_at, etc.


def initial_state(raw_record: dict | None = None) -> AgentState:
    """
    Build a fresh AgentState with all safe defaults.

    Single-job mode: pass `raw_record` to bypass scout/dedup.
    Pipeline mode:   leave `raw_record` as None — scout_node fills raw_records.

    Args:
        raw_record: Optional raw job dict for single-job mode.

    Returns:
        AgentState with all fields initialized to safe defaults.
    """
    return AgentState(
        schema_version=CURRENT_SCHEMA_VERSION,
        # --- Phase 6.5 batch fields ---
        raw_records=[],
        job_queue=[raw_record] if raw_record else [],
        current_job_index=0,
        pipeline_stats={"total": 0, "skipped": 0, "approved": 0, "rejected": 0, "errors": 0},
        # --- Phase 6 per-job fields ---
        current_job=raw_record or {},
        job_uid=None,
        matched_projects=[],
        match_score=0.0,
        todo_list=[],
        human_decision="pending",
        generated_docs={},
        error=None,
        routing="continue",
        metadata={},
    )


def pipeline_initial_state() -> AgentState:
    """
    Build a fresh AgentState for full-pipeline (scout → dedup → loop) mode.

    Scout and dedup nodes will populate raw_records and job_queue.
    """
    return AgentState(
        schema_version=CURRENT_SCHEMA_VERSION,
        raw_records=[],
        job_queue=[],
        current_job_index=0,
        pipeline_stats={"total": 0, "skipped": 0, "approved": 0, "rejected": 0, "errors": 0},
        current_job={},
        job_uid=None,
        matched_projects=[],
        match_score=0.0,
        todo_list=[],
        human_decision="pending",
        generated_docs={},
        error=None,
        routing="continue",
        metadata={},
    )

