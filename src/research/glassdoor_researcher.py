"""
Glassdoor company research using web search and Gemini summarization.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import google.generativeai as genai
from loguru import logger
from pydantic import BaseModel, Field

from config.settings import CONFIG_DIR
from src.research.web_searcher import WebSearcher


class GlassdoorInsights(BaseModel):
    """Structured Glassdoor research output."""
    
    overall_rating: float | None = Field(
        default=None,
        description="Overall company rating (1-5 stars)",
    )
    
    pros: list[str] = Field(
        default_factory=list,
        description="Common positive points from reviews",
        max_length=5,
    )
    
    cons: list[str] = Field(
        default_factory=list,
        description="Common negative points from reviews",
        max_length=5,
    )
    
    interview_questions: list[str] = Field(
        default_factory=list,
        description="Common interview questions mentioned",
        max_length=5,
    )
    
    red_flags: list[str] = Field(
        default_factory=list,
        description="Potential red flags identified",
        max_length=3,
    )
    
    sentiment: str = Field(
        default="neutral",
        description="Overall sentiment (positive/negative/neutral/mixed)",
    )
    
    summary: str = Field(
        default="",
        description="Brief summary of findings",
        max_length=500,
    )


class GlassdoorResearcher:
    """
    Research companies using Glassdoor reviews via web search.
    
    Uses Tavily to find Glassdoor pages, then Gemini to summarize insights.
    """
    
    def __init__(self, config_path: Path | None = None):
        """Initialize Glassdoor researcher with config."""
        self.config = self._load_config(config_path)
        self.web_searcher = WebSearcher(config_path)
        
        model_name = self.config.get("summarization", {}).get("model", "gemini-2.5-flash")
        temperature = self.config.get("summarization", {}).get("temperature", 0.2)
        
        self.model = genai.GenerativeModel(
            model_name=model_name,
            generation_config={
                "temperature": temperature,
                "response_mime_type": "application/json",
                "response_schema": GlassdoorInsights,
            },
        )
        
        logger.info(f"[glassdoor] Initialized with model: {model_name}")
    
    def _load_config(self, config_path: Path | None) -> dict:
        """Load research config."""
        if config_path is None:
            config_path = CONFIG_DIR / "research.json"
        
        if not config_path.exists():
            logger.warning(f"[glassdoor] Config not found: {config_path}, using defaults")
            return self._default_config()
        
        with open(config_path, encoding="utf-8") as f:
            config = json.load(f)
        
        return config
    
    def _default_config(self) -> dict:
        """Default config if file not found."""
        return {
            "glassdoor_research": {
                "enabled": True,
                "search_query_template": "{company_name} Glassdoor reviews Egypt",
                "max_reviews_to_analyze": 10,
                "extract_interview_questions": True,
            },
            "summarization": {
                "model": "gemini-2.5-flash",
                "temperature": 0.2,
                "extract_red_flags": True,
                "sentiment_analysis": True,
            },
            "rate_limiting": {
                "gemini_delay_seconds": 4,
            },
        }
    
    def research_company(self, company_name: str) -> GlassdoorInsights | None:
        """
        Research a company using Glassdoor reviews.
        
        Args:
            company_name: Company name to research
        
        Returns:
            GlassdoorInsights object with summarized findings, or None if research fails
        """
        if not self.config.get("glassdoor_research", {}).get("enabled", True):
            logger.info("[glassdoor] Glassdoor research disabled in config")
            return None
        
        if not self.web_searcher.is_available():
            logger.warning("[glassdoor] Web searcher not available")
            return None
        
        search_results = self.web_searcher.search_company(company_name, "glassdoor")
        
        if not search_results:
            logger.warning(f"[glassdoor] No search results for: {company_name}")
            return None
        
        insights = self._analyze_results(company_name, search_results)
        
        return insights
    
    def _analyze_results(
        self,
        company_name: str,
        search_results: list[dict],
    ) -> GlassdoorInsights | None:
        """Analyze search results using Gemini."""
        combined_content = self._combine_search_results(search_results)
        
        if not combined_content:
            logger.warning(f"[glassdoor] No content to analyze for: {company_name}")
            return None
        
        prompt = self._build_analysis_prompt(company_name, combined_content)
        
        try:
            logger.info(f"[glassdoor] Analyzing Glassdoor data for: {company_name}")
            
            response = self.model.generate_content(prompt)
            
            delay = self.config.get("rate_limiting", {}).get("gemini_delay_seconds", 4)
            time.sleep(delay)
            
            insights = GlassdoorInsights.model_validate_json(response.text)
            
            logger.info(f"[glassdoor] Analysis complete - Sentiment: {insights.sentiment}")
            return insights
        
        except Exception as exc:
            logger.error(f"[glassdoor] Analysis failed: {exc}")
            return None
    
    def _combine_search_results(self, results: list[dict]) -> str:
        """Combine search results into a single text for analysis."""
        combined = []
        
        for i, result in enumerate(results[:5], 1):
            title = result.get("title", "")
            snippet = result.get("snippet", "")
            content = result.get("content", "")
            url = result.get("url", "")
            
            combined.append(f"**Source {i}:** {title}")
            combined.append(f"URL: {url}")
            if snippet:
                combined.append(f"Snippet: {snippet}")
            if content:
                combined.append(f"Content: {content[:1000]}")
            combined.append("---")
        
        return "\n".join(combined)
    
    def _build_analysis_prompt(self, company_name: str, content: str) -> str:
        """Build Gemini prompt for Glassdoor analysis."""
        extract_questions = self.config.get("glassdoor_research", {}).get("extract_interview_questions", True)
        extract_red_flags = self.config.get("summarization", {}).get("extract_red_flags", True)
        
        prompt = f"""You are a company research analyst specializing in employee reviews and workplace insights.

**Company:** {company_name}

**Task:** Analyze the following Glassdoor-related search results and extract key insights.

**Search Results:**
{content}

**Analysis Requirements:**

1. **Overall Rating:** If mentioned, extract the overall company rating (1-5 stars). If not found, set to null.

2. **Pros (Top 5):** Identify the most commonly mentioned positive aspects:
   - Work culture
   - Benefits and compensation
   - Growth opportunities
   - Work-life balance
   - Management quality
   - Technology stack
   - Team collaboration

3. **Cons (Top 5):** Identify the most commonly mentioned negative aspects:
   - Management issues
   - Compensation concerns
   - Work-life balance problems
   - Limited growth
   - Technical debt
   - Poor processes

4. **Interview Questions (Top 5):** {
    "Extract common interview questions mentioned in reviews." if extract_questions 
    else "Leave empty - not required."
}

5. **Red Flags (Top 3):** {
    "Identify serious concerns like: high turnover, late payments, toxic culture, mass layoffs, legal issues." if extract_red_flags
    else "Leave empty - not required."
}

6. **Sentiment:** Classify overall sentiment as:
   - "positive" - mostly good reviews
   - "negative" - mostly bad reviews
   - "mixed" - balanced mix
   - "neutral" - insufficient data

7. **Summary (max 500 words):** Write a concise summary covering:
   - Company reputation
   - Employee satisfaction
   - Key strengths and weaknesses
   - Whether this seems like a good place to work

**Guidelines:**
- Be factual and objective
- Don't invent information not in the sources
- If data is insufficient, say so
- Prioritize recent information over old reviews
- Focus on patterns, not individual complaints

Generate the analysis now."""

        return prompt
