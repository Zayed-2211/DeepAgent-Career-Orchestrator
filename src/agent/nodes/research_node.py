"""
Research node - Phase 8: Company research using Tavily and Gemini.
"""

from __future__ import annotations

import json
from pathlib import Path

from loguru import logger

from config.settings import CONFIG_DIR, DATA_DIR
from src.agent.state import AgentState
from src.research.glassdoor_researcher import GlassdoorResearcher
from src.research.prep_pack_builder import PrepPackBuilder
from src.research.web_searcher import WebSearcher


def research_node(state: AgentState) -> dict:
    """
    Research company using Glassdoor, LinkedIn, and web search.
    
    This node is called after dispatch_node for approved jobs.
    It generates a "Prep Pack" with company insights.
    
    Args:
        state: Current agent state with job data
    
    Returns:
        Updated state with company research data
    """
    logger.info("[research] Starting company research...")
    
    config = _load_config()
    
    if not config.get("research_enabled", True):
        logger.info("[research] Research disabled in config")
        return {"routing": "skip"}
    
    if config.get("dev_mode", {}).get("skip_research", False):
        logger.info("[research] Skipping research (dev mode)")
        return {"routing": "skip"}
    
    current_job = state.get("current_job", {})
    job_uid = state.get("job_uid")
    
    if not job_uid:
        logger.warning("[research] No job_uid in state")
        return {"routing": "error", "error": "No job_uid for research"}
    
    company_name = current_job.get("company", "")
    
    if not company_name or company_name.lower() in ["unknown", "n/a", "none"]:
        logger.warning(f"[research] Invalid company name: {company_name}")
        return {"routing": "skip"}
    
    safe_job_uid = job_uid.replace(":", "_")
    output_dir = DATA_DIR / "outputs" / safe_job_uid
    output_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"[research] Output directory: {output_dir}")
    
    company_research = {}
    
    try:
        web_searcher = WebSearcher()
        
        if not web_searcher.is_available():
            logger.warning("[research] Web searcher not available - skipping research")
            return {"routing": "skip"}
        
        if config.get("glassdoor_research", {}).get("enabled", True):
            glassdoor_researcher = GlassdoorResearcher()
            
            logger.info(f"[research] Researching Glassdoor for: {company_name}")
            glassdoor_insights = glassdoor_researcher.research_company(company_name)
            
            if glassdoor_insights:
                company_research["glassdoor"] = glassdoor_insights.model_dump()
                logger.info(f"[research] Glassdoor research complete - Sentiment: {glassdoor_insights.sentiment}")
        
        if config.get("linkedin_research", {}).get("enabled", True):
            logger.info(f"[research] Searching LinkedIn for: {company_name}")
            linkedin_results = web_searcher.search_company(company_name, "linkedin")
            
            if linkedin_results:
                company_research["linkedin"] = {
                    "results": linkedin_results[:3],
                    "summary": _summarize_linkedin_results(linkedin_results),
                }
        
        prep_pack_builder = PrepPackBuilder()
        
        prep_pack_path = output_dir / "prep_pack.md"
        
        prep_pack_builder.build_prep_pack(
            job=current_job,
            glassdoor_insights=company_research.get("glassdoor"),
            linkedin_data=company_research.get("linkedin"),
            community_sentiment=None,
            output_path=prep_pack_path,
        )
        
        company_research["prep_pack_path"] = str(prep_pack_path)
        
        logger.info(f"[research] Research complete - Prep pack → {prep_pack_path}")
        
        return {
            "company_research": company_research,
            "routing": "continue",
        }
    
    except Exception as exc:
        logger.error(f"[research] Research failed: {exc}")
        return {
            "routing": "error",
            "error": f"Research failed: {exc}",
        }


def _load_config() -> dict:
    """Load research config."""
    config_path = CONFIG_DIR / "research.json"
    
    if not config_path.exists():
        return {"research_enabled": True}
    
    with open(config_path, encoding="utf-8") as f:
        return json.load(f)


def _summarize_linkedin_results(results: list[dict]) -> str:
    """Create a brief summary of LinkedIn search results."""
    if not results:
        return "No LinkedIn data found."
    
    summaries = []
    for result in results[:3]:
        title = result.get("title", "")
        snippet = result.get("snippet", "")
        
        if snippet:
            summaries.append(f"- {title}: {snippet[:200]}")
    
    return "\n".join(summaries) if summaries else "No detailed information available."
