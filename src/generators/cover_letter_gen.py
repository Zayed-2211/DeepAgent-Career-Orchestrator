"""
Cover letter generation sub-agent using Gemini.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from loguru import logger

from config.settings import CONFIG_DIR, get_settings
from src.generators.schemas import TailoredCoverLetter


class CoverLetterGenerator:
    """
    Gemini-powered cover letter generator.
    
    Creates personalized cover letters based on job requirements,
    matched projects, and optional company research.
    """
    
    def __init__(self, config_path: Path | None = None):
        """Initialize cover letter generator with config."""
        self.config = self._load_config(config_path)
        
        self.model_name = self.config.get("cover_letter_generation", {}).get("model", "gemini-2.5-flash")
        temperature = self.config.get("cover_letter_generation", {}).get("temperature", 0.4)
        
        api_key = get_settings().gemini_api_key
        if not api_key:
            logger.error("[cover_letter] GEMINI_API_KEY not set")
            self.llm = None
        else:
            self.llm = ChatGoogleGenerativeAI(
                model=self.model_name,
                google_api_key=api_key,
                temperature=temperature,
            ).with_structured_output(TailoredCoverLetter)
        
        logger.info(f"[cover_letter] Initialized with model: {self.model_name}")
    
    def _load_config(self, config_path: Path | None) -> dict:
        """Load generators config."""
        if config_path is None:
            config_path = CONFIG_DIR / "generators.json"
        
        if not config_path.exists():
            logger.warning(f"[cover_letter] Config not found: {config_path}, using defaults")
            return self._default_config()
        
        with open(config_path, encoding="utf-8") as f:
            config = json.load(f)
        
        return config
    
    def _default_config(self) -> dict:
        """Default config if file not found."""
        return {
            "cover_letter_generation": {
                "model": "gemini-2.5-flash",
                "temperature": 0.4,
                "tone": "professional",
                "include_company_research": True,
            }
        }
    
    def generate_cover_letter(
        self,
        job: dict,
        matched_projects: list[dict],
        user_profile: dict,
        company_research: dict | None = None,
    ) -> TailoredCoverLetter:
        """
        Generate a tailored cover letter for a specific job.
        
        Args:
            job: Parsed job posting with intelligence data
            matched_projects: Top matched projects from matching_node
            user_profile: User's profile data
            company_research: Optional company research from Phase 8
        
        Returns:
            TailoredCoverLetter object with customized content
        """
        prompt = self._build_prompt(job, matched_projects, user_profile, company_research)
        
        if not self.llm:
            raise RuntimeError("Cover letter generator not initialized - GEMINI_API_KEY missing")
        
        try:
            job_title = job.get('title', 'Unknown')
            company = job.get('company', 'Unknown')
            logger.info(f"[cover_letter] Starting cover letter generation for '{job_title}' at {company}")
            logger.debug(f"[cover_letter] Using model: {self.model_name}")
            
            prompt_template = ChatPromptTemplate.from_messages([
                ("system", "You are an expert cover letter writer specializing in compelling, personalized application letters for tech roles."),
                ("human", "{prompt}")
            ])
            
            chain = prompt_template | self.llm
            cover_letter = chain.invoke({"prompt": prompt})
            
            time.sleep(4)
            
            logger.info(f"[cover_letter] ✓ Cover letter generated successfully - Tone: {cover_letter.tone}")
            return cover_letter
        
        except Exception as exc:
            logger.error(f"[cover_letter] ✗ Cover letter generation failed for '{job.get('title', 'Unknown')}': {exc}")
            raise
    
    def _build_prompt(
        self,
        job: dict,
        matched_projects: list[dict],
        user_profile: dict,
        company_research: dict | None,
    ) -> str:
        """Build the Gemini prompt for cover letter generation."""
        job_title = job.get("title", "Unknown Position")
        company = job.get("company", "Unknown Company")
        
        intelligence = job.get("intelligence", {})
        role_summary = intelligence.get("role_summary", "")
        required_skills = intelligence.get("required_skills", [])
        responsibilities = intelligence.get("responsibilities", [])
        
        tone = self.config.get("cover_letter_generation", {}).get("tone", "professional")
        
        user_name = user_profile.get("name", "Candidate")
        
        prompt = f"""You are an expert cover letter writer specializing in tech industry applications.

