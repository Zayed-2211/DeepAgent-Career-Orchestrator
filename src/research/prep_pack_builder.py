"""
Prep Pack builder - combines all research into a comprehensive document.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from loguru import logger

from config.settings import CONFIG_DIR


class PrepPackBuilder:
    """
    Assembles company research into a "Prep Pack" markdown document.
    
    Combines Glassdoor insights, LinkedIn data, and community sentiment
    into a single, actionable document for interview preparation.
    """
    
    def __init__(self, config_path: Path | None = None):
        """Initialize prep pack builder with config."""
        self.config = self._load_config(config_path)
        logger.info("[prep_pack] Initialized")
    
    def _load_config(self, config_path: Path | None) -> dict:
        """Load research config."""
        if config_path is None:
            config_path = CONFIG_DIR / "research.json"
        
        if not config_path.exists():
            logger.warning(f"[prep_pack] Config not found: {config_path}, using defaults")
            return self._default_config()
        
        with open(config_path, encoding="utf-8") as f:
            config = json.load(f)
        
        return config
    
    def _default_config(self) -> dict:
        """Default config if file not found."""
        return {
            "prep_pack": {
                "enabled": True,
                "format": "markdown",
                "filename": "prep_pack.md",
                "sections": {
                    "company_overview": True,
                    "glassdoor_insights": True,
                    "community_sentiment": True,
                    "interview_questions": True,
                    "red_flags": True,
                    "key_takeaways": True,
                },
                "include_sources": True,
            }
        }
    
    def build_prep_pack(
        self,
        job: dict,
        glassdoor_insights: dict | None = None,
        linkedin_data: dict | None = None,
        community_sentiment: dict | None = None,
        output_path: Path | None = None,
    ) -> Path:
        """
        Build a comprehensive prep pack document.
        
        Args:
            job: Job posting data
            glassdoor_insights: Glassdoor research results
            linkedin_data: LinkedIn company data
            community_sentiment: Community research results
            output_path: Where to save the prep pack
        
        Returns:
            Path to generated prep pack file
        """
        if not self.config.get("prep_pack", {}).get("enabled", True):
            logger.info("[prep_pack] Prep pack generation disabled in config")
            return None
        
        company_name = job.get("company", "Unknown Company")
        job_title = job.get("title", "Unknown Position")
        
        logger.info(f"[prep_pack] Building prep pack for: {company_name} - {job_title}")
        
        sections = self.config.get("prep_pack", {}).get("sections", {})
        
        content = []
        
        content.append(self._build_header(company_name, job_title))
        
        if sections.get("company_overview", True):
            content.append(self._build_company_overview(job, linkedin_data))
        
        if sections.get("glassdoor_insights", True) and glassdoor_insights:
            content.append(self._build_glassdoor_section(glassdoor_insights))
        
        if sections.get("community_sentiment", True) and community_sentiment:
            content.append(self._build_community_section(community_sentiment))
        
        if sections.get("interview_questions", True) and glassdoor_insights:
            content.append(self._build_interview_questions_section(glassdoor_insights))
        
        if sections.get("red_flags", True):
            content.append(self._build_red_flags_section(glassdoor_insights))
        
        if sections.get("key_takeaways", True):
            content.append(self._build_key_takeaways(glassdoor_insights, job))
        
        content.append(self._build_footer())
        
        markdown = "\n\n".join(content)
        
        if output_path is None:
            filename = self.config.get("prep_pack", {}).get("filename", "prep_pack.md")
            output_path = Path(filename)
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(markdown)
        
        logger.info(f"[prep_pack] Prep pack saved → {output_path}")
        return output_path
    
    def _build_header(self, company_name: str, job_title: str) -> str:
        """Build document header."""
        date = datetime.now().strftime("%B %d, %Y")
        
        return f"""# Interview Prep Pack

**Company:** {company_name}  
**Position:** {job_title}  
**Generated:** {date}

---

## 📋 Overview

This document contains research and insights to help you prepare for your interview with **{company_name}**. It includes employee reviews, company culture insights, common interview questions, and potential red flags to be aware of.

**How to Use This Document:**
1. Read the company overview to understand their business and culture
2. Review Glassdoor insights to know what employees say
3. Prepare answers for common interview questions
4. Note any red flags and prepare questions to ask the interviewer
5. Use key takeaways to tailor your responses

