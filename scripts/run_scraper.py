"""
CLI entry point for running scrapers.

Usage:
    python scripts/run_scraper.py                          # Run all enabled platforms
    python scripts/run_scraper.py --platform linkedin      # Run only LinkedIn
    python scripts/run_scraper.py --platform linkedin --query "AI Engineer"
    python scripts/run_scraper.py --no-filters             # Skip post-scrape filtering
"""

import sys
import argparse
from pathlib import Path

# Add project root to path so imports work
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from loguru import logger
from rich.console import Console
from rich.table import Table

from src.scrapers.scraper_manager import ScraperManager

console = Console()


def main():
    parser = argparse.ArgumentParser(description="Run job scrapers")
    parser.add_argument(
        "--platform",
        type=str,
        default=None,
        help="Platform to scrape (linkedin, glassdoor, indeed, google). Default: all enabled.",
    )
    parser.add_argument(
        "--query",
        type=str,
        default=None,
        help="Override search query (runs only this one query instead of the config file).",
    )
    parser.add_argument(
        "--no-filters",
        action="store_true",
        help="Skip post-scrape filtering.",
    )
    args = parser.parse_args()

    # Configure logging
    logger.remove()
    logger.add(sys.stderr, level="INFO", format="<green>{time:HH:mm:ss}</green> | <level>{message}</level>")

    console.print("\n[bold cyan]🤖 DeepAgent Career Orchestrator — Scraper[/bold cyan]\n")

    manager = ScraperManager()

    # Override queries if --query is passed
    if args.query:
        manager.queries_config["search_queries"] = [args.query]
        console.print(f"[yellow]Using override query:[/yellow] {args.query}\n")

    # Run
    if args.platform:
        console.print(f"[cyan]Running platform:[/cyan] {args.platform}\n")
        results = manager.run_platform(args.platform)
    else:
        console.print("[cyan]Running all enabled platforms...[/cyan]\n")
        results = manager.run_all()

    # Print summary table
    if results:
        _print_results_table(results)
    else:
        console.print("[yellow]No results found.[/yellow]")

    console.print(f"\n[bold green]✓ Done — {len(results)} jobs scraped[/bold green]\n")


def _print_results_table(results: list[dict]):
    """Print a summary table of scraped results."""
    table = Table(title=f"Scraped Jobs ({len(results)} total)", show_lines=False)
    table.add_column("#", style="dim", width=4)
    table.add_column("Title", style="bold", max_width=40)
    table.add_column("Company", max_width=25)
    table.add_column("Location", max_width=20)
    table.add_column("Type", max_width=10)
    table.add_column("Remote", max_width=6)
    table.add_column("Posted", max_width=12)

    for i, job in enumerate(results[:50], 1):  # Show max 50
        location = job.get("city") or job.get("state") or job.get("country") or "—"
        table.add_row(
            str(i),
            job.get("title", "—"),
            job.get("company", "—"),
            location,
            job.get("job_type", "—"),
            "✓" if job.get("is_remote") else "—",
            str(job.get("date_posted", "—"))[:10],
        )

    console.print(table)

    if len(results) > 50:
        console.print(f"[dim]  ... and {len(results) - 50} more (check the JSON output)[/dim]")


if __name__ == "__main__":
    main()
