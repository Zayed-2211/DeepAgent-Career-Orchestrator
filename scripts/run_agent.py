"""
Agent CLI — Phase 6.

Run the LangGraph agent for one or more jobs from a processed JSON file.

Usage:
    python scripts/run_agent.py --job-file data/intelligence/2026-03-07/parsed_jobs.json
    python scripts/run_agent.py --job-file data/processed/2026-03-07/deduped_jobs.json --index 2
    python scripts/run_agent.py --job-file data/processed/2026-03-07/deduped_jobs.json --all
    python scripts/run_agent.py --export-graph   # Save agent_graph.png and exit

Options:
    --job-file FILE     Path to a JSON array of job records (Phase 3 or Phase 4 output).
    --index INT         Process only the job at this index (0-based). Default: 0.
    --all               Process ALL jobs in the file sequentially.
    --export-graph      Only export the graph PNG and exit. Does not run any jobs.
    --thread-id STR     LangGraph thread ID for checkpointing. Defaults to the job_uid.
"""

import argparse
import json
import sys
from pathlib import Path

from loguru import logger

# ── Ensure project root is on the path ────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.agent.graph import compiled_graph, export_graph_png
from src.agent.state import initial_state


# ---------------------------------------------------------------------------
# Record loading
# ---------------------------------------------------------------------------

def _load_records(path: str) -> list[dict]:
    """Load a JSON file that contains a list of job records."""
    p = Path(path)
    if not p.exists():
        logger.error(f"File not found: {p}")
        sys.exit(1)

    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        logger.error(f"Failed to read {p}: {e}")
        sys.exit(1)

    if not isinstance(data, list):
        logger.error(f"Expected a JSON array, got {type(data).__name__}")
        sys.exit(1)

    # Filter out metadata/instruction objects (those with _comment/_instructions)
    records = [r for r in data if isinstance(r, dict) and "name" not in r or "title" in r or "raw_title" in r]
    # Simpler: keep any dict that looks like a job (has title or description)
    records = [
        r for r in data
        if isinstance(r, dict)
        and ("title" in r or "raw_title" in r or "description" in r)
        and "_comment" not in r
        and "_instructions" not in r
    ]
    logger.info(f"Loaded {len(records)} job record(s) from {p.name}")
    return records


# ---------------------------------------------------------------------------
# Single-job runner
# ---------------------------------------------------------------------------

def run_one(record: dict, thread_id: str | None = None) -> dict:
    """
    Run the full agent graph for one job record.

    Args:
        record:    Raw or parsed job dict.
        thread_id: LangGraph thread ID for checkpointing. Defaults to job_uid.

    Returns:
        Final AgentState after graph execution.
    """
    uid = record.get("job_uid") or record.get("_split_from") or "unknown"
    tid = thread_id or uid.replace(":", "_").replace("/", "_")[:60]

    state = initial_state(raw_record=record)
    config: dict = {"configurable": {"thread_id": tid}}

    logger.info(f"[agent] ─── Running graph for thread_id={tid} ───")
    result = compiled_graph.invoke(state, config)
    logger.info(f"[agent] ─── Graph complete. Decision: {result.get('human_decision', '?').upper()} ───")
    return result


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="DeepAgent Career Orchestrator — Phase 6 Agent Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--job-file",
        metavar="FILE",
        help="Path to JSON array of job records (Phase 3 or Phase 4 output).",
    )
    parser.add_argument(
        "--index",
        type=int,
        default=0,
        metavar="N",
        help="Process only the job at index N (0-based). Default: 0.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        dest="process_all",
        help="Process ALL jobs in the file sequentially.",
    )
    parser.add_argument(
        "--export-graph",
        action="store_true",
        help="Export the agent graph as PNG and exit.",
    )
    parser.add_argument(
        "--thread-id",
        metavar="ID",
        help="LangGraph thread ID for checkpointing. Defaults to the job_uid.",
    )
    return parser


def main() -> None:
    args = _build_parser().parse_args()

    # ── Export graph only ──────────────────────────────────────────────────
    if args.export_graph:
        path = export_graph_png()
        if path:
            print(f"\n✅ Graph exported → {path}\n")
        else:
            print("\n⚠️  Graph export failed (graphviz may not be installed).\n")
        return

    # ── Need a job file for anything else ─────────────────────────────────
    if not args.job_file:
        print("❌ Please provide --job-file or --export-graph.\n")
        _build_parser().print_help()
        sys.exit(1)

    records = _load_records(args.job_file)
    if not records:
        logger.warning("No valid job records found in file.")
        return

    # ── Process all or single ─────────────────────────────────────────────
    if args.process_all:
        logger.info(f"Processing all {len(records)} record(s)...")
        for i, record in enumerate(records):
            print(f"\n{'='*60}")
            print(f"  Job {i + 1}/{len(records)}")
            print(f"{'='*60}")
            run_one(record, thread_id=args.thread_id)
    else:
        if args.index >= len(records):
            logger.error(f"--index {args.index} out of range (file has {len(records)} records).")
            sys.exit(1)
        run_one(records[args.index], thread_id=args.thread_id)


if __name__ == "__main__":
    main()
