"""
In-memory todo-list tool for the agent — Phase 6.

The planning node creates a structured task list that:
  1. Tracks what the agent has already done (marked ✓)
  2. Tracks what sub-agents still need to do (marked ⬜)

The list is stored in `AgentState.todo_list` and updated by nodes.
Persisted automatically via LangGraph checkpointing.
"""

from typing import Literal

# Prefix tokens for display
_DONE_PREFIX = "✓"
_TODO_PREFIX = "⬜"


def create_todo(items: list[str], *, done: bool = False) -> list[str]:
    """
    Create a new todo list.

    Args:
        items: List of task descriptions.
        done:  If True, mark all items as done.

    Returns:
        List of prefixed task strings.

    Example:
        create_todo(["Extract info", "Find projects"]) →
            ["⬜ Extract info", "⬜ Find projects"]
    """
    prefix = _DONE_PREFIX if done else _TODO_PREFIX
    return [f"{prefix} {item.lstrip('✓⬜ ')}" for item in items]


def mark_done(todo_list: list[str], item_substring: str) -> list[str]:
    """
    Mark the first item whose text contains `item_substring` as done.

    Args:
        todo_list:      Current todo list.
        item_substring: Substring to search for (case-insensitive).

    Returns:
        Updated todo list with the matching item marked done.
    """
    result = []
    lower = item_substring.lower()
    marked = False
    for item in todo_list:
        if not marked and lower in item.lower() and not item.startswith(_DONE_PREFIX):
            item = f"{_DONE_PREFIX} {item.lstrip('✓⬜ ')}"
            marked = True
        result.append(item)
    return result


def get_pending(todo_list: list[str]) -> list[str]:
    """Return only unfinished tasks from the todo list."""
    return [item for item in todo_list if item.startswith(_TODO_PREFIX)]


def get_done(todo_list: list[str]) -> list[str]:
    """Return only completed tasks from the todo list."""
    return [item for item in todo_list if item.startswith(_DONE_PREFIX)]


def format_list(todo_list: list[str]) -> str:
    """Format the todo list as a human-readable string."""
    return "\n".join(f"  {item}" for item in todo_list)


def progress(todo_list: list[str]) -> str:
    """Return a progress string like '2/4 tasks completed'."""
    total = len(todo_list)
    done = len(get_done(todo_list))
    return f"{done}/{total} tasks completed"
