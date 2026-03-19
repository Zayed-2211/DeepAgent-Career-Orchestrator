"""
Test script for Phase 7 - CV and cover letter generation.

Tests the LaTeX engine, CV tailor, and cover letter generator independently.
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
from src.generators.cv_tailor import CVTailor
from src.generators.cover_letter_gen import CoverLetterGenerator
from src.generators.latex_engine import LaTeXEngine


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


def load_sample_projects() -> list[dict]:
    """Load sample projects for testing."""
    projects_file = DATA_DIR / "profile" / "my_projects.json"
    
    if not projects_file.exists():
        logger.warning("No projects file found, using mock data")
        return [
            {
                "name": "AI Chatbot Platform",
                "description": "Built a scalable chatbot platform using LangChain and FastAPI",
                "tech_stack": ["Python", "LangChain", "FastAPI", "PostgreSQL"],
                "github_url": "https://github.com/user/chatbot",
                "highlights": ["Handled 10k+ daily users", "99.9% uptime"],
            },
            {
                "name": "Data Pipeline System",
                "description": "Developed ETL pipeline for processing large datasets",
                "tech_stack": ["Python", "Apache Airflow", "Pandas", "Docker"],
                "github_url": "https://github.com/user/pipeline",
                "highlights": ["Processed 1TB+ data daily", "Reduced processing time by 60%"],
            },
        ]
    
    with open(projects_file, encoding="utf-8") as f:
        projects = json.load(f)
    
    logger.info(f"Loaded {len(projects)} projects")
    return projects[:3]


def get_user_profile() -> dict:
    """Get user profile for testing."""
    return {
        "name": "Test Candidate",
        "email": "test@example.com",
        "phone": "+20 123 456 7890",
        "location": "Cairo, Egypt",
        "linkedin_url": "https://linkedin.com/in/testuser",
        "github_url": "https://github.com/testuser",
        "experience": [
            {
                "company": "Tech Company",
                "position": "Senior Software Engineer",
                "period": "Jan 2022 - Present",
                "description": "Led development of AI-powered applications",
            },
            {
                "company": "Startup Inc",
                "position": "Software Engineer",
                "period": "Jun 2020 - Dec 2021",
                "description": "Developed backend services and APIs",
            },
        ],
        "education": [
            {
                "degree": "Bachelor of Computer Science",
                "institution": "Cairo University",
                "period": "2016 - 2020",
                "gpa": "3.8/4.0",
                "honors": "Graduated with Honors",
            }
        ],
        "skills": ["Python", "FastAPI", "PostgreSQL", "Docker", "LangChain"],
        "certifications": ["AWS Certified Developer"],
    }


def test_latex_engine():
    """Test LaTeX engine with sample template."""
    console.print("\n[bold cyan]Testing LaTeX Engine...[/bold cyan]")
    
    engine = LaTeXEngine()
    
    test_context = {
        "name": "Test User",
        "email": "test@example.com",
        "phone": "+20 123 456 7890",
        "location": "Cairo, Egypt",
        "linkedin_url": "https://linkedin.com/in/test",
        "github_url": "https://github.com/test",
        "professional_summary": "Experienced software engineer with 5+ years in AI and backend development.",
        "technical_skills": ["Python", "FastAPI", "PostgreSQL", "Docker"],
        "soft_skills": ["Leadership", "Communication", "Problem Solving"],
        "experience": [
            {
                "company": "Tech Co",
                "position": "Senior Engineer",
                "period": "2022 - Present",
                "bullets": ["Led team of 5 engineers", "Improved performance by 40%"],
            }
        ],
        "projects": [
            {
                "name": "AI Platform",
                "tech_stack": ["Python", "LangChain"],
                "bullets": ["Built scalable platform", "Served 10k+ users"],
                "github_url": "https://github.com/test/ai-platform",
            }
        ],
        "education": [
            {
                "degree": "BSc Computer Science",
                "institution": "Cairo University",
                "period": "2016-2020",
                "gpa": "3.8/4.0",
            }
        ],
        "certifications": ["AWS Certified Developer"],
    }
    
    output_dir = DATA_DIR / "outputs" / "test_generator"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        result = engine.render_and_compile(
            template_name="cv_template.tex",
            context=test_context,
            output_dir=output_dir,
            base_name="test_cv",
        )
        
        if result.get("tex"):
            console.print(f"✅ LaTeX file created: {result['tex']}")
        
        if result.get("pdf"):
            console.print(f"✅ PDF compiled: {result['pdf']}")
        else:
            console.print("⚠️  PDF compilation skipped or failed (check pdflatex installation)")
        
        return True
    
    except Exception as exc:
        console.print(f"❌ LaTeX engine test failed: {exc}")
        return False


def test_cv_tailor():
    """Test CV tailor with sample job."""
    console.print("\n[bold cyan]Testing CV Tailor...[/bold cyan]")
    
    job = load_sample_job()
    projects = load_sample_projects()
    profile = get_user_profile()
    
    tailor = CVTailor()
    
    try:
        tailored_cv = tailor.tailor_cv(job, projects, profile)
        
        console.print(Panel(
            f"[bold]Professional Summary:[/bold]\n{tailored_cv.professional_summary}\n\n"
            f"[bold]Technical Skills:[/bold] {', '.join(tailored_cv.technical_skills[:10])}\n\n"
            f"[bold]Projects:[/bold] {len(tailored_cv.projects)}\n"
            f"[bold]Experience:[/bold] {len(tailored_cv.experience)}",
            title="Tailored CV Preview",
            border_style="green",
        ))
        
        return True
    
    except Exception as exc:
        console.print(f"❌ CV tailor test failed: {exc}")
        logger.exception(exc)
        return False


def test_cover_letter_generator():
    """Test cover letter generator with sample job."""
    console.print("\n[bold cyan]Testing Cover Letter Generator...[/bold cyan]")
    
    job = load_sample_job()
    projects = load_sample_projects()
    profile = get_user_profile()
    
    generator = CoverLetterGenerator()
    
    try:
        cover_letter = generator.generate_cover_letter(job, projects, profile)
        
        console.print(Panel(
            f"[bold]Opening:[/bold]\n{cover_letter.opening[:200]}...\n\n"
            f"[bold]Tone:[/bold] {cover_letter.tone}",
            title="Cover Letter Preview",
            border_style="green",
        ))
        
        return True
    
    except Exception as exc:
        console.print(f"❌ Cover letter generator test failed: {exc}")
        logger.exception(exc)
        return False


def test_full_generation():
    """Test full CV and cover letter generation pipeline."""
    console.print("\n[bold cyan]Testing Full Generation Pipeline...[/bold cyan]")
    
    job = load_sample_job()
    projects = load_sample_projects()
    profile = get_user_profile()
    
    output_dir = DATA_DIR / "outputs" / "test_full_generation"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        tailor = CVTailor()
        cover_letter_gen = CoverLetterGenerator()
        latex_engine = LaTeXEngine()
        
        console.print("1. Tailoring CV...")
        tailored_cv = tailor.tailor_cv(job, projects, profile)
        
        cv_context = {
            "name": profile["name"],
            "email": profile["email"],
            "phone": profile["phone"],
            "location": profile["location"],
            "linkedin_url": profile.get("linkedin_url", ""),
            "github_url": profile.get("github_url", ""),
            "professional_summary": tailored_cv.professional_summary,
            "technical_skills": tailored_cv.technical_skills,
            "soft_skills": tailored_cv.soft_skills,
            "experience": [
                {
                    "company": exp.company,
                    "position": exp.position,
                    "period": exp.period,
                    "bullets": exp.bullets,
                }
                for exp in tailored_cv.experience
            ],
            "projects": [
                {
                    "name": proj.name,
                    "tech_stack": proj.tech_stack,
                    "bullets": proj.bullets,
                    "github_url": proj.github_url,
                }
                for proj in tailored_cv.projects
            ],
            "education": profile.get("education", []),
            "certifications": profile.get("certifications", []),
        }
        
        console.print("2. Rendering CV...")
        cv_files = latex_engine.render_and_compile(
            template_name="cv_template.tex",
            context=cv_context,
            output_dir=output_dir,
            base_name="tailored_cv",
        )
        
        console.print("3. Generating cover letter...")
        tailored_cover_letter = cover_letter_gen.generate_cover_letter(
            job, projects, profile
        )
        
        from datetime import date as dt
        
        cover_letter_context = {
            "name": profile["name"],
            "email": profile["email"],
            "phone": profile["phone"],
            "location": profile["location"],
            "date": dt.today().strftime("%B %d, %Y"),
            "recipient_name": "",
            "company_name": job.get("company", ""),
            "company_address": "",
            "opening": tailored_cover_letter.opening,
            "body_paragraph_1": tailored_cover_letter.body_paragraph_1,
            "body_paragraph_2": tailored_cover_letter.body_paragraph_2,
            "closing": tailored_cover_letter.closing,
        }
        
        console.print("4. Rendering cover letter...")
        cover_letter_files = latex_engine.render_and_compile(
            template_name="cover_letter_template.tex",
            context=cover_letter_context,
            output_dir=output_dir,
            base_name="cover_letter",
        )
        
        console.print("\n[bold green]✅ Full generation pipeline complete![/bold green]")
        console.print(f"\nOutput directory: {output_dir}")
        
        if cv_files.get("pdf"):
            console.print(f"  CV PDF: {cv_files['pdf']}")
        if cover_letter_files.get("pdf"):
            console.print(f"  Cover Letter PDF: {cover_letter_files['pdf']}")
        
        return True
    
    except Exception as exc:
        console.print(f"❌ Full generation test failed: {exc}")
        logger.exception(exc)
        return False


def main():
    """Run all Phase 7 tests."""
    console.print(Panel(
        "[bold]Phase 7 - CV & Cover Letter Generation Tests[/bold]\n\n"
        "This script tests the LaTeX engine, CV tailor, and cover letter generator.",
        title="Test Suite",
        border_style="cyan",
    ))
    
    results = {
        "LaTeX Engine": test_latex_engine(),
        "CV Tailor": test_cv_tailor(),
        "Cover Letter Generator": test_cover_letter_generator(),
        "Full Pipeline": test_full_generation(),
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
        console.print("\n[bold red]⚠️  Some tests failed. Check logs above.[/bold red]")
        return 1


if __name__ == "__main__":
    sys.exit(main())
