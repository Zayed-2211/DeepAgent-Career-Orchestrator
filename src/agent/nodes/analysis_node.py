"""
Analysis Node — Phase 6.

Calls Phase 4's JobParser to extract structured intelligence from the
raw job description. This is the most expensive node (1 Gemini API call).

State in:  current_job (raw dict, possibly already a ParsedJob from Phase 4)
State out: current_job (updated with .scout and .intelligence populated)
"""

from loguru import logger

from src.agent.state import AgentState
from src.intelligence.job_parser import JobParser


# Create the parser once per process (avoids rebuilding LangChain chains each time)
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

    State in:  current_job (dict — raw or partially parsed)
    State out: current_job (updated: .scout and .intelligence filled in)

    If the record already has intelligence data (i.e., it came from a
    Phase 4 output file), parsing is skipped to avoid a redundant API call.
    """
    record = state.get("current_job") or {}

    # --- Fast path: already parsed (e.g. from data/intelligence/*.json) ---
    if record.get("scout") and record.get("scout", {}).get("is_job_posting") is not None:
        logger.info("[analysis] Skipping — record already has scout data.")
        return state

    title = (record.get("raw_title") or record.get("title") or "no title")[:60]
    logger.info(f"[analysis] Parsing job: {title}")

    try:
        parser = _get_parser()
        parsed = parser.parse(record)

        enriched = {
            **record,
            # Merge ParsedJob fields back into the flat dict
            "scout": parsed.scout.model_dump() if parsed.scout else None,
            "intelligence": parsed.intelligence.model_dump() if parsed.intelligence else None,
            "record_type": parsed.record_type,
            "parse_error": parsed.parse_error,
            "model_used": parsed.model_used,
        }

        if parsed.parse_error:
            logger.warning(f"[analysis] Parse error: {parsed.parse_error[:100]}")
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
        return {**state, "current_job": enriched}

    except Exception as e:
        err = str(e)[:200]
        logger.error(f"[analysis] Unexpected error: {err}")
        return {**state, "error": err}
