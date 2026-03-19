"""
Dedup node for pipeline mode.

Consumes state["raw_records"], runs the dedup pipeline, and stores unique
records in state["job_queue"] for the processing loop.
"""

from loguru import logger

from src.agent.intelligence_artifacts import append_run_log, update_run_status
from src.agent.state import AgentState
from src.dedup.pipeline import DeduplicationPipeline


def dedup_node(state: AgentState) -> AgentState:
    """
    Run the deduplication pipeline on raw_records from scout_node.

    State out: job_queue, pipeline_stats
    """
    raw_records = state.get("raw_records") or []

    if not raw_records:
        logger.warning("[dedup] No raw records to deduplicate - job_queue will be empty.")
        append_run_log("dedup complete | raw_records=0 | unique_records=0")
        update_run_status("done", {"stage": "dedup", "raw_records": 0, "unique_records": 0})
        return {
            **state,
            "job_queue": [],
        }

    logger.info(f"[dedup] Running dedup pipeline on {len(raw_records)} record(s)...")

    try:
        pipeline = DeduplicationPipeline()
        result = pipeline.run(raw_records, output_path=None)

        unique_records: list[dict] = result.get("unique_records") or []
        total_after = len(unique_records)

        logger.info(
            f"[dedup] Complete - {total_after} unique record(s) after dedup "
            f"(from {len(raw_records)} raw)."
        )
        append_run_log(
            "dedup complete | "
            f"raw_records={len(raw_records)} | "
            f"unique_records={total_after} | "
            f"uid_dupes={result.get('uid_dupes_skipped', 0)} | "
            f"fingerprint_dupes={result.get('fingerprint_dupes_skipped', 0)} | "
            f"fuzzy_dupes={result.get('fuzzy_dupes_skipped', 0)}"
        )
        update_run_status(
            "running",
            {
                "stage": "dedup",
                "raw_records": len(raw_records),
                "unique_records": total_after,
                "uid_dupes_skipped": result.get("uid_dupes_skipped", 0),
                "fingerprint_dupes_skipped": result.get("fingerprint_dupes_skipped", 0),
                "fuzzy_dupes_skipped": result.get("fuzzy_dupes_skipped", 0),
            },
        )

        current_stats = state.get("pipeline_stats") or {}
        return {
            **state,
            "job_queue": unique_records,
            "pipeline_stats": {
                **current_stats,
                "total": total_after,
                "raw_scraped": len(raw_records),
            },
        }

    except Exception as exc:
        err = str(exc)[:300]
        logger.error(f"[dedup] Pipeline failed: {err}")
        logger.warning("[dedup] Falling back to raw records (no deduplication).")
        append_run_log(f"dedup failed | error={err} | fallback=raw_records")
        update_run_status("error", {"stage": "dedup", "error": err})
        return {
            **state,
            "job_queue": raw_records,
            "error": f"dedup_node failed (using raw): {err}",
        }
