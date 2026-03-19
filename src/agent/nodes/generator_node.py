"""
Generator node - Phase 7: LaTeX CV and cover letter generation.
"""

from __future__ import annotations

import json
from pathlib import Path
import time

from loguru import logger
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from config.settings import CONFIG_DIR, DATA_DIR
from src.agent.state import AgentState
from src.generators.cv_tailor import CVTailor
from src.generators.cover_letter_gen import CoverLetterGenerator
from src.generators.latex_engine import LaTeXEngine

console = Console()


def generator_node(state: AgentState) -> dict:
    """
    Generate tailored CV and cover letter for approved jobs.
    
    This node is called after dispatch_node for approved jobs.
    It uses Gemini to tailor content and LaTeX to generate PDFs.
    
    Args:
        state: Current agent state with job and matched projects
    
    Returns:
        Updated state with generated document paths
    """
    config = _load_config()
    
    if not config.get("cv_generation", {}).get("enabled", True):
        logger.info("[generator] CV generation disabled in config")
        return {"routing": "skip"}
    
    current_job = state.get("current_job", {})
    job_uid = state.get("job_uid")
    matched_projects = state.get("matched_projects", [])
    
    job_title = current_job.get("title", "Unknown")
    company = current_job.get("company", "Unknown")
    
    # Rate limiting: Wait before starting CV generation
    rate_limit_config = config.get("rate_limiting", {})
    if rate_limit_config.get("enabled", True):
        delay = rate_limit_config.get("delay_before_cv_generation_seconds", 300)
        logger.info(f"[generator] ⏳ Rate limiting: Waiting {delay}s ({delay//60}m {delay%60}s) before CV generation...")
        logger.info(f"[generator] This prevents hitting Gemini API rate limits")
        time.sleep(delay)
    
    logger.info(f"[generator] 🚀 Starting document generation for '{job_title}' at {company}")
    
    if not current_job or not job_uid:
        logger.warning("[generator] No job data in state")
        return {"routing": "error", "error": "No job data for generation"}
    
    safe_job_uid = job_uid.replace(":", "_")
    output_dir = DATA_DIR / "outputs" / safe_job_uid
    output_dir.mkdir(parents=True, exist_ok=True)
    
    logger.debug(f"[generator] Output directory: {output_dir}")
    
    user_profile = _load_user_profile()
    
    generated_docs = {}
    
    try:
        cv_tailor = CVTailor()
        latex_engine = LaTeXEngine()
        
        logger.info(f"[generator] Tailoring CV for: {current_job.get('title', 'Unknown')}")
        tailored_cv = cv_tailor.tailor_cv(current_job, matched_projects, user_profile)
        
        cv_context = _build_cv_context(tailored_cv, user_profile)
        
        cv_files = latex_engine.render_and_compile(
            template_name="cv_template.tex",
            context=cv_context,
            output_dir=output_dir,
            base_name="tailored_cv",
        )
        
        cv_pdf_path = cv_files.get("pdf")
        cv_tex_path = cv_files.get("tex")
        
        if cv_pdf_path:
            generated_docs["cv_pdf"] = str(cv_pdf_path)
            logger.info(f"[generator] ✓ CV generated successfully")
            logger.debug(f"[generator]   PDF: {cv_pdf_path}")
            logger.debug(f"[generator]   LaTeX: {cv_tex_path}")
        
        if cv_tex_path:
            generated_docs["cv_tex"] = str(cv_tex_path)
        
        if config.get("cover_letter_generation", {}).get("enabled", True):
            cover_letter_gen = CoverLetterGenerator()
            
            company_research = state.get("company_research")
            
            logger.info("[generator] → Generating cover letter...")
            tailored_cover_letter = cover_letter_gen.generate_cover_letter(
                current_job,
                matched_projects,
                user_profile,
                company_research,
            )
            
            cover_letter_context = _build_cover_letter_context(
                tailored_cover_letter,
                user_profile,
                current_job,
            )
            
            cover_letter_files = latex_engine.render_and_compile(
                template_name="cover_letter_template.tex",
                context=cover_letter_context,
                output_dir=output_dir,
                base_name="cover_letter",
            )
            
            cl_pdf_path = cover_letter_files.get("pdf")
            cl_tex_path = cover_letter_files.get("tex")
            
            if cl_pdf_path:
                generated_docs["cover_letter_pdf"] = str(cl_pdf_path)
                logger.info(f"[generator] ✓ Cover letter generated successfully")
                logger.debug(f"[generator]   PDF: {cl_pdf_path}")
                logger.debug(f"[generator]   LaTeX: {cl_tex_path}")
            
            if cl_tex_path:
                generated_docs["cover_letter_tex"] = str(cl_tex_path)
        
        logger.info(f"[generator] ✓ Document generation complete - {len(generated_docs)} files created")
        logger.info(f"[generator] ✅ Files created in: {output_dir}")
        for doc_type, path in generated_docs.items():
            logger.info(f"[generator]    - {doc_type}: {Path(path).name}")
        
        return {
            "generated_docs": {**state.get("generated_docs", {}), **generated_docs},
            "routing": "loop",
        }
    
    except Exception as e:
        logger.error(f"[generator] ✗ Document generation failed for '{job_title}': {e}")
        return {
            "routing": "error",
            "error": f"Document generation failed: {e}",
        }