**Job Details:**
- Position: {job_title}
- Company: {company}
- Role Summary: {role_summary}
- Key Requirements: {', '.join(required_skills[:8])}
- Responsibilities: {', '.join(responsibilities[:5])}

**Candidate Profile:**
- Name: {user_name}
{self._format_user_profile(user_profile)}

**Top Matched Projects:**
{self._format_projects(matched_projects[:2])}

**Company Research:**
{self._format_company_research(company_research)}

**Task:**
Write a compelling cover letter with the following structure:

1. **Opening (150-200 words):**
   - Express genuine interest in the role and company
   - Briefly introduce yourself and your current role/status
   - Mention how you found the position (if known)
   - Hook the reader with a relevant achievement or passion

2. **Body Paragraph 1 (250-300 words):**
   - Highlight your most relevant experience and projects
   - Connect your background directly to the job requirements
   - Use specific examples from your matched projects
   - Quantify achievements where possible

3. **Body Paragraph 2 (250-300 words):**
   - Explain why you're excited about THIS specific company
   - Reference company research if available (culture, values, recent news)
   - Show how your skills and values align with the company
   - Demonstrate you've done your homework

4. **Closing (100-150 words):**
   - Reiterate your enthusiasm for the role
   - Call to action (request interview, mention availability)
   - Thank them for their consideration
   - Professional sign-off

**Guidelines:**
- Tone: {tone}
- Be authentic and enthusiastic, not generic
- Avoid clichés like "I am writing to apply for..."
- Show personality while remaining professional
- Use active voice and strong action verbs
- Keep paragraphs focused and well-structured
- Don't repeat what's in the CV - add new insights
- Proofread for grammar and clarity

Generate the cover letter now."""

        return prompt
    
    def _format_projects(self, projects: list[dict]) -> str:
        """Format matched projects for the prompt."""
        if not projects:
            return "No projects available."
        
        formatted = []
        for i, proj in enumerate(projects, 1):
            name = proj.get("name", "Unnamed Project")
            description = proj.get("description", "")
            tech_stack = proj.get("tech_stack", [])
            
            formatted.append(
                f"{i}. **{name}**\n"
                f"   - {description}\n"
                f"   - Technologies: {', '.join(tech_stack[:5])}"
            )
        
        return "\n".join(formatted)
    
    def _format_user_profile(self, profile: dict) -> str:
        """Format user profile for the prompt."""
        experience = profile.get("experience", [])
        education = profile.get("education", [])
        
        formatted = []
        
        if experience:
            latest_exp = experience[0] if experience else {}
            position = latest_exp.get("position", "")
            company = latest_exp.get("company", "")
            if position and company:
                formatted.append(f"- Current/Latest Role: {position} at {company}")
        
        if education:
            latest_edu = education[0] if education else {}
            degree = latest_edu.get("degree", "")
            institution = latest_edu.get("institution", "")
            if degree and institution:
                formatted.append(f"- Education: {degree} from {institution}")
        
        return "\n".join(formatted) if formatted else "No profile data available."
    
    def _format_company_research(self, research: dict | None) -> str:
        """Format company research for the prompt."""
        if not research:
            return "No company research available. Focus on the job description and general industry knowledge."
        
        formatted = []
        
        if research.get("glassdoor_summary"):
            formatted.append(f"**Glassdoor Insights:**\n{research['glassdoor_summary']}")
        
        if research.get("company_overview"):
            formatted.append(f"**Company Overview:**\n{research['company_overview']}")
        
        if research.get("recent_news"):
            formatted.append(f"**Recent News:**\n{research['recent_news']}")
        
        if research.get("culture_notes"):
            formatted.append(f"**Culture:**\n{research['culture_notes']}")
        
        return "\n\n".join(formatted) if formatted else "No detailed research available."
