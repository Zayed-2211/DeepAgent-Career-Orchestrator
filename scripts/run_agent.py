"""
Agent CLI - Phase 6 / 6.5.

MODES:
  --pipeline          Full pipeline: scrape -> dedup -> loop through all jobs.

  --job-file FILE     Single-file mode: load jobs from a JSON file and loop
                      through them one by one. No scraping.
  --index N           (with --job-file) Process only job at index N. Default: 0.
  --all               (with --job-file) Process ALL jobs in the file.

  --export-graph      Export docs/agent_graph.png and exit.

OPTIONS:
  --thread-id STR     LangGraph thread ID for checkpointing.
                      Pipeline mode default: today's date (YYYY-MM-DD).
                      Single-job mode default: job_uid.

EXAMPLES:
  # Full pipeline (live scrape)
  python scripts/run_agent.py --pipeline --dev 5

  # Process jobs from an existing intelligence file
  python scripts/run_agent.py --job-file data/intelligence/2026-03-09/parsed_jobs.json --all

  # Single job at index 2
  python scripts/run_agent.py --job-file data/processed/2026-03-09/deduped_jobs.json --index 2

  # Re-export the graph PNG
  python scripts/run_agent.py --export-graph
"""

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

from loguru import logger

# Ensure project root is on the path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# ---------------------------------------------------------------------------
# Record loading helpers
# ---------------------------------------------------------------------------

def _load_records(path: str) -> list[dict]:
    """Load a JSON array of job records from disk. Filters metadata objects."""
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
        logger.error(f"Expected JSON array, got {type(data).__name__}")
        sys.exit(1)

    # Filter metadata/placeholder objects
    records = [
        r
        for r in data
        if isinstance(r, dict)
        and ("title" in r or "raw_title" in r or "description" in r)
        and "_comment" not in r
        and "_instructions" not in r
    ]
    logger.info(f"Loaded {len(records)} job record(s) from {p.name}")
    return records


# ---------------------------------------------------------------------------
# Pre-run profile sync (best effort, warn-and-continue)
# ---------------------------------------------------------------------------

def _auto_sync_cv_projects() -> None:
    """Sync CV projects before runs. Never abort this runner on sync issues."""
    # Skip in dev mode to preserve Gemini quota for pipeline
    if os.environ.get("DEV_MODE_LIMIT"):
        logger.info("[agent] Skipping CV sync in dev mode (preserving Gemini quota)")
        return
    
    try:
        from scripts.sync_cv_projects import sync_cv_projects
    except Exception as exc:
        logger.warning(f"[agent] Could not import CV sync helper: {exc}")
        return

    try:
        logger.info("[agent] Syncing CV projects before run...")
        sync_cv_projects(dry_run=False, force=False)
    except SystemExit as exc:
        logger.warning(f"[agent] CV sync exited early (code={exc.code}). Continuing run.")
    except Exception as exc:
        logger.warning(f"[agent] CV sync failed ({exc}). Continuing run.")


# ---------------------------------------------------------------------------
# Pipeline mode (full scrape -> dedup -> loop)
# ---------------------------------------------------------------------------

def run_pipeline(thread_id: str | None = None, dev_limit: int | None = None) -> dict:
    """
    Run the full pipeline graph: scout -> dedup -> loop.

    Uses pipeline_graph (9 nodes, 2 visible loops).
    If dev_limit is set, runs in Dev Mode with a live scrape budget.
    """
    # Dev Mode setup (must be before CV sync to skip it in dev mode)
    if dev_limit is not None:
        os.environ["DEV_MODE_LIMIT"] = str(dev_limit)
        logger.info(f"[agent] --- DEV MODE ACTIVE (Limit: {dev_limit}) ---")
        logger.info("[agent] Dev Mode: live scraping only. Cached/mock reuse is disabled.")
    
    _auto_sync_cv_projects()

    # Import graph/state lazily so optional deps do not crash at module import time.
    from src.agent.intelligence_artifacts import (
        append_run_log,
        clear_agent_run,
        prepare_agent_run,
        update_run_status,
    )
    from src.agent.graph import pipeline_graph
    from src.agent.state import pipeline_initial_state

    # Pipeline mode should always use live scraping.
    os.environ.pop("MOCK_SCRAPER", None)
    os.environ.pop("MOCK_SCRAPER_FILE", None)
    os.environ.pop("DEV_FORCE_RESCRAPE", None)

    tid = thread_id or f"pipeline-{date.today().isoformat()}"
    state = pipeline_initial_state()
    config: dict = {"configurable": {"thread_id": tid}}
    prepare_agent_run(tid, mode="pipeline")

    logger.info(f"[agent] --- PIPELINE MODE | thread_id={tid} ---")
    try:
        result = pipeline_graph.invoke(state, config)
        stats = result.get("pipeline_stats", {})
        logger.info(
            f"[agent] --- Pipeline done. "
            f"Total={stats.get('total', 0)} "
            f"Approved={stats.get('approved', 0)} "
            f"Rejected={stats.get('rejected', 0)} "
            f"Skipped={stats.get('skipped', 0)} ---"
        )
        append_run_log(
            "run finished | "
            f"raw_scraped={stats.get('raw_scraped', 0)} | "
            f"total={stats.get('total', 0)} | "
            f"approved={stats.get('approved', 0)} | "
            f"rejected={stats.get('rejected', 0)} | "
            f"skipped={stats.get('skipped', 0)}"
        )
        update_run_status("done", {"pipeline_stats": stats})
        return result
    except Exception as exc:
        append_run_log(f"run failed | error={str(exc)[:300]}")
        update_run_status("error", {"error": str(exc)[:300]})
        raise
    finally:
        clear_agent_run()


