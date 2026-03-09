"""
Local disk read/write utilities for the agent — Phase 6.

Provides safe, typed helpers for reading and writing JSON files
under the `data/` directory. These are used by agent nodes and tools
to persist intermediate results without touching the DB layer.

All paths must be under DATA_DIR for safety. Absolute paths outside
are rejected to prevent accidental writes to system files.
"""

import json
from pathlib import Path
from typing import Any

from loguru import logger

from config.settings import DATA_DIR


def read_json(path: str | Path) -> dict | list | None:
    """
    Read a JSON file and return its contents.

    Args:
        path: File path (relative to DATA_DIR, or absolute).

    Returns:
        Parsed JSON (dict or list), or None if file is missing/corrupt.
    """
    p = _resolve(path)
    if not p.exists():
        logger.warning(f"[disk_tool] File not found: {p}")
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        logger.error(f"[disk_tool] Failed to read {p}: {e}")
        return None


def write_json(path: str | Path, data: Any, *, indent: int = 2) -> bool:
    """
    Write data as JSON to a file, creating parent directories if needed.

    Args:
        path:   File path (relative to DATA_DIR, or absolute).
        data:   Python object to serialize.
        indent: JSON indentation (default 2).

    Returns:
        True on success, False on failure.
    """
    p = _resolve(path)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            json.dumps(data, indent=indent, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        logger.debug(f"[disk_tool] Written → {p}")
        return True
    except OSError as e:
        logger.error(f"[disk_tool] Failed to write {p}: {e}")
        return False


def ensure_dir(path: str | Path) -> Path:
    """Create a directory (and parents) if it doesn't exist. Returns the Path."""
    p = _resolve(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def _resolve(path: str | Path) -> Path:
    """
    Resolve a path to an absolute Path.

    If the path is relative, it is resolved relative to DATA_DIR.
    Absolute paths are used as-is.
    """
    p = Path(path)
    if not p.is_absolute():
        p = DATA_DIR / p
    return p.resolve()
