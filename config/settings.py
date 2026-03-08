"""
Central configuration loader.
Reads from .env file and JSON config files using pydantic-settings.
"""

import json
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
DATA_DIR = PROJECT_ROOT / "data"

from config.search_queries import SEARCH_QUERIES, LOCATIONS
from config.platforms_config import PLATFORMS_CONFIG
from config.filters_and_sorting import FILTERS, SORTING
from config.projects_config import (
    GITHUB_PROFILE_URL,
    GITHUB_INCLUDE_REPOS,
    GITHUB_EXCLUDE_REPOS,
    CV_FILE,
    MANUAL_PROJECTS_FILE,
    PROFILE_INDEX_DIR,
)

# ---------------------------------------------------------------------------
# Environment settings (from .env)
# ---------------------------------------------------------------------------
class Settings(BaseSettings):
    """Loads environment variables from .env file."""

    # --- Required keys ---
    gemini_api_key: str = Field(default="", description="Google Gemini API key")

    # --- Optional keys (filled in later phases) ---
    apify_api_token: str = Field(default="", description="Apify API token")
    tavily_api_key: str = Field(default="", description="Tavily search API key")
    github_token: str = Field(default="", description="GitHub personal access token")

    # --- Cloud (Phase 9) ---
    supabase_url: str = Field(default="", description="Supabase project URL")
    supabase_key: str = Field(default="", description="Supabase anon key")

    # --- Notifications ---
    telegram_bot_token: str = Field(default="", description="Telegram bot token")
    telegram_chat_id: str = Field(default="", description="Telegram chat ID")

    # --- Environment mode ---
    environment: str = Field(default="local", description="local | cloud")

    model_config = {
        "env_file": str(PROJECT_ROOT / ".env"),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


# ---------------------------------------------------------------------------
# Python config loaders (kept for backwards compatibility with ScraperManager)
# ---------------------------------------------------------------------------
def load_search_queries() -> dict:
    """Load search queries and locations from config/search_queries.py."""
    return {
        "search_queries": SEARCH_QUERIES,
        "locations": LOCATIONS
    }


def load_platforms_config() -> dict:
    """Load per-platform scraping settings from config/platforms_config.py."""
    return PLATFORMS_CONFIG


def load_filters_config() -> dict:
    """Load filters and sorting rules from config/filters_and_sorting.py."""
    return {
        "filters": FILTERS,
        "sorting": SORTING
    }


# ---------------------------------------------------------------------------
# Singleton settings instance
# ---------------------------------------------------------------------------
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Returns a cached Settings instance (reads .env once)."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