# ---------------------------------------------------------------------------
# Single-file mode (loop through jobs from a file)
# ---------------------------------------------------------------------------

def run_file(job_file: str, index: int | None, process_all: bool, thread_id: str | None) -> None:
    """
    Load records from a JSON file and process them via single_job_graph.

    If `process_all` is True, loads ALL records into the queue.
    If `index` is provided, loads only that one record.
    """
    _auto_sync_cv_projects()

    # Lazy import keeps runner import safe when optional graph deps are missing.
    from src.agent.intelligence_artifacts import (
        append_run_log,
        clear_agent_run,
        prepare_agent_run,
        update_run_status,
    )
    from src.agent.graph import single_job_graph
    from src.agent.state import initial_state

    records = _load_records(job_file)

    if not records:
        logger.warning("No valid job records found in file.")
        return

    if process_all:
        # Load all records into queue, let loop_controller process them.
        logger.info(f"[agent] --- FILE MODE (all {len(records)} jobs) ---")
        state = initial_state()
        state["job_queue"] = records
        state["pipeline_stats"] = {
            "total": len(records),
            "skipped": 0,
            "approved": 0,
            "rejected": 0,
            "errors": 0,
        }
        tid = thread_id or f"file-all-{date.today().isoformat()}"
        config: dict = {"configurable": {"thread_id": tid}}
        prepare_agent_run(tid, mode="job-file-all")
        try:
            single_job_graph.invoke(state, config)
            append_run_log(f"run finished | mode=job-file-all | total={len(records)}")
            update_run_status("done", {"input_records": len(records)})
        except Exception as exc:
            append_run_log(f"run failed | error={str(exc)[:300]}")
            update_run_status("error", {"error": str(exc)[:300]})
            raise
        finally:
            clear_agent_run()

    else:
        idx = index or 0
        if idx >= len(records):
            logger.error(f"--index {idx} out of range (file has {len(records)} records).")
            sys.exit(1)

        record = records[idx]
        title = record.get("raw_title") or record.get("title") or "?"
        logger.info(f"[agent] --- FILE MODE (index={idx}: {title[:60]}) ---")

        state = initial_state(raw_record=record)
        uid = record.get("job_uid") or f"job-{idx}"
        tid = thread_id or uid.replace(":", "_").replace("/", "_")[:60]
        config: dict = {"configurable": {"thread_id": tid}}
        prepare_agent_run(tid, mode="job-file-single")
        try:
            single_job_graph.invoke(state, config)
            append_run_log(f"run finished | mode=job-file-single | index={idx}")
            update_run_status("done", {"input_index": idx})
        except Exception as exc:
            append_run_log(f"run failed | error={str(exc)[:300]}")
            update_run_status("error", {"error": str(exc)[:300]})
            raise
        finally:
            clear_agent_run()


# ---------------------------------------------------------------------------
# CLI argument parser
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="DeepAgent Career Orchestrator - Agent Runner (Phase 6 / 6.5)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--pipeline",
        action="store_true",
        help="Full pipeline mode: live scrape -> dedup -> process all jobs.",
    )
    mode.add_argument(
        "--job-file",
        metavar="FILE",
        help="Path to JSON array of job records (Phase 3 or Phase 4 output).",
    )
    mode.add_argument(
        "--export-graph",
        action="store_true",
        help="Export the full pipeline agent graph as PNG and exit.",
    )
    parser.add_argument(
        "--index",
        type=int,
        default=None,
        metavar="N",
        help="(--job-file) Process only the job at index N (0-based).",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        dest="process_all",
        help="(--job-file) Process ALL jobs in the file.",
    )
    parser.add_argument(
        "--thread-id",
        metavar="ID",
        help="LangGraph thread ID for checkpointing.",
    )
    parser.add_argument(
        "--dev",
        type=int,
        nargs="?",
        const=5,
        metavar="N",
        help=(
            "Run in Developer Economy Mode. Applies a global scrape/process budget of N jobs "
            "(default 5). Always uses live scraping."
        ),
    )
    return parser


def main() -> None:
    args = _build_parser().parse_args()

    # Export graph only
    if args.export_graph:
        from src.agent.graph import export_graph_png

        path = export_graph_png()
        if path:
            print(f"\n  Graph exported -> {path}\n")
        else:
            print("\n  Graph export failed (graphviz/playwright may not be installed).\n")
        return

    # Full pipeline mode
    if args.pipeline:
        run_pipeline(thread_id=args.thread_id, dev_limit=args.dev)
        return

    # File mode
    if args.job_file:
        run_file(
            job_file=args.job_file,
            index=args.index,
            process_all=args.process_all,
            thread_id=args.thread_id,
        )
        return

    # No mode selected
    print("\nPlease provide --pipeline, --job-file, or --export-graph.\n")
    _build_parser().print_help()
    sys.exit(1)


if __name__ == "__main__":
    main()
