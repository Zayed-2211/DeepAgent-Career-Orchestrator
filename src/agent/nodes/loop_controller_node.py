"""
Loop Controller Node — Phase 6.5.

The heart of the multi-job processing loop. This node:
  1. Pops the next record from `state["job_queue"]`
  2. Places it in `state["current_job"]` for the downstream nodes
  3. Increments the loop counter
  4. Prints a rich progress summary
  5. Routes to "next_job" (continue loop) or "done" (queue exhausted)

Loop pattern in LangGraph:
    loop_controller ──next_job──▶ intake_node ──▶ ... ──▶ dispatch_node
          ▲                                                       │
          └─────────────────── (routing = "loop") ───────────────┘

The loop also receives "loop" routing after intake_node skips a duplicate,
avoiding unnecessary processing and immediately going back here.

State in:  job_queue, current_job_index, pipeline_stats
State out: current_job (next job), job_queue (popped), current_job_index++,
           routing ("next_job" | "done")
"""

from loguru import logger
from rich.console import Console
from rich import box
from rich.panel import Panel

from src.agent.state import AgentState


console = Console()


def loop_controller_node(state: AgentState) -> AgentState:
    """
    Pop the next job from the queue and route accordingly.

    - If queue is non-empty: pop, set current_job, route "next_job"
    - If queue is empty:     print final summary, route "done"

    State in:  job_queue, current_job_index, pipeline_stats
    State out: current_job, job_queue, current_job_index, routing
    """
    import os

    queue = list(state.get("job_queue") or [])
    
    # ---- Dev Mode Limit ----
    dev_limit_str = os.environ.get("DEV_MODE_LIMIT")
    dev_limit = int(dev_limit_str) if dev_limit_str else None
    if dev_limit is not None and queue and len(queue) > dev_limit:
        logger.warning(f"[loop] DEV MODE: Truncating queue from {len(queue)} to {dev_limit} jobs.")
        queue = queue[:dev_limit]

    idx = state.get("current_job_index", 0)
    stats = dict(state.get("pipeline_stats") or {})
    total = stats.get("total", len(queue) + idx)
    
    # Adjust total if we truncated
    if dev_limit is not None and total > dev_limit:
        total = dev_limit
        stats["total"] = dev_limit

    # ---- Queue exhausted → done ----
    if not queue:
        _print_final_summary(stats, total)
        return {
            **state,
            "job_queue": [],
            "routing": "done",
        }

    # ---- Pop next job ----
    next_job = queue.pop(0)  # FIFO — always take the oldest record first
    new_idx = idx + 1

    title = (
        next_job.get("raw_title")
        or next_job.get("title")
        or (next_job.get("scout") or {}).get("role_title")
        or "Unknown Role"
    )[:60]

    # Progress bar (simple ASCII)
    processed = new_idx - 1
    total_display = max(total, new_idx)
    bar_filled = int((processed / total_display) * 20) if total_display else 0
    bar = "█" * bar_filled + "░" * (20 - bar_filled)

    console.print()
    console.print(Panel(
        f"[bold cyan]Job {new_idx} / {total_display}[/]  [{bar}]  [dim]{title}[/]\n"
        f"  [green]✓ Approved:[/] {stats.get('approved', 0)}   "
        f"[red]✗ Rejected:[/] {stats.get('rejected', 0)}   "
        f"[yellow]⟳ Skipped:[/] {stats.get('skipped', 0)}   "
        f"[dim]Remaining: {len(queue)}[/]",
        border_style="cyan",
        expand=False,
    ))

    logger.info(
        f"[loop] Job {new_idx}/{total_display} — "
        f"{title} | queue remaining: {len(queue)}"
    )

    return {
        **state,
        "current_job": next_job,
        "job_queue": queue,
        "current_job_index": new_idx,
        # Reset per-job fields for the new iteration
        "job_uid": None,
        "matched_projects": [],
        "match_score": 0.0,
        "todo_list": [],
        "human_decision": "pending",
        "generated_docs": {},
        "error": None,
        "routing": "next_job",
        "metadata": {},
    }


def route_after_loop_controller(state: AgentState) -> str:
    """Conditional edge: 'next_job' to continue loop, 'done' to end."""
    return state.get("routing", "done")


def _print_final_summary(stats: dict, total: int) -> None:
    """Print a final summary panel when all jobs are processed."""
    console.print()
    console.rule("[bold green]Pipeline Complete[/]")
    console.print(Panel(
        f"  [bold]Total Jobs Processed:[/] {total}\n"
        f"  [green]Approved :[/] {stats.get('approved', 0)}\n"
        f"  [red]Rejected :[/] {stats.get('rejected', 0)}\n"
        f"  [yellow]Skipped  :[/] {stats.get('skipped', 0)}\n"
        f"  [dim]Errors   :[/] {stats.get('errors', 0)}",
        title="[bold green]Summary[/]",
        border_style="green",
        expand=False,
    ))
    console.print()
