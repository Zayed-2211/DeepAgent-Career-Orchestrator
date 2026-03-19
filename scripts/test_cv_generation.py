"""
Test script for CV and cover letter generation.

This script loads already-scraped jobs and generates tailored CVs and cover letters
for a specified number of jobs. Useful for testing the generation pipeline without
re-scraping.

Usage:
    python scripts/test_cv_generation.py --jobs 2
    python scripts/test_cv_generation.py --jobs 2 --skip-delay
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from loguru import logger
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import DATA_DIR, CONFIG_DIR
from src.generators.cv_tailor import CVTailor
from src.generators.cover_letter_gen import CoverLetterGenerator
from src.generators.latex_engine import LaTeXEngine

console = Console()


def load_latest_parsed_jobs() -> list[dict]:
    """Load the most recent parsed jobs from intelligence directory."""
    intelligence_dir = DATA_DIR / "intelligence"
    
    if not intelligence_dir.exists():
        console.print("[red]✗ No intelligence directory found. Run the pipeline first.[/red]")
        return []
    
    # Find the most recent date directory
    date_dirs = [d for d in intelligence_dir.iterdir() if d.is_dir()]
    if not date_dirs:
        console.print("[red]✗ No intelligence data found. Run the pipeline first.[/red]")
        return []
    
    latest_dir = max(date_dirs, key=lambda d: d.name)
    parsed_jobs_file = latest_dir / "parsed_jobs.json"
    
    if not parsed_jobs_file.exists():
        console.print(f"[red]✗ No parsed_jobs.json found in {latest_dir}[/red]")
        return []
    
    with open(parsed_jobs_file, encoding="utf-8") as f:
        data = json.load(f)
    
    jobs = data.get("jobs", [])
    console.print(f"[green]✓ Loaded {len(jobs)} jobs from {parsed_jobs_file}[/green]")
    return jobs


def load_user_profile() -> dict:
    """Load user profile data."""
    profile_dir = DATA_DIR / "profile"
    
    # Load projects
    projects_file = profile_dir / "my_projects.json"
    projects = []
    if projects_file.exists():
        with open(projects_file, encoding="utf-8") as f:
            projects = json.load(f)
    
    # Load CV (just check it exists)
    cv_file = profile_dir / "my_cv.tex"
    if not cv_file.exists():
        console.print("[yellow]⚠ Warning: my_cv.tex not found[/yellow]")
    
    return {
        "projects": projects,
        "cv_path": str(cv_file) if cv_file.exists() else None,
    }


def display_job_summary(jobs: list[dict], num_jobs: int):
    """Display a summary table of jobs to be processed."""
    table = Table(title=f"Jobs to Process (First {num_jobs})", show_header=True, header_style="bold magenta")
    table.add_column("#", style="dim", width=3)
    table.add_column("Job Title", style="cyan", width=40)
    table.add_column("Company", style="green", width=25)
    table.add_column("Job UID", style="yellow", width=30)
    
    for i, job in enumerate(jobs[:num_jobs], 1):
        table.add_row(
            str(i),
            job.get("title", "Unknown")[:40],
            job.get("company", "Unknown")[:25],
            job.get("job_uid", "N/A")[:30]
        )
    
    console.print(table)


def generate_for_job(
    job: dict,
    job_num: int,
    total_jobs: int,
    user_profile: dict,
    skip_delay: bool = False
) -> dict:
    """Generate CV and cover letter for a single job."""
    job_title = job.get("title", "Unknown")
    company = job.get("company", "Unknown")
    job_uid = job.get("job_uid", "unknown")
    
    console.print(f"\n[bold cyan]{'='*80}[/bold cyan]")
    console.print(f"[bold]Processing Job {job_num}/{total_jobs}: {job_title} at {company}[/bold]")
    console.print(f"[dim]Job UID: {job_uid}[/dim]")
    console.print(f"[bold cyan]{'='*80}[/bold cyan]\n")
    
    # Create output directory
    safe_job_uid = job_uid.replace(":", "_").replace("/", "_")[:80]
    output_dir = DATA_DIR / "outputs" / safe_job_uid
    output_dir.mkdir(parents=True, exist_ok=True)
    
    results = {
        "job_uid": job_uid,
        "job_title": job_title,
        "company": company,
        "output_dir": str(output_dir),
        "cv_generated": False,
        "cover_letter_generated": False,
        "errors": []
    }
    
    # Get matched projects (top 3 from job's matched_projects or use all)
    matched_projects = job.get("matched_projects", user_profile.get("projects", []))[:3]
    
    try:
        # Initialize generators
        cv_tailor = CVTailor()
        cover_letter_gen = CoverLetterGenerator()
        latex_engine = LaTeXEngine()
        
        # Generate CV
        console.print("[bold blue]→ Generating tailored CV...[/bold blue]")
        tailored_cv = cv_tailor.tailor_cv(job, matched_projects, user_profile)
        
        # Build CV context
        cv_context = {
            "name": "Your Name",  # TODO: Extract from profile
            "email": "your.email@example.com",
            "phone": "+20 XXX XXX XXXX",
            "linkedin": "linkedin.com/in/yourprofile",
            "github": "github.com/yourusername",
            "summary": tailored_cv.professional_summary,
            "experience": [
                {
                    "company": exp.company,
                    "position": exp.position,
                    "period": exp.period,
                    "bullets": exp.bullets
                }
                for exp in tailored_cv.experience
            ],
            "projects": [
                {
                    "name": proj.name,
                    "tech_stack": ", ".join(proj.tech_stack),
                    "bullets": proj.bullets,
                    "github_url": proj.github_url or ""
                }
                for proj in tailored_cv.projects
            ],
            "technical_skills": ", ".join(tailored_cv.technical_skills),
            "soft_skills": ", ".join(tailored_cv.soft_skills),
        }
        
        # Compile CV
        cv_files = latex_engine.render_and_compile(
            template_name="cv_template.tex",
            context=cv_context,
            output_dir=output_dir,
            base_name="tailored_cv"
        )
        
        if cv_files.get("pdf"):
            console.print(f"[green]✓ CV generated: {cv_files['pdf']}[/green]")
            results["cv_generated"] = True
            results["cv_pdf"] = str(cv_files["pdf"])
            results["cv_tex"] = str(cv_files.get("tex", ""))
        
        # Generate cover letter
        console.print("[bold blue]→ Generating cover letter...[/bold blue]")
        company_research = job.get("company_research")
        tailored_cover_letter = cover_letter_gen.generate_cover_letter(
            job, matched_projects, user_profile, company_research
        )
        
        # Build cover letter context
        cover_letter_context = {
            "name": "Your Name",
            "address": "Your Address",
            "city": "Your City",
            "email": "your.email@example.com",
            "phone": "+20 XXX XXX XXXX",
            "date": datetime.now().strftime("%B %d, %Y"),
            "company_name": company,
            "hiring_manager": "Hiring Manager",
            "company_address": "",
            "position": job_title,
            "opening": tailored_cover_letter.opening,
            "body_paragraph_1": tailored_cover_letter.body_paragraph_1,
            "body_paragraph_2": tailored_cover_letter.body_paragraph_2,
            "closing": tailored_cover_letter.closing,
        }
        
        # Compile cover letter
        cl_files = latex_engine.render_and_compile(
            template_name="cover_letter_template.tex",
            context=cover_letter_context,
            output_dir=output_dir,
            base_name="cover_letter"
        )
        
        if cl_files.get("pdf"):
            console.print(f"[green]✓ Cover letter generated: {cl_files['pdf']}[/green]")
            results["cover_letter_generated"] = True
            results["cover_letter_pdf"] = str(cl_files["pdf"])
            results["cover_letter_tex"] = str(cl_files.get("tex", ""))
        
    except Exception as e:
        error_msg = f"Generation failed: {str(e)}"
        console.print(f"[red]✗ {error_msg}[/red]")
        results["errors"].append(error_msg)
        logger.exception(f"Error generating documents for {job_title}")
    
    return results


def display_final_summary(all_results: list[dict]):
    """Display final summary of all generations."""
    console.print("\n" + "="*80)
    console.print("[bold green]Final Summary[/bold green]")
    console.print("="*80 + "\n")
    
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("#", style="dim", width=3)
    table.add_column("Job Title", style="cyan", width=30)
    table.add_column("CV", justify="center", width=8)
    table.add_column("Cover Letter", justify="center", width=15)
    table.add_column("Output Dir", style="yellow", width=40)
    
    for i, result in enumerate(all_results, 1):
        cv_status = "[green]✓[/green]" if result["cv_generated"] else "[red]✗[/red]"
        cl_status = "[green]✓[/green]" if result["cover_letter_generated"] else "[red]✗[/red]"
        
        table.add_row(
            str(i),
            result["job_title"][:30],
            cv_status,
            cl_status,
            result["output_dir"][-40:]
        )
    
    console.print(table)
    
    # Statistics
    total = len(all_results)
    cv_success = sum(1 for r in all_results if r["cv_generated"])
    cl_success = sum(1 for r in all_results if r["cover_letter_generated"])
    
    stats_panel = Panel(
        f"[bold]Total Jobs:[/bold] {total}\n"
        f"[bold]CVs Generated:[/bold] {cv_success}/{total} ({cv_success/total*100:.0f}%)\n"
        f"[bold]Cover Letters Generated:[/bold] {cl_success}/{total} ({cl_success/total*100:.0f}%)",
        title="Statistics",
        border_style="green"
    )
    console.print("\n", stats_panel)


def main():
    parser = argparse.ArgumentParser(description="Test CV and cover letter generation")
    parser.add_argument("--jobs", type=int, default=2, help="Number of jobs to process (default: 2)")
    parser.add_argument("--skip-delay", action="store_true", help="Skip rate limiting delays")
    args = parser.parse_args()
    
    console.print(Panel.fit(
        "[bold cyan]CV & Cover Letter Generation Test[/bold cyan]\n"
        f"Processing {args.jobs} job(s) from scraped data",
        border_style="cyan"
    ))
    
    # Load data
    jobs = load_latest_parsed_jobs()
    if not jobs:
        console.print("[red]No jobs found. Run the pipeline first with: python scripts/run_agent.py --pipeline --dev 3[/red]")
        return 1
    
    user_profile = load_user_profile()
    
    # Limit to requested number
    num_jobs = min(args.jobs, len(jobs))
    jobs_to_process = jobs[:num_jobs]
    
    # Display summary
    display_job_summary(jobs, num_jobs)
    
    # Optionally modify config to skip delays
    if args.skip_delay:
        console.print("\n[yellow]⚠ Skipping rate limiting delays (--skip-delay flag)[/yellow]")
        config_path = CONFIG_DIR / "generators.json"
        if config_path.exists():
            with open(config_path, encoding="utf-8") as f:
                config = json.load(f)
            config["rate_limiting"]["enabled"] = False
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2)
    
    # Process jobs
    all_results = []
    for i, job in enumerate(jobs_to_process, 1):
        result = generate_for_job(job, i, num_jobs, user_profile, args.skip_delay)
        all_results.append(result)
    
    # Restore config if modified
    if args.skip_delay:
        config["rate_limiting"]["enabled"] = True
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
    
    # Display final summary
    display_final_summary(all_results)
    
    console.print("\n[bold green]✓ Test complete![/bold green]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
