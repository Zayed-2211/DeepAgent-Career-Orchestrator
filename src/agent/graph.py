"""
LangGraph Agent Graph — Phase 6.5 + Phase 7 & 8.

Full pipeline with 11 nodes and visible loop cycles:

    [START]
       │
    scout_node ─────────────────────────────────────▶ [END]  (on error)
       │ success
    dedup_node
       │
    loop_controller ─────────────────────────────▶ [END]  (queue done)
       │ next_job                     ▲
    intake_node ──loop────────────────┘  (duplicate skip → back to loop)
       │ continue
    analysis_node
       │
    matching_node
       │
    planning_node
       │
    review_node
       │ (approve or reject — both go to dispatch)
    dispatch_node ──reject→loop───────┘  (rejected jobs)
       │ approve
    research_node (Phase 8 - company research)
       │
    generator_node (Phase 7 - CV & cover letter)
       │
    ──────────────────loop────────────┘  (next job)

Pipeline mode  (--pipeline flag):  START → scout → dedup → loop → ...
Single-job mode (--job-file flag): START → loop → intake → ... (scout/dedup skipped)

The loop edges from intake ("loop") and generator ("loop") both point back to
loop_controller, creating the visible cycle in the graph PNG.
"""

from pathlib import Path

from langgraph.graph import END, StateGraph
from loguru import logger

from src.agent.checkpointer import make_checkpointer
from src.agent.nodes.analysis_node import analysis_node
from src.agent.nodes.dedup_node import dedup_node
from src.agent.nodes.dispatch_node import dispatch_node
from src.agent.nodes.generator_node import generator_node
from src.agent.nodes.intake_node import intake_node, route_after_intake
from src.agent.nodes.loop_controller_node import (
    loop_controller_node,
    route_after_loop_controller,
)
from src.agent.nodes.matching_node import matching_node
from src.agent.nodes.planning_node import planning_node
from src.agent.nodes.research_node import research_node
from src.agent.nodes.review_node import review_node, route_after_review
from src.agent.nodes.scout_node import scout_node, route_after_scout
from src.agent.state import AgentState


# ---------------------------------------------------------------------------
# Output path for graph visualization
# ---------------------------------------------------------------------------
_DOCS_DIR = Path(__file__).resolve().parent.parent.parent / "docs"
GRAPH_PNG_PATH = _DOCS_DIR / "agent_graph.png"


# ---------------------------------------------------------------------------
# Graph builder — FULL PIPELINE (scout → dedup → loop → per-job chain)
# ---------------------------------------------------------------------------

def build_pipeline_graph() -> StateGraph:
    """
    Build the full-pipeline StateGraph (Phase 6.5 + Phase 7 & 8).

    11 nodes, 6 conditional edge groups, 2 visible loop cycles.

    Entry point: scout_node (--pipeline mode)
    Use build_single_job_graph() for --job-file mode.
    """
    workflow = StateGraph(AgentState)

    # Register all 11 nodes
    workflow.add_node("scout", scout_node)
    workflow.add_node("dedup", dedup_node)
    workflow.add_node("loop_controller", loop_controller_node)
    workflow.add_node("intake", intake_node)
    workflow.add_node("analysis", analysis_node)
    workflow.add_node("matching", matching_node)
    workflow.add_node("planning", planning_node)
    workflow.add_node("review", review_node)
    workflow.add_node("dispatch", dispatch_node)
    workflow.add_node("research", research_node)
    workflow.add_node("generator", generator_node)

    # Entry point: start the pipeline at scout
    workflow.set_entry_point("scout")

    # Edge 1: after scout → success (continue) or error (end)
    workflow.add_conditional_edges(
        "scout",
        route_after_scout,
        {
            "success": "dedup",
            "error": END,
        },
    )

    # Edge 2: scout → dedup (linear)
    workflow.add_edge("dedup", "loop_controller")

    # Edge 3: after loop_controller → next job (intake) or done (end)
    workflow.add_conditional_edges(
        "loop_controller",
        route_after_loop_controller,
        {
            "next_job": "intake",
            "done": END,
        },
    )

    # Edge 4: after intake → loop (skip duplicate) or continue (new job)
    # *** LOOP BACK: "loop" routes back to loop_controller ***
    workflow.add_conditional_edges(
        "intake",
        route_after_intake,
        {
            "loop": "loop_controller",       # ← visible cycle in graph PNG
            "continue": "analysis",
        },
    )

    # Linear per-job chain
    workflow.add_edge("analysis", "matching")
    workflow.add_edge("matching", "planning")
    workflow.add_edge("planning", "review")

    # Edge 5: after review → both outcomes go to dispatch
    workflow.add_conditional_edges(
        "review",
        route_after_review,
        {
            "approve": "dispatch",
            "reject": "dispatch",
        },
    )

    # Edge 6: after dispatch → generate (approved) or loop (rejected)
    workflow.add_conditional_edges(
        "dispatch",
        lambda s: s.get("routing", "loop"),
        {
            "generate": "research",          # ← approved jobs go to research
            "loop": "loop_controller",       # ← rejected jobs skip to next
        },
    )

    # Edge 7: research → generator (linear for approved jobs)
    workflow.add_edge("research", "generator")

    # Edge 8: after generator → loop back to loop_controller
    # *** LOOP BACK: creates the per-job iteration cycle ***
    workflow.add_conditional_edges(
        "generator",
        lambda s: s.get("routing", "loop"),
        {
            "loop": "loop_controller",       # ← visible cycle in graph PNG
            "skip": "loop_controller",       # ← if generation disabled
            "error": "loop_controller",      # ← continue on error
        },
    )

    return workflow


