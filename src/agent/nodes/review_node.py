"""
Review Node — Phase 6 — Human-in-the-Loop Gate.

Presents a rich summary of the matched job to the user and waits for a
decision before any CV generation or application takes place.

This node is the trust boundary of the entire system.
Nothing is sent/applied without the user explicitly typing "approve".

Design:
  - Uses `rich` for formatted terminal output.
  - Accepts "approve" / "reject" / "a" / "r".
  - On "reject", archives with a reason.
  - Respects NON_INTERACTIVE mode for automated testing.

State in:  current_job, matched_projects, match_score, todo_list
State out: human_decision ("approve" | "reject"), routing ("approve" | "reject")
"""

import os

from loguru import logger
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

from src.agent.state import AgentState
from src.agent.tools.todo_tool import format_list


console = Console()

# Set NON_INTERACTIVE=1 in env to auto-approve (useful for CI / integration tests)
_NON_INTERACTIVE = os.environ.get("NON_INTERACTIVE", "0") == "1"


def review_node(state: AgentState) -> AgentState:
    """
    Present a job summary and wait for human approval.

    State in:  current_job, matched_projects, match_score, todo_list
    State out: human_decision, routing
    """
    record = state.get("current_job") or {}
    scout = record.get("scout") or {}
    intel = record.get("intelligence") or {}
    matched = state.get("matched_projects") or []
    score = state.get("match_score", 0.0)
    todo = state.get("todo_list") or []

    # -------------------------------------------------------------------------
    # Build display data
    # -------------------------------------------------------------------------
    title = record.get("raw_title") or record.get("title") or "Unknown Role"
    company = scout.get("company_name") or record.get("author_name") or "Unknown Company"
    city = scout.get("city") or ""
    is_remote = scout.get("is_remote")
    location = city
    if is_remote is True:
        location = f"{city} (Remote)" if city else "Remote"
    elif is_remote is False:
        location = f"{city} (On-site)" if city else "On-site"

    salary_min = scout.get("salary_min")
    salary_max = scout.get("salary_max")
    currency = scout.get("currency") or ""
    salary = (
        f"{salary_min:,.0f}–{salary_max:,.0f} {currency}"
        if salary_min and salary_max
        else (f"{salary_min:,.0f}+ {currency}" if salary_min else "Not specified")
    )

    seniority = intel.get("seniority") or scout.get("seniority") or "unknown"
    job_type = intel.get("job_type") or scout.get("job_type") or "unknown"
    contact = scout.get("contact_info") or record.get("primary_contact") or "—"
    source_url = record.get("job_url") or record.get("source_url") or "—"

    # -------------------------------------------------------------------------
    # Score bar
    # -------------------------------------------------------------------------
    bar_len = 20
    filled = int(score * bar_len)
    bar = "█" * filled + "░" * (bar_len - filled)
    score_pct = f"{score:.0%}"
    score_label = (
        "[bold green]Excellent[/]" if score >= 0.7
        else "[bold yellow]Good[/]" if score >= 0.4
        else "[bold red]Low[/]"
    )

    # -------------------------------------------------------------------------
    # Rich output
    # -------------------------------------------------------------------------
    console.print()
    console.rule("[bold cyan]🤖 DeepAgent — Job Review[/]")

    # Job overview panel
    console.print(Panel(
        f"[bold white]{title}[/] @ [cyan]{company}[/]\n"
        f"📍 {location}   💼 {seniority}   🕐 {job_type}\n"
        f"💰 {salary}\n"
        f"📧 {contact}\n"
        f"🔗 {source_url[:80]}{'...' if len(source_url) > 80 else ''}",
        title="[bold]📋 Job Details[/]",
        border_style="blue",
        expand=False,
    ))

    # Match score panel
    console.print(Panel(
        f"[cyan]{bar}[/] {score_pct}  {score_label}",
        title="[bold]📊 Match Score[/]",
        border_style="green" if score >= 0.5 else "red",
        expand=False,
    ))

    # Matched projects table
    if matched:
        table = Table(title="🔗 Matched Projects", box=box.ROUNDED, show_header=True)
        table.add_column("#", style="dim", width=3)
        table.add_column("Project", style="bold white")
        table.add_column("Score", justify="right", style="yellow")
        table.add_column("Tech Stack", style="cyan")
        for i, proj in enumerate(matched[:3], 1):
            table.add_row(
                str(i),
                proj.get("name", "—")[:40],
                f"{proj.get('_match_score', 0):.0%}",
                ", ".join(proj.get("tech_stack") or [])[:50],
            )
        console.print(table)
    else:
        console.print("[dim]  No projects matched.[/]")

    # Todo list
    if todo:
        console.print(Panel(
            format_list(todo),
            title="[bold]🗒️  Action Plan[/]",
            border_style="dim",
            expand=False,
        ))

    # -------------------------------------------------------------------------
    # Human decision
    # -------------------------------------------------------------------------
    if _NON_INTERACTIVE:
        decision = "approve"
        logger.info("[review] NON_INTERACTIVE=1 — auto-approving.")
    else:
        console.print()
        raw = console.input(
            "[bold green]Decision — [approve/a] or [reject/r]:[/] "
        ).strip().lower()
        decision = "approve" if raw in ("approve", "a", "yes", "y") else "reject"

    routing = decision  # "approve" or "reject"
    logger.info(f"[review] Human decision: {decision.upper()}")

    return {
        **state,
        "human_decision": decision,
        "routing": routing,
    }


def route_after_review(state: AgentState) -> str:
    """Conditional edge function: returns 'approve' or 'reject'."""
    return state.get("routing", "reject")
