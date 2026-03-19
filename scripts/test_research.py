"""
Test script for Phase 8 - Company research.

Tests the Tavily web searcher, Glassdoor researcher, and prep pack builder.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from loguru import logger
from rich.console import Console
from rich.panel import Panel

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import DATA_DIR
from src.research.glassdoor_researcher import GlassdoorResearcher
from src.research.prep_pack_builder import PrepPackBuilder
from src.research.web_searcher import WebSearcher


console = Console()


def load_sample_job() -> dict:
    """Load a sample parsed job for testing."""
    intelligence_dir = DATA_DIR / "intelligence"
    
    for date_dir in sorted(intelligence_dir.glob("*"), reverse=True):
        parsed_jobs_file = date_dir / "parsed_jobs.json"
        if parsed_jobs_file.exists():
            with open(parsed_jobs_file, encoding="utf-8") as f:
                jobs = json.load(f)
            
            if jobs:
                logger.info(f"Loaded sample job from {parsed_jobs_file}")
                return jobs[0]
    
    logger.error("No parsed jobs found for testing")
    sys.exit(1)


def test_web_searcher():
    """Test Tavily web searcher."""
    console.print("\n[bold cyan]Testing Web Searcher (Tavily)...[/bold cyan]")
    
    searcher = WebSearcher()
    
    if not searcher.is_available():
        console.print("⚠️  Tavily API not available (TAVILY_API_KEY not set)")
        console.print("   Set TAVILY_API_KEY in .env to enable research features")
        return False
    
    try:
        results = searcher.search("Python programming language", max_results=3)
        
        if results:
            console.print(f"✅ Found {len(results)} search results")
            
            for i, result in enumerate(results[:2], 1):
                console.print(f"\n  Result {i}:")
                console.print(f"    Title: {result.get('title', 'N/A')[:60]}")
                console.print(f"    URL: {result.get('url', 'N/A')[:60]}")
        else:
            console.print("⚠️  No results returned")
        
        return True
    
    except Exception as exc:
        console.print(f"❌ Web searcher test failed: {exc}")
        logger.exception(exc)
        return False


def test_glassdoor_researcher():
    """Test Glassdoor researcher."""
    console.print("\n[bold cyan]Testing Glassdoor Researcher...[/bold cyan]")
    
    job = load_sample_job()
    company_name = job.get("company", "Google")
    
    console.print(f"Researching company: {company_name}")
    
    researcher = GlassdoorResearcher()
    
    try:
        insights = researcher.research_company(company_name)
        
        if insights:
            console.print(Panel(
                f"[bold]Overall Rating:[/bold] {insights.overall_rating or 'N/A'}/5.0\n"
                f"[bold]Sentiment:[/bold] {insights.sentiment}\n\n"
                f"[bold]Top Pros:[/bold]\n" + "\n".join(f"  • {pro}" for pro in insights.pros[:3]) + "\n\n"
                f"[bold]Top Cons:[/bold]\n" + "\n".join(f"  • {con}" for con in insights.cons[:3]) + "\n\n"
                f"[bold]Red Flags:[/bold] {len(insights.red_flags)}",
                title=f"Glassdoor Insights - {company_name}",
                border_style="green",
            ))
            return True
        else:
            console.print("⚠️  No insights returned (company may not have reviews)")
            return False
    
    except Exception as exc:
        console.print(f"❌ Glassdoor researcher test failed: {exc}")
        logger.exception(exc)
        return False


def test_prep_pack_builder():
    """Test prep pack builder."""
    console.print("\n[bold cyan]Testing Prep Pack Builder...[/bold cyan]")
    
    job = load_sample_job()
    
    mock_glassdoor_insights = {
        "overall_rating": 4.2,
        "pros": [
            "Great work-life balance",
            "Competitive salary and benefits",
            "Innovative projects",
        ],
        "cons": [
            "Limited growth opportunities",
            "Bureaucratic processes",
        ],
        "interview_questions": [
            "Tell me about yourself",
            "Why do you want to work here?",
            "Describe a challenging project",
        ],
        "red_flags": [],
        "sentiment": "positive",
        "summary": "Overall a good company with strong benefits and interesting work.",
    }
    
    builder = PrepPackBuilder()
    
    output_dir = DATA_DIR / "outputs" / "test_research"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        prep_pack_path = builder.build_prep_pack(
            job=job,
            glassdoor_insights=mock_glassdoor_insights,
            linkedin_data=None,
            community_sentiment=None,
            output_path=output_dir / "test_prep_pack.md",
        )
        
        if prep_pack_path and prep_pack_path.exists():
            console.print(f"✅ Prep pack created: {prep_pack_path}")
            
            with open(prep_pack_path, encoding="utf-8") as f:
                content = f.read()
            
            console.print(f"\n[dim]Preview (first 500 chars):[/dim]")
            console.print(Panel(content[:500] + "...", border_style="dim"))
            
            return True
        else:
            console.print("❌ Prep pack not created")
            return False
    
    except Exception as exc:
        console.print(f"❌ Prep pack builder test failed: {exc}")
        logger.exception(exc)
        return False


def test_full_research_pipeline():
    """Test full research pipeline."""
    console.print("\n[bold cyan]Testing Full Research Pipeline...[/bold cyan]")
    
    job = load_sample_job()
    company_name = job.get("company", "Google")
    
    console.print(f"Researching: {company_name}")
    
    try:
        searcher = WebSearcher()
        
        if not searcher.is_available():
            console.print("⚠️  Skipping (Tavily API not available)")
            return False
        
        console.print("1. Searching Glassdoor...")
        researcher = GlassdoorResearcher()
        glassdoor_insights = researcher.research_company(company_name)
        
        console.print("2. Searching LinkedIn...")
        linkedin_results = searcher.search_company(company_name, "linkedin")
        
        console.print("3. Building prep pack...")
        builder = PrepPackBuilder()
        
        output_dir = DATA_DIR / "outputs" / "test_full_research"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        prep_pack_path = builder.build_prep_pack(
            job=job,
            glassdoor_insights=glassdoor_insights.model_dump() if glassdoor_insights else None,
            linkedin_data={"results": linkedin_results[:3]} if linkedin_results else None,
            community_sentiment=None,
            output_path=output_dir / "prep_pack.md",
        )
        
        console.print("\n[bold green]✅ Full research pipeline complete![/bold green]")
        console.print(f"\nPrep pack: {prep_pack_path}")
        
        return True
    
    except Exception as exc:
        console.print(f"❌ Full research pipeline test failed: {exc}")
        logger.exception(exc)
        return False


def main():
    """Run all Phase 8 tests."""
    console.print(Panel(
        "[bold]Phase 8 - Company Research Tests[/bold]\n\n"
        "This script tests the web searcher, Glassdoor researcher, and prep pack builder.\n\n"
        "[yellow]Note: Requires TAVILY_API_KEY in .env for full testing[/yellow]",
        title="Test Suite",
        border_style="cyan",
    ))
    
    results = {
        "Web Searcher": test_web_searcher(),
        "Glassdoor Researcher": test_glassdoor_researcher(),
        "Prep Pack Builder": test_prep_pack_builder(),
        "Full Pipeline": test_full_research_pipeline(),
    }
    
    console.print("\n" + "=" * 60)
    console.print("[bold]Test Results:[/bold]\n")
    
    for test_name, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        console.print(f"  {test_name}: {status}")
    
    all_passed = all(results.values())
    
    if all_passed:
        console.print("\n[bold green]🎉 All tests passed![/bold green]")
        return 0
    else:
        console.print("\n[bold yellow]⚠️  Some tests failed (may be due to missing API keys)[/bold yellow]")
        return 1


if __name__ == "__main__":
    sys.exit(main())
