"""
LangGraph Agent Graph — Phase 6.

Wires all agent nodes into a compiled StateGraph:

    [START]
       │
    intake_node ──skip──▶ [END]
       │continue
    analysis_node
       │
    matching_node
       │
    planning_node
       │
    review_node ──reject──▶ dispatch_node ──▶ [END]
       │approve
    dispatch_node ──▶ [END]

After compilation, the graph is exported as a PNG to:
    docs/agent_graph.png

Usage:
    from src.agent.graph import compiled_graph, build_graph

    # Run for one job:
    config = {"configurable": {"thread_id": "job-001"}}
    result = compiled_graph.invoke(initial_state(raw_record), config)
"""

from pathlib import Path

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, StateGraph
from loguru import logger

from src.agent.checkpointer import make_checkpointer
from src.agent.nodes.analysis_node import analysis_node
from src.agent.nodes.dispatch_node import dispatch_node
from src.agent.nodes.intake_node import intake_node, route_after_intake
from src.agent.nodes.matching_node import matching_node
from src.agent.nodes.planning_node import planning_node
from src.agent.nodes.review_node import review_node, route_after_review
from src.agent.state import AgentState


# ---------------------------------------------------------------------------
# Output path for graph visualization
# ---------------------------------------------------------------------------
_DOCS_DIR = Path(__file__).resolve().parent.parent.parent / "docs"
GRAPH_PNG_PATH = _DOCS_DIR / "agent_graph.png"


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------

def build_graph() -> StateGraph:
    """
    Build and return the compiled LangGraph StateGraph.

    Nodes:
        intake_node    → runs first on every job
        analysis_node  → Gemini intelligence extraction
        matching_node  → keyword overlap project matching
        planning_node  → builds the todo list
        review_node    → human-in-the-loop gate
        dispatch_node  → writes approve/reject output files

    Edges:
        intake → (conditional) → skip → END
                                → continue → analysis
        review → (conditional) → approve → dispatch → END
                                → reject  → dispatch → END
    """
    workflow = StateGraph(AgentState)

    # --- Register all nodes ---
    workflow.add_node("intake", intake_node)
    workflow.add_node("analysis", analysis_node)
    workflow.add_node("matching", matching_node)
    workflow.add_node("planning", planning_node)
    workflow.add_node("review", review_node)
    workflow.add_node("dispatch", dispatch_node)

    # --- Entry point ---
    workflow.set_entry_point("intake")

    # --- Conditional edge: after intake ---
    workflow.add_conditional_edges(
        "intake",
        route_after_intake,
        {
            "skip": END,         # duplicate → stop immediately
            "continue": "analysis",
        },
    )

    # --- Linear path through analysis → matching → planning → review ---
    workflow.add_edge("analysis", "matching")
    workflow.add_edge("matching", "planning")
    workflow.add_edge("planning", "review")

    # --- Conditional edge: after review ---
    workflow.add_conditional_edges(
        "review",
        route_after_review,
        {
            "approve": "dispatch",
            "reject": "dispatch",   # both go to dispatch — it handles the split
        },
    )

    # --- Final edge: dispatch → END ---
    workflow.add_edge("dispatch", END)

    return workflow


# ---------------------------------------------------------------------------
# Compiled graph (singleton, shared by CLI)
# ---------------------------------------------------------------------------

def _compile() -> "CompiledStateGraph":
    checkpointer = make_checkpointer()
    graph = build_graph()
    return graph.compile(checkpointer=checkpointer)


compiled_graph = _compile()


# ---------------------------------------------------------------------------
# Graph visualization
# ---------------------------------------------------------------------------

def export_graph_png(path: Path = GRAPH_PNG_PATH) -> Path | None:
    """
    Export a PNG visualization of the agent graph.

    Saved to `docs/agent_graph.png` by default.
    Returns the path if successful, None if export fails.

    Requires the `graphviz` system package. LangGraph falls back to
    Mermaid if graphviz is unavailable.
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        png_bytes = compiled_graph.get_graph().draw_mermaid_png()
        path.write_bytes(png_bytes)
        logger.info(f"[graph] Agent graph exported → {path}")
        return path
    except Exception as e:
        logger.warning(f"[graph] Could not export graph PNG: {e}")
        return None


# Auto-export on import if the file doesn't exist yet
if not GRAPH_PNG_PATH.exists():
    export_graph_png()
