"""
CV tailoring sub-agent using Gemini to customize CVs for specific jobs.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from loguru import logger

from config.settings import CONFIG_DIR, get_settings
from src.generators.schemas import TailoredCV


class CVTailor:
    """
    Gemini-powered CV tailoring agent.
    
    Takes a job posting, matched projects, and user profile,
    then generates a tailored CV optimized for that specific role.
    """
    
    def __init__(self, config_path: Path | None = None):
        """Initialize CV tailor with config."""
        self.config = self._load_config(config_path)
        
        self.model_name = self.config.get("cv_generation", {}).get("model", "gemini-2.5-flash")
        temperature = self.config.get("cv_generation", {}).get("temperature", 0.3)
        
        api_key = get_settings().gemini_api_key
        if not api_key:
            logger.error("[cv_tailor] GEMINI_API_KEY not set")
            self.llm = None
        else:
            self.llm = ChatGoogleGenerativeAI(
                model=self.model_name,
                google_api_key=api_key,
                temperature=temperature,
            ).with_structured_output(TailoredCV)
        
        logger.info(f"[cv_tailor] Initialized with model: {self.model_name}")
    
    def _load_config(self, config_path: Path | None) -> dict:
        """Load generators config."""
        if config_path is None:
            config_path = CONFIG_DIR / "generators.json"
        
        if not config_path.exists():
            logger.warning(f"[cv_tailor] Config not found: {config_path}, using defaults")
            return self._default_config()
        
        with open(config_path, encoding="utf-8") as f:
            config = json.load(f)
        
        return config
    
    def _default_config(self) -> dict:
        """Default config if file not found."""
        return {
            "cv_generation": {
                "model": "gemini-2.5-flash",
                "temperature": 0.3,
                "max_projects": 3,
                "max_experience_bullets": 5,
                "max_project_bullets": 3,
            }
        }
    
    def tailor_cv(
        self,
        job: dict,
        matched_projects: list[dict],
        user_profile: dict,
    ) -> TailoredCV:
        """
        Generate a tailored CV for a specific job.
        
        Args:
            job: Parsed job posting with intelligence data
            matched_projects: Top matched projects from matching_node
            user_profile: User's profile data (experience, education, skills)
        
        Returns:
            TailoredCV object with customized content
        """
        prompt = self._build_prompt(job, matched_projects, user_profile)
        
        if not self.llm:
            raise RuntimeError("CV tailor not initialized - GEMINI_API_KEY missing")
        
        try:
            job_title = job.get('title', 'Unknown')
            company = job.get('company', 'Unknown')
            logger.info(f"[cv_tailor] Starting CV tailoring for '{job_title}' at {company}")
            logger.debug(f"[cv_tailor] Using model: {self.model_name}")
            
            # Get configurable prompts from config
            system_prompt = self.config.get("cv_generation", {}).get(
                "system_prompt",
                "You are an expert CV writer specializing in ATS-optimized, tailored resumes for tech roles."
            )
            custom_instructions = self.config.get("cv_generation", {}).get("custom_instructions", "")
            
            # Add custom instructions to the prompt if provided
            full_prompt = prompt
            if custom_instructions:
                full_prompt = f"{custom_instructions}\n\n{prompt}"
            
            prompt_template = ChatPromptTemplate.from_messages([
                ("system", system_prompt),
                ("human", "{prompt}")
            ])
            
            chain = prompt_template | self.llm
            tailored_cv = chain.invoke({"prompt": full_prompt})
            
            # Rate limiting delay between Gemini calls
            rate_limit_config = self.config.get("rate_limiting", {})
            if rate_limit_config.get("enabled", True):
                delay = rate_limit_config.get("delay_between_gemini_calls_seconds", 60)
                logger.debug(f"[cv_tailor] Rate limiting: waiting {delay}s before next call")
                time.sleep(delay)
            else:
                time.sleep(4)  # Minimum delay
            
            logger.info(f"[cv_tailor] ✓ CV tailored successfully - {len(tailored_cv.experience)} experience entries, {len(tailored_cv.projects)} projects")
            return tailored_cv
        
        except Exception as exc:
            logger.error(f"[cv_tailor] ✗ CV tailoring failed for '{job.get('title', 'Unknown')}': {exc}")
            raise
    
    def _build_prompt(
        self,
        job: dict,
        matched_projects: list[dict],
        user_profile: dict,
    ) -> str:
        """Build the Gemini prompt for CV tailoring."""
        job_title = job.get("title", "Unknown Position")
        company = job.get("company", "Unknown Company")
        
        intelligence = job.get("intelligence", {})
        role_summary = intelligence.get("role_summary", "")
        tech_stack = intelligence.get("tech_stack", [])
        required_skills = intelligence.get("required_skills", [])
        preferred_skills = intelligence.get("preferred_skills", [])
        responsibilities = intelligence.get("responsibilities", [])
        
        max_projects = self.config.get("cv_generation", {}).get("max_projects", 3)
        max_exp_bullets = self.config.get("cv_generation", {}).get("max_experience_bullets", 5)
        max_proj_bullets = self.config.get("cv_generation", {}).get("max_project_bullets", 3)
        
        prompt = f"""You are an expert CV writer specializing in ATS-optimized, tailored resumes for tech roles.

