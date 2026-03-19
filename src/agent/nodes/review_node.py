"""
Review Node - Phase 6.

Renders a concise rich summary for visibility, then auto-approves so
pipeline runs stay unattended.

State in:  current_job, matched_projects, match_score, todo_list
State out: human_decision ("approve"), routing ("approve")
"""

from loguru import logger
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.agent.state import AgentState
from src.agent.tools.todo_tool import format_list


console = Console()


def review_node(state: AgentState) -> AgentState:
    """
    Render summary and auto-approve.

    State in:  current_job, matched_projects, match_score, todo_list
    State out: human_decision, routing
    """
    record = state.get("current_job") or {}
    scout = record.get("scout") or {}
    intel = record.get("intelligence") or {}
    matched = state.get("matched_projects") or []
    score = state.get("match_score", 0.0)
    todo = state.get("todo_list") or []

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
        f"{salary_min:,.0f}-{salary_max:,.0f} {currency}"
        if salary_min and salary_max
        else (f"{salary_min:,.0f}+ {currency}" if salary_min else "Not specified")
    )

    seniority = intel.get("seniority") or scout.get("seniority") or "unknown"
    job_type = intel.get("job_type") or scout.get("job_type") or "unknown"
    contact = scout.get("contact_info") or record.get("primary_contact") or "-"
    source_url = record.get("job_url") or record.get("source_url") or "-"

    bar_len = 20
    filled = int(score * bar_len)
    bar = "#" * filled + "." * (bar_len - filled)
    score_pct = f"{score:.0%}"
    score_label = (
        "[bold green]Excellent[/]"
        if score >= 0.7
        else "[bold yellow]Good[/]"
        if score >= 0.4
        else "[bold red]Low[/]"
    )

    console.print()
    console.rule("[bold cyan]DeepAgent - Job Review[/]")

    console.print(
        Panel(
            f"[bold white]{title}[/] @ [cyan]{company}[/]\n"
            f"Location: {location}   Seniority: {seniority}   Type: {job_type}\n"
            f"Salary: {salary}\n"
            f"Contact: {contact}\n"
            f"URL: {source_url[:80]}{'...' if len(source_url) > 80 else ''}",
            title="[bold]Job Details[/]",
            border_style="blue",
            expand=False,
        )
    )

    console.print(
        Panel(
            f"[cyan]{bar}[/] {score_pct}  {score_label}",
            title="[bold]Match Score[/]",
            border_style="green" if score >= 0.5 else "red",
            expand=False,
        )
    )

    if matched:
        table = Table(title="Matched Projects", box=box.ROUNDED, show_header=True)
        table.add_column("#", style="dim", width=3)
        table.add_column("Project", style="bold white")
        table.add_column("Score", justify="right", style="yellow")
        table.add_column("Tech Stack", style="cyan")
        for i, proj in enumerate(matched[:3], 1):
            table.add_row(
                str(i),
                proj.get("name", "-")[:40],
                f"{proj.get('_match_score', 0):.0%}",
                ", ".join(proj.get("tech_stack") or [])[:50],
            )
        console.print(table)
    else:
        console.print("[dim]  No projects matched.[/]")

    if todo:
        console.print(
            Panel(
                format_list(todo),
                title="[bold]Action Plan[/]",
                border_style="dim",
                expand=False,
            )
        )

    logger.info("[review] Unattended mode: auto-approving.")

    return {
        **state,
        "human_decision": "approve",
        "routing": "approve",
    }


def route_after_review(state: AgentState) -> str:
    """Conditional edge function: returns approve by default."""
    return state.get("routing", "approve")
