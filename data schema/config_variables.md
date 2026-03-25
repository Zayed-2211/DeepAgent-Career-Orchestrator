# Configuration Variables

> Sources: `config/settings.py`, `.env`, `config/*.py`, `config/*.json`

## Environment Variables (`.env`)

| Variable | Type | Required | Used By |
|----------|------|----------|---------|
| `gemini_api_key` | str | ✓ | `JobParser`, `CVTailor`, `CoverLetterGenerator` |
| `apify_api_token` | str | For LinkedIn posts | `LinkedInPostScraper` |
| `tavily_api_key` | str | For research | `WebSearcher` |
| `AGENT_INTELLIGENCE_RUN_STATUS` | str | ✗ | `intelligence_artifacts.py` (path override for run status JSON) |
| `AGENT_INTELLIGENCE_RUN_LOG` | str | ✗ | `intelligence_artifacts.py` (path override for run log) |
| `AGENT_INTELLIGENCE_LATEST_URL` | str | ✗ | `intelligence_artifacts.py` (latest artifacts URL) |
| `DEV_MODE_LIMIT` | str | ✗ | `ScraperManager`, `run_agent.py` (dev mode budget) |
| `MOCK_SCRAPER` | str | ✗ | `run_agent.py` (testing — disabled in pipeline mode) |
| `MOCK_SCRAPER_FILE` | str | ✗ | `run_agent.py` (testing — disabled in pipeline mode) |
| `DEV_FORCE_RESCRAPE` | str | ✗ | `run_agent.py` (testing — disabled in pipeline mode) |

## AppConfig (`config/settings.py`)

Aggregates all configs via `get_settings()`:

| Property | Source | Description |
|----------|--------|-------------|
| `gemini_api_key` | `.env` | Gemini API key |
| `apify_api_token` | `.env` | Apify API token |
| `tavily_api_key` | `.env` | Tavily search API key |
| `search_queries` | `search_queries.py` | Search queries + locations |
| `platforms_config` | `platforms_config.py` | Enabled platforms + params |
| `filters_config` | `filters_and_sorting.py` | Filters + sorting rules |
| `models_config` | `models_config.py` | LLM model IDs |
| `prompts` | `prompts.py` | All LLM prompt templates |
| `projects_config` | `projects_config.py` | CV/profile settings |
| `generators_config` | `generators.json` | Generation parameters |
| `research_config` | `research.json` | Research settings |

## Key Config Files

| File | Format | Purpose |
|------|--------|---------|
| `config/models_config.py` | Python | LLM model IDs per phase |
| `config/prompts.py` | Python | All centralized prompt templates |
| `config/constants.py` | Python | Enums: Platform, PostingType, SortBy, etc. |
| `config/search_queries.py` | Python | Search queries and location maps |
| `config/platforms_config.py` | Python | Per-platform scraping params |
| `config/filters_and_sorting.py` | Python | Post-scraping filters |
| `config/projects_config.py` | Python | Profile/CV settings |
| `config/schemas.py` | Python | Pydantic models for JSON configs |
| `config/generators.json` | JSON | Generator params (model, temperature, rate limiting) |
| `config/research.json` | JSON | Research toggle + Glassdoor/LinkedIn settings |

## Directory Constants

| Constant | Value | Defined In |
|----------|-------|------------|
| `DATA_DIR` | `{project_root}/data` | `config/settings.py` |
| `CONFIG_DIR` | `{project_root}/config` | `config/settings.py` |
| `MANUAL_PROJECTS_FILE` | `data/profile/my_projects.json` | `config/projects_config.py` |