def build_single_job_graph() -> StateGraph:
    """
    Build the single-job StateGraph (Phase 6 + Phase 7 & 8).

    Skips scout and dedup. Starts at loop_controller which pops the
    single record pre-loaded into job_queue by initial_state().

    9 nodes, 4 conditional edge groups.
    Entry point: loop_controller
    """
    workflow = StateGraph(AgentState)

    # Register the 9 per-job nodes
    workflow.add_node("loop_controller", loop_controller_node)
    workflow.add_node("intake", intake_node)
    workflow.add_node("analysis", analysis_node)
    workflow.add_node("matching", matching_node)
    workflow.add_node("planning", planning_node)
    workflow.add_node("review", review_node)
    workflow.add_node("dispatch", dispatch_node)
    workflow.add_node("research", research_node)
    workflow.add_node("generator", generator_node)

    workflow.set_entry_point("loop_controller")

    # After loop_controller: go to intake (next_job) or end (done/empty)
    workflow.add_conditional_edges(
        "loop_controller",
        route_after_loop_controller,
        {
            "next_job": "intake",
            "done": END,
        },
    )

    # After intake: loop (skip) ends the single-job graph, continue processes
    workflow.add_conditional_edges(
        "intake",
        route_after_intake,
        {
            "loop": END,          # single-job mode: skip → end immediately
            "continue": "analysis",
        },
    )

    workflow.add_edge("analysis", "matching")
    workflow.add_edge("matching", "planning")
    workflow.add_edge("planning", "review")

    workflow.add_conditional_edges(
        "review",
        route_after_review,
        {
            "approve": "dispatch",
            "reject": "dispatch",
        },
    )

    # After dispatch in single-job mode: generate (approved) or loop (rejected)
    workflow.add_conditional_edges(
        "dispatch",
        lambda s: s.get("routing", "loop"),
        {
            "generate": "research",          # ← approved jobs go to research
            "loop": "loop_controller",       # ← rejected jobs end (empty queue)
        },
    )

    # Research → generator (linear for approved jobs)
    workflow.add_edge("research", "generator")

    # After generator → loop_controller (which sees empty queue → END)
    workflow.add_conditional_edges(
        "generator",
        lambda s: s.get("routing", "loop"),
        {
            "loop": "loop_controller",       # loop_controller will see empty queue → END
            "skip": "loop_controller",
            "error": "loop_controller",
        },
    )

    return workflow


# ---------------------------------------------------------------------------
# Compiled graphs (singletons used by CLI)
# ---------------------------------------------------------------------------

def _compile_pipeline() -> "CompiledGraph":
    checkpointer = make_checkpointer()
    return build_pipeline_graph().compile(checkpointer=checkpointer)


def _compile_single_job() -> "CompiledGraph":
    checkpointer = make_checkpointer()
    return build_single_job_graph().compile(checkpointer=checkpointer)


# Lazily compiled — imported by CLI and tests
pipeline_graph = _compile_pipeline()
single_job_graph = _compile_single_job()

# Default alias (used by existing tests that import `compiled_graph`)
compiled_graph = single_job_graph


# ---------------------------------------------------------------------------
# Graph visualization
# ---------------------------------------------------------------------------

def export_graph_png(path: Path = GRAPH_PNG_PATH) -> Path | None:
    """
    Export a PNG visualization of the FULL pipeline graph.

    Saved to `docs/agent_graph.png` by default (force-added past .gitignore).
    Returns the path if successful, None if export fails.

    Uses LangGraph's built-in Mermaid renderer — no graphviz needed.
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        png_bytes = pipeline_graph.get_graph().draw_mermaid_png()
        path.write_bytes(png_bytes)
        logger.info(f"[graph] Pipeline graph exported -> {path}")
        return path
    except Exception as e:
        logger.warning(f"[graph] Could not export graph PNG: {e}")
        return None


# Auto-export on import (only if file doesn't exist or is stale)
if not GRAPH_PNG_PATH.exists():
    export_graph_png()