def _load_config() -> dict:
    """Load generators config."""
    config_path = CONFIG_DIR / "generators.json"
    
    if not config_path.exists():
        return {"cv_generation": {"enabled": True}, "cover_letter_generation": {"enabled": True}}
    
    with open(config_path, encoding="utf-8") as f:
        return json.load(f)


def _load_user_profile() -> dict:
    """Load user profile from my_projects.json and my_cv.tex metadata."""
    profile_path = DATA_DIR / "profile" / "my_projects.json"
    
    if not profile_path.exists():
        logger.warning("[generator] User profile not found, using defaults")
        return {
            "name": "Candidate Name",
            "email": "email@example.com",
            "phone": "+20 123 456 7890",
            "location": "Cairo, Egypt",
            "linkedin_url": "",
            "github_url": "",
            "experience": [],
            "education": [],
            "skills": [],
        }
    
    with open(profile_path, encoding="utf-8") as f:
        projects_data = json.load(f)
    
    tech_skills = set()
    for project in projects_data:
        tech_skills.update(project.get("tech_stack", []))
    
    return {
        "name": "Your Name",
        "email": "your.email@example.com",
        "phone": "+20 123 456 7890",
        "location": "Cairo, Egypt",
        "linkedin_url": "https://linkedin.com/in/yourprofile",
        "github_url": "https://github.com/yourusername",
        "experience": [
            {
                "company": "Previous Company",
                "position": "Software Engineer",
                "period": "Jan 2022 - Present",
                "description": "Developed and maintained software applications",
            }
        ],
        "education": [
            {
                "degree": "Bachelor of Computer Science",
                "institution": "University Name",
                "period": "2018 - 2022",
                "gpa": "3.8/4.0",
                "honors": "Graduated with Honors",
            }
        ],
        "skills": sorted(list(tech_skills)),
        "certifications": [],
    }


def _build_cv_context(tailored_cv: object, user_profile: dict) -> dict:
    """Build context dictionary for CV template."""
    return {
        "name": user_profile.get("name", "Your Name"),
        "email": user_profile.get("email", ""),
        "phone": user_profile.get("phone", ""),
        "location": user_profile.get("location", ""),
        "linkedin_url": user_profile.get("linkedin_url", ""),
        "github_url": user_profile.get("github_url", ""),
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
        "education": user_profile.get("education", []),
        "certifications": user_profile.get("certifications", []),
    }


def _build_cover_letter_context(
    tailored_cover_letter: object,
    user_profile: dict,
    job: dict,
) -> dict:
    """Build context dictionary for cover letter template."""
    from datetime import date
    
    return {
        "name": user_profile.get("name", "Your Name"),
        "email": user_profile.get("email", ""),
        "phone": user_profile.get("phone", ""),
        "location": user_profile.get("location", ""),
        "date": date.today().strftime("%B %d, %Y"),
        "recipient_name": "",
        "company_name": job.get("company", ""),
        "company_address": "",
        "opening": tailored_cover_letter.opening,
        "body_paragraph_1": tailored_cover_letter.body_paragraph_1,
        "body_paragraph_2": tailored_cover_letter.body_paragraph_2,
        "closing": tailored_cover_letter.closing,
    }
