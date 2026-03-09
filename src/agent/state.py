"""
LangGraph Agent State — Phase 6.

Defines the shared `AgentState` TypedDict that flows through every node
in the graph. All mutable data must live here.

Design rules:
  - Store references/UIDs, not large blobs — keep state small.
  - All fields are Optional with defaults so nodes can be run individually.
  - `schema_version` lets us detect stale checkpoints after state changes.

State flow:
  intake_node       → sets current_job, routing edge
  analysis_node     → enriches current_job with intelligence data
  matching_node     → sets matched_projects, match_score
  planning_node     → sets todo_list
  review_node       → sets human_decision
  dispatch_node     → sets generated_docs (paths only)
"""

from typing import Any, TypedDict


# Current schema version — bump this if you add/remove fields.
# Old checkpoints from a previous schema_version are considered stale.
CURRENT_SCHEMA_VERSION = 1


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

    # -------------------------------------------------------------------------
    # Current job being processed
    # -------------------------------------------------------------------------
    current_job: dict  # Serialised ParsedJob (or raw record pre-Phase 4)
    job_uid: str | None  # Extracted early for fast dedup checks

    # -------------------------------------------------------------------------
    # Matching results
    # -------------------------------------------------------------------------
    matched_projects: list[dict]  # Top-N project dicts from my_projects.json
    match_score: float  # Overall relevance 0.0–1.0

    # -------------------------------------------------------------------------
    # Agent planning
    # -------------------------------------------------------------------------
    todo_list: list[str]  # Human-readable task items (some pre-checked ✓)

    # -------------------------------------------------------------------------
    # Human-in-the-loop decision
    # -------------------------------------------------------------------------
    human_decision: str  # "approve" | "reject" | "pending"

    # -------------------------------------------------------------------------
    # Output paths (assigned by dispatch_node, consumed by Phase 7/8)
    # -------------------------------------------------------------------------
    generated_docs: dict[str, str]  # {"cv": "data/outputs/.../cv.tex", ...}

    # -------------------------------------------------------------------------
    # Error tracking
    # -------------------------------------------------------------------------
    error: str | None  # Non-null if any node encountered an unrecoverable error

    # -------------------------------------------------------------------------
    # Internal routing hints (used by conditional edges)
    # -------------------------------------------------------------------------
    routing: str  # "skip" | "continue" | "approve" | "reject"

    # -------------------------------------------------------------------------
    # Miscellaneous metadata (passed through from raw record)
    # -------------------------------------------------------------------------
    metadata: dict[str, Any]  # Platform, source URL, scraped_at, etc.


def initial_state(raw_record: dict | None = None) -> AgentState:
    """
    Build a fresh AgentState with all safe defaults.

    Args:
        raw_record: Optional raw job dict to attach at startup.

    Returns:
        AgentState with all fields initialized to safe defaults.
    """
    return AgentState(
        schema_version=CURRENT_SCHEMA_VERSION,
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