**Job Details:**
- Position: {job_title}
- Company: {company}
- Role Summary: {role_summary}
- Required Tech Stack: {', '.join(tech_stack[:10])}
- Required Skills: {', '.join(required_skills[:10])}
- Preferred Skills: {', '.join(preferred_skills[:5])}
- Key Responsibilities: {', '.join(responsibilities[:5])}

**Matched Projects (Top {max_projects}):**
{self._format_projects(matched_projects[:max_projects])}

**User Profile:**
{self._format_user_profile(user_profile)}

**Task:**
Generate a tailored CV that:
1. **Professional Summary**: Write a 2-3 sentence summary that positions the candidate as an ideal fit for this specific role. Mention the most relevant skills and experience.

2. **Experience**: Tailor the candidate's work experience bullets to emphasize achievements and responsibilities that align with the job requirements. Maximum {max_exp_bullets} bullets per role. Use action verbs and quantify results where possible.

3. **Projects**: Select and tailor the top {max_projects} matched projects. For each project, write {max_proj_bullets} bullets that highlight aspects most relevant to the job. Emphasize technologies and outcomes that match the job requirements.

4. **Technical Skills**: List technical skills that appear in BOTH the user's profile AND the job requirements. Prioritize exact matches. Maximum 15 skills.

5. **Soft Skills**: Extract soft skills mentioned in the job description that the user likely possesses based on their experience. Maximum 5 skills.

**Guidelines:**
- Be honest - don't invent experience or skills
- Use keywords from the job description naturally
- Quantify achievements with numbers/percentages when possible
- Keep language professional and concise
- Optimize for ATS parsing (avoid fancy formatting in text)
- Emphasize impact and results, not just duties

Generate the tailored CV now."""

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
            github_url = proj.get("github_url", "")
            
            formatted.append(
                f"{i}. **{name}**\n"
                f"   - Description: {description}\n"
                f"   - Tech Stack: {', '.join(tech_stack)}\n"
                f"   - GitHub: {github_url if github_url else 'N/A'}"
            )
        
        return "\n".join(formatted)
    
    def _format_user_profile(self, profile: dict) -> str:
        """Format user profile for the prompt."""
        experience = profile.get("experience", [])
        education = profile.get("education", [])
        skills = profile.get("skills", [])
        
        formatted = []
        
        if experience:
            formatted.append("**Work Experience:**")
            for exp in experience[:3]:
                company = exp.get("company", "Unknown")
                position = exp.get("position", "Unknown")
                period = exp.get("period", "")
                description = exp.get("description", "")
                
                formatted.append(f"- {position} at {company} ({period})")
                if description:
                    formatted.append(f"  {description}")
        
        if education:
            formatted.append("\n**Education:**")
            for edu in education:
                degree = edu.get("degree", "")
                institution = edu.get("institution", "")
                period = edu.get("period", "")
                
                formatted.append(f"- {degree} from {institution} ({period})")
        
        if skills:
            formatted.append(f"\n**Skills:** {', '.join(skills[:20])}")
        
        return "\n".join(formatted) if formatted else "No profile data available."