---"""
    
    def _build_company_overview(self, job: dict, linkedin_data: dict | None) -> str:
        """Build company overview section."""
        company_name = job.get("company", "Unknown Company")
        company_industry = job.get("company_industry", "")
        
        content = [f"## 🏢 Company Overview\n"]
        content.append(f"**Company Name:** {company_name}")
        
        if company_industry:
            content.append(f"**Industry:** {company_industry}")
        
        if linkedin_data:
            if linkedin_data.get("employee_count"):
                content.append(f"**Size:** {linkedin_data['employee_count']} employees")
            
            if linkedin_data.get("description"):
                content.append(f"\n**About:**\n{linkedin_data['description']}")
        
        return "\n".join(content)
    
    def _build_glassdoor_section(self, insights: dict) -> str:
        """Build Glassdoor insights section."""
        content = [f"## ⭐ Glassdoor Insights\n"]
        
        if insights.get("overall_rating"):
            rating = insights["overall_rating"]
            stars = "★" * int(rating) + "☆" * (5 - int(rating))
            content.append(f"**Overall Rating:** {rating}/5.0 {stars}\n")
        
        if insights.get("sentiment"):
            sentiment_emoji = {
                "positive": "😊",
                "negative": "😟",
                "mixed": "😐",
                "neutral": "😶",
            }
            emoji = sentiment_emoji.get(insights["sentiment"], "")
            content.append(f"**Employee Sentiment:** {insights['sentiment'].title()} {emoji}\n")
        
        if insights.get("pros"):
            content.append("### ✅ What Employees Like")
            for pro in insights["pros"]:
                content.append(f"- {pro}")
            content.append("")
        
        if insights.get("cons"):
            content.append("### ❌ What Employees Dislike")
            for con in insights["cons"]:
                content.append(f"- {con}")
            content.append("")
        
        if insights.get("summary"):
            content.append(f"### 📝 Summary\n")
            content.append(insights["summary"])
        
        return "\n".join(content)
    
    def _build_community_section(self, sentiment: dict) -> str:
        """Build community sentiment section."""
        content = [f"## 💬 Community Sentiment\n"]
        
        if sentiment.get("summary"):
            content.append(sentiment["summary"])
        
        if sentiment.get("mentions"):
            content.append(f"\n**Mentions Found:** {sentiment['mentions']}")
        
        return "\n".join(content)
    
    def _build_interview_questions_section(self, insights: dict) -> str:
        """Build interview questions section."""
        questions = insights.get("interview_questions", [])
        
        if not questions:
            return ""
        
        content = [f"## 🎯 Common Interview Questions\n"]
        content.append("Based on employee reports, here are questions you might encounter:\n")
        
        for i, question in enumerate(questions, 1):
            content.append(f"{i}. {question}")
        
        content.append("\n**Tip:** Prepare STAR (Situation, Task, Action, Result) answers for behavioral questions.")
        
        return "\n".join(content)
    
    def _build_red_flags_section(self, insights: dict | None) -> str:
        """Build red flags section."""
        red_flags = insights.get("red_flags", []) if insights else []
        
        content = [f"## 🚩 Potential Red Flags\n"]
        
        if red_flags:
            content.append("**Important concerns to be aware of:**\n")
            for flag in red_flags:
                content.append(f"- ⚠️ {flag}")
            
            content.append("\n**Action:** Ask the interviewer about these concerns tactfully during your interview.")
        else:
            content.append("✅ No major red flags identified in the research.")
        
        return "\n".join(content)
    
    def _build_key_takeaways(self, insights: dict | None, job: dict) -> str:
        """Build key takeaways section."""
        content = [f"## 💡 Key Takeaways\n"]
        
        content.append("**Before Your Interview:**")
        content.append("- [ ] Review the job description and match your experience to requirements")
        content.append("- [ ] Prepare examples demonstrating relevant skills")
        content.append("- [ ] Research the company's recent projects/news")
        content.append("- [ ] Prepare thoughtful questions about the role and team")
        
        if insights and insights.get("cons"):
            content.append("\n**Questions to Ask the Interviewer:**")
            content.append(f"- How does the team handle [mention a concern from cons]?")
            content.append("- What does success look like in this role after 6 months?")
            content.append("- Can you describe the team culture and collaboration style?")
        
        content.append("\n**During the Interview:**")
        content.append("- Be authentic and enthusiastic")
        content.append("- Listen carefully and ask clarifying questions")
        content.append("- Take notes on important points")
        content.append("- Express genuine interest in the company's mission")
        
        return "\n".join(content)
    
    def _build_footer(self) -> str:
        """Build document footer."""
        include_sources = self.config.get("prep_pack", {}).get("include_sources", True)
        
        if not include_sources:
            return ""
        
        return f"""---

## 📚 Sources

This prep pack was compiled from:
- Glassdoor employee reviews
- LinkedIn company information
- Web search results
- Community discussions

**Note:** Information is aggregated from public sources and may not be 100% accurate or up-to-date. Use this as a guide, not absolute truth. Always verify important details during your interview.

---

*Generated by DeepAgent Career Orchestrator*"""
