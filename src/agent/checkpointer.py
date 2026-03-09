"""
Checkpointer — Phase 6.

Thin wrapper around LangGraph's MemorySaver.

Why not SqliteSaver?
  MemorySaver is kept in-RAM for development. Phase 9 replaces it
  with a cloud-backed Supabase checkpointer. For a session that
  survives process restarts, the CLI packs/unpacks state to a JSON
  file in data/state/checkpoints/.

Usage:
    from src.agent.checkpointer import make_checkpointer
    checkpointer = make_checkpointer()
    # Pass to StateGraph.compile(checkpointer=checkpointer)
"""

import json
from pathlib import Path

from langgraph.checkpoint.memory import MemorySaver
from loguru import logger

from config.settings import DATA_DIR


# Default directory for file-based checkpoint snapshots
CHECKPOINT_DIR = DATA_DIR / "state" / "checkpoints"


def make_checkpointer() -> MemorySaver:
    """
    Create a fresh MemorySaver instance for development use.

    Note: MemorySaver is in-process only — state is lost on restart.
    For persistence across runs, use save_checkpoint() / load_checkpoint()
    to serialise the thread state to disk between runs.
    """
    return MemorySaver()


def save_checkpoint(thread_id: str, state: dict) -> Path:
    """
    Save the current agent state for a thread to disk.

    file: data/state/checkpoints/{thread_id}.json

    Returns the written file path.
    """
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    path = CHECKPOINT_DIR / f"{thread_id}.json"
    path.write_text(
        json.dumps(state, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    logger.debug(f"[checkpointer] Saved checkpoint → {path}")
    return path


def load_checkpoint(thread_id: str) -> dict | None:
    """
    Load agent state for a thread from disk.

    Returns the state dict, or None if no checkpoint exists.
    """
    path = CHECKPOINT_DIR / f"{thread_id}.json"
    if not path.exists():
        return None
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
        logger.debug(f"[checkpointer] Loaded checkpoint ← {path}")
        return state
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"[checkpointer] Failed to load checkpoint {path}: {e}")
        return None


def clear_checkpoint(thread_id: str) -> bool:
    """Delete a checkpoint file. Returns True if deleted, False if not found."""
    path = CHECKPOINT_DIR / f"{thread_id}.json"
    if path.exists():
        path.unlink()
        logger.debug(f"[checkpointer] Cleared checkpoint: {thread_id}")
        return True
    return False
