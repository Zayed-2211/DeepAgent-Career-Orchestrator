"""
Helpers for writing agent-run intelligence artifacts to data/intelligence/{date}/.
"""

from __future__ import annotations

import json
import os
from datetime import date, datetime, timezone
from pathlib import Path

from loguru import logger

from config.settings import DATA_DIR


_ENV_DAY_DIR = "AGENT_INTELLIGENCE_DAY_DIR"
_ENV_RUN_FILE = "AGENT_INTELLIGENCE_RUN_FILE"
_ENV_STATUS_FILE = "AGENT_INTELLIGENCE_STATUS_FILE"
_ENV_LOG_FILE = "AGENT_INTELLIGENCE_LOG_FILE"
_ENV_PARSED_FILE = "AGENT_INTELLIGENCE_PARSED_FILE"
_ENV_STARTED_AT = "AGENT_INTELLIGENCE_STARTED_AT"
_ENV_THREAD_ID = "AGENT_INTELLIGENCE_THREAD_ID"


def prepare_agent_run(thread_id: str, mode: str) -> dict[str, Path]:
    """Create intelligence artifacts for the current agent run and expose them via env."""
    day_dir = DATA_DIR / "intelligence" / date.today().isoformat()
    day_dir.mkdir(parents=True, exist_ok=True)

    started_at = datetime.now(timezone.utc)
    safe_thread = _sanitize_thread_id(thread_id)
    run_file = day_dir / f"agent_run_{started_at.strftime('%H-%M-%S')}_{safe_thread}.json"
    status_file = day_dir / "run_status.json"
    log_file = day_dir / "run_log.txt"
    parsed_file = day_dir / "parsed_jobs.json"

    os.environ[_ENV_DAY_DIR] = str(day_dir)
    os.environ[_ENV_RUN_FILE] = str(run_file)
    os.environ[_ENV_STATUS_FILE] = str(status_file)
    os.environ[_ENV_LOG_FILE] = str(log_file)
    os.environ[_ENV_PARSED_FILE] = str(parsed_file)
    os.environ[_ENV_STARTED_AT] = started_at.isoformat()
    os.environ[_ENV_THREAD_ID] = thread_id

    update_run_status(
        "running",
        {
            "mode": mode,
            "thread_id": thread_id,
            "run_file": run_file.name,
            "started_at": started_at.strftime("%Y-%m-%d %H:%M:%S UTC"),
        },
    )
    append_run_log(f"run started | mode={mode} | thread_id={thread_id}")

    return {
        "day_dir": day_dir,
        "run_file": run_file,
        "status_file": status_file,
        "log_file": log_file,
        "parsed_file": parsed_file,
    }


def clear_agent_run() -> None:
    """Clear per-run environment variables after the pipeline finishes."""
    for key in (
        _ENV_DAY_DIR,
        _ENV_RUN_FILE,
        _ENV_STATUS_FILE,
        _ENV_LOG_FILE,
        _ENV_PARSED_FILE,
        _ENV_STARTED_AT,
        _ENV_THREAD_ID,
    ):
        os.environ.pop(key, None)


def append_run_log(message: str) -> None:
    """Append a timestamped line to the current agent run log."""
    log_file = _path_from_env(_ENV_LOG_FILE)
    if not log_file:
        return

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with open(log_file, "a", encoding="utf-8") as handle:
        handle.write(f"[{timestamp}] {message}\n")


def update_run_status(status: str, extra: dict | None = None) -> None:
    """Write or overwrite the current run status JSON."""
    status_file = _path_from_env(_ENV_STATUS_FILE)
    if not status_file:
        return

    payload = {
        "status": status,
        "thread_id": os.environ.get(_ENV_THREAD_ID),
        "started_at": os.environ.get(_ENV_STARTED_AT),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if extra:
        payload.update(extra)

    status_file.parent.mkdir(parents=True, exist_ok=True)
    with open(status_file, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False, default=str)


def append_parsed_job(record: dict) -> None:
    """Append one parsed record to both the per-run file and the daily parsed_jobs file."""
    run_file = _path_from_env(_ENV_RUN_FILE)
    parsed_file = _path_from_env(_ENV_PARSED_FILE)
    if not run_file or not parsed_file:
        return

    _append_to_json_array(run_file, record)
    _merge_into_daily(parsed_file, record)


def _append_to_json_array(path: Path, record: dict) -> None:
    data = _load_json_array(path)
    data.append(record)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False, default=str)


def _merge_into_daily(path: Path, record: dict) -> None:
    data = _load_json_array(path)
    uid = record.get("job_uid")

    if uid:
        replaced = False
        for index, existing in enumerate(data):
            if existing.get("job_uid") == uid:
                data[index] = record
                replaced = True
                break
        if not replaced:
            data.append(record)
    else:
        data.append(record)

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False, default=str)


def _load_json_array(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, list) else []
    except Exception as exc:
        logger.warning(f"[agent_artifacts] Could not read {path}: {exc}")
        return []


def _path_from_env(name: str) -> Path | None:
    raw = os.environ.get(name)
    return Path(raw) if raw else None


def _sanitize_thread_id(thread_id: str) -> str:
    safe = thread_id.replace(":", "_").replace("/", "_").replace("\\", "_")
    safe = safe.replace(" ", "_")
    return safe[:60] or "agent"
