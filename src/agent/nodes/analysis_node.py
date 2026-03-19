"""
Analysis node for Phase 6.

Parses the current job record with JobParser and persists agent-run
intelligence artifacts for debugging and traceability.
"""

from loguru import logger

from src.agent.intelligence_artifacts import (
    append_parsed_job,
    append_run_log,
    update_run_status,
)
from src.agent.state import AgentState
from src.intelligence.job_parser import JobParser


_PARSER: JobParser | None = None


def _get_parser() -> JobParser:
    """Lazily initialize the parser singleton."""
    global _PARSER
    if _PARSER is None:
        _PARSER = JobParser()
    return _PARSER


def analysis_node(state: AgentState) -> AgentState:
    """
    Parse and extract intelligence from the current job record.

    State out: current_job with scout/intelligence fields populated.
    """
    record = state.get("current_job") or {}

    # Fast path for records that are already parsed.
    if record.get("scout") and record.get("scout", {}).get("is_job_posting") is not None:
        logger.info("[analysis] Skipping - record already has scout data.")
        append_parsed_job(record)
        append_run_log(
            "analysis skipped | "
            f"job_uid={record.get('job_uid')} | reason=already_parsed"
        )
        update_run_status(
            "running",
            {"stage": "analysis", "job_uid": record.get("job_uid"), "result": "already_parsed"},
        )
        return state

    title = (record.get("raw_title") or record.get("title") or "no title")[:60]
    logger.info(f"[analysis] Parsing job: {title}")

    try:
        parser = _get_parser()
        parsed = parser.parse(record)

        enriched = {
            **record,
            "scout": parsed.scout.model_dump() if parsed.scout else None,
            "intelligence": parsed.intelligence.model_dump() if parsed.intelligence else None,
            "record_type": parsed.record_type,
            "parse_error": parsed.parse_error,
            "model_used": parsed.model_used,
        }

        append_parsed_job(enriched)

        if parsed.parse_error:
            logger.warning(f"[analysis] Parse error: {parsed.parse_error[:100]}")
            append_run_log(
                "analysis parse_error | "
                f"job_uid={enriched.get('job_uid')} | "
                f"title={title} | "
                f"error={parsed.parse_error[:160]}"
            )
            update_run_status(
                "running",
                {
                    "stage": "analysis",
                    "job_uid": enriched.get("job_uid"),
                    "title": title,
                    "result": "parse_error",
                },
            )
            return {
                **state,
                "current_job": enriched,
                "error": parsed.parse_error,
            }

        is_job = parsed.scout and parsed.scout.is_job_posting
        logger.info(
            f"[analysis] Parsed OK | is_job_posting={is_job} | "
            f"record_type={parsed.record_type}"
        )
        append_run_log(
            "analysis complete | "
            f"job_uid={enriched.get('job_uid')} | "
            f"title={title} | "
            f"is_job_posting={is_job} | "
            f"record_type={parsed.record_type}"
        )
        update_run_status(
            "running",
            {
                "stage": "analysis",
                "job_uid": enriched.get("job_uid"),
                "title": title,
                "result": "parsed",
                "record_type": parsed.record_type,
                "is_job_posting": is_job,
            },
        )
        return {**state, "current_job": enriched}

    except Exception as exc:
        err = str(exc)[:200]
        logger.error(f"[analysis] Unexpected error: {err}")
        append_run_log(f"analysis failed | title={title} | error={err}")
        update_run_status("error", {"stage": "analysis", "title": title, "error": err})
        return {**state, "error": err}
