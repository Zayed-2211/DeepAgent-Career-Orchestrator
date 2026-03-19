"""
Tavily web search API wrapper for company research.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

from loguru import logger

from config.settings import CONFIG_DIR


class WebSearcher:
    """
    Tavily API wrapper for web search.
    
    Provides structured search results for company research.
    """
    
    def __init__(self, config_path: Path | None = None):
        """Initialize web searcher with config."""
        self.config = self._load_config(config_path)
        self.api_key = os.getenv("TAVILY_API_KEY")
        
        if not self.api_key:
            logger.warning("[web_search] TAVILY_API_KEY not set - research will be disabled")
            self.client = None
        else:
            try:
                from tavily import TavilyClient
                self.client = TavilyClient(api_key=self.api_key)
                logger.info("[web_search] Tavily client initialized")
            except ImportError:
                logger.error("[web_search] tavily-python not installed. Run: pip install tavily-python")
                self.client = None
    
    def _load_config(self, config_path: Path | None) -> dict:
        """Load research config."""
        if config_path is None:
            config_path = CONFIG_DIR / "research.json"
        
        if not config_path.exists():
            logger.warning(f"[web_search] Config not found: {config_path}, using defaults")
            return self._default_config()
        
        with open(config_path, encoding="utf-8") as f:
            config = json.load(f)
        
        return config
    
    def _default_config(self) -> dict:
        """Default config if file not found."""
        return {
            "web_search": {
                "enabled": True,
                "max_results": 5,
                "search_depth": "basic",
                "timeout": 10,
            },
            "rate_limiting": {
                "tavily_delay_seconds": 1,
                "max_retries": 3,
            },
        }
    
    def search(
        self,
        query: str,
        max_results: int | None = None,
        include_domains: list[str] | None = None,
        exclude_domains: list[str] | None = None,
    ) -> list[dict]:
        """
        Search the web using Tavily API.
        
        Args:
            query: Search query
            max_results: Maximum number of results (default from config)
            include_domains: Only search these domains
            exclude_domains: Exclude these domains
        
        Returns:
            List of search results with title, url, snippet, content
        """
        if not self.config.get("web_search", {}).get("enabled", True):
            logger.info("[web_search] Web search disabled in config")
            return []
        
        if not self.client:
            logger.warning("[web_search] Tavily client not available")
            return []
        
        max_results = max_results or self.config.get("web_search", {}).get("max_results", 5)
        search_depth = self.config.get("web_search", {}).get("search_depth", "basic")
        
        include_domains = include_domains or self.config.get("web_search", {}).get("include_domains", [])
        exclude_domains = exclude_domains or self.config.get("web_search", {}).get("exclude_domains", [])
        
        try:
            logger.info(f"[web_search] Searching: {query}")
            
            response = self.client.search(
                query=query,
                max_results=max_results,
                search_depth=search_depth,
                include_domains=include_domains if include_domains else None,
                exclude_domains=exclude_domains if exclude_domains else None,
            )
            
            delay = self.config.get("rate_limiting", {}).get("tavily_delay_seconds", 1)
            time.sleep(delay)
            
            results = response.get("results", [])
            
            logger.info(f"[web_search] Found {len(results)} results")
            return results
        
        except Exception as exc:
            logger.error(f"[web_search] Search failed: {exc}")
            return []
    
    def search_company(
        self,
        company_name: str,
        search_type: str = "general",
    ) -> list[dict]:
        """
        Search for company information.
        
        Args:
            company_name: Company name to search
            search_type: Type of search (general, glassdoor, linkedin, news)
        
        Returns:
            List of search results
        """
        query_templates = {
            "general": f"{company_name} company overview Egypt",
            "glassdoor": f"{company_name} Glassdoor reviews Egypt",
            "linkedin": f"{company_name} LinkedIn company page",
            "news": f"{company_name} company news Egypt 2024",
        }
        
        query = query_templates.get(search_type, f"{company_name}")
        
        return self.search(query)
    
    def is_available(self) -> bool:
        """Check if Tavily API is available."""
        return self.client is not None and self.api_key is not None
