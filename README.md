# 🤖 DeepAgent Career Orchestrator

An AI-powered career agent that **automatically scrapes** job listings, **intelligently parses** them, **matches** them against your profile, and **generates tailored CVs & cover letters** — all orchestrated by a LangGraph agent with human-in-the-loop approval.

---

## ✨ What It Does

1. **Scrapes jobs** from LinkedIn, Glassdoor, and organic LinkedIn posts (via Apify)
2. **Deduplicates & cleans** raw listings — splits multi-role posts, extracts contact info
3. **Parses with AI** — uses Gemini to extract structured data (skills, salary, experience, etc.)
4. **Matches against your profile** — indexes your GitHub projects + CV into a vector store (ChromaDB)
5. **Asks for your approval** — presents match scores and a plan before acting
6. **Generates tailored documents** — LaTeX CVs and cover letters customized per job
7. **Researches companies** — Glassdoor reviews, community sentiment, interview prep packs
8. **Syncs to cloud** — all data backed up to Supabase for future analysis

---

## 🚀 Quick Start

### 1. Clone & Enter

```bash
git clone https://github.com/YOUR_USERNAME/DeepAgent-Career-Orchestrator.git
cd DeepAgent-Career-Orchestrator
```

### 2. Create Virtual Environment

```bash
python -m venv .career-env

# Windows
.career-env\Scripts\activate

# macOS / Linux
source .career-env/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

> **Tip:** You don't need all dependencies right away. Install only what the current phase needs. See the [roadmap](docs/roadmap_part1_setup_and_scraping.md) for per-phase instructions.

### 4. Configure Environment

```bash
copy .env.example .env        # Windows
# cp .env.example .env        # macOS / Linux
```

Open `.env` and fill in your API keys:

| Variable | Required | Where to Get It |
|----------|----------|-----------------|
| `GEMINI_API_KEY` | ✅ Yes | [aistudio.google.com](https://aistudio.google.com/) |
| `APIFY_API_TOKEN` | Phase 2+ | [apify.com](https://apify.com) → Settings → Integrations |
| `TAVILY_API_KEY` | Phase 8+ | [tavily.com](https://tavily.com) |
| `SUPABASE_URL` | Phase 9+ | [supabase.com](https://supabase.com) → Project Settings → API |
| `SUPABASE_KEY` | Phase 9+ | Same as above |

> **Note:** No GitHub token is needed. Public GitHub repos are fetched via the unauthenticated public API (60 req/hour limit — sufficient for profile indexing).

---

## 📁 Project Structure

```
DeepAgent-Career-Orchestrator/
├── config/                    # Configuration files (all .py with detailed comments)
│   ├── settings.py            # Central config loader (reads .env)
│   ├── constants.py           # Shared enums and constants
│   ├── search_queries.py      # 🔍 Job search queries, locations, geo IDs, post keywords
│   ├── platforms_config.py    # Per-platform scraping settings
│   ├── filters_and_sorting.py # Post-scrape filtering rules & sort order
│   └── projects_config.py     # CV/index behavior settings, template toggle
│
├── src/                       # Application source code
│   ├── scrapers/              # Phase 1 & 2 — Job scraping engines
│   ├── dedup/                 # Phase 3 — Deduplication & cleaning
│   ├── db/                    # Shared database layer (SQLite)
│   ├── intelligence/          # Phase 4 — AI-powered parsing
│   ├── profile/               # Phase 5 — RAG & profile builder
│   ├── agent/                 # Phase 6 — LangGraph agent core
│   ├── generators/            # Phase 7 — LaTeX CV & cover letter generation
│   ├── research/              # Phase 8 — Company research sub-agents
│   ├── notifications/         # Phase 9 — Email & Telegram alerts
│   └── cloud/                 # Phase 9 — Supabase cloud sync
│
├── data/                      # Runtime data (gitignored)
│   ├── raw/                   # Raw scraped results
│   ├── processed/             # Cleaned & parsed jobs
│   ├── cache/                 # Cached LLM outputs (keyword generation)
│   │   └── keywords/          # Per-config keyword cache files
│   ├── outputs/               # Generated CVs, cover letters, prep packs
│   ├── profiles/              # Your profile snapshots
│   ├── db/                    # Local SQLite database
│   ├── intelligence/          # Phase 4 parsed AI output (per-day folders)
│   │   └── {date}/
│   │       ├── run_*.json         # Per-run output (written incrementally)
│   │       ├── parsed_jobs.json   # Merged daily view (rebuilt each run)
│   │       ├── run_status.json    # Live progress (overwritten per record)
│   │       └── run_log.txt        # Append-only run log
│   └── profile/               # Phase 5 profile data (gitignored)
│       ├── my_cv.tex              # ← Your LaTeX CV
│       ├── my_github.py           # ← GitHub URL + include/exclude lists
│       ├── my_projects.json       # ← Manual projects (not on GitHub)
│       └── vector_index/          # ChromaDB profile index (auto-generated)
│
├── data/profile.example/      # Starter files — rename folder to profile/ to use
│   ├── my_cv.tex              # CV placeholder
│   ├── my_github.py           # GitHub settings placeholder
│   ├── my_projects.json       # Manual projects placeholder
│   └── README.md              # Setup instructions
│
├── templates/                 # Project templates (committed)
│   └── cv_template.tex        # Default ATS-friendly LaTeX CV (fallback)
│
├── tests/                     # Test suite (mirrors src/ structure)
├── scripts/                   # CLI entry points for each phase
│
├── .env.example               # Environment variable template
├── .gitignore                 # Git ignore rules
├── requirements.txt           # Python dependencies
├── LICENSE                    # Project license
└── README.md                  # This file
```

---

## 🔍 Search Queries (`config/search_queries.py`)

This file is the **single source of truth** for what the scraper searches for and where. All scrapers read from it. Edit anytime — no code changes needed.

```python
# Job titles — used by job board scraper (Phase 1) AND to generate
# LLM-powered boolean keywords for LinkedIn post scraper (Phase 2)
SEARCH_QUERIES = [
    "AI Engineer",
    "Machine Learning Engineer",
    "Generative AI Engineer",
]

# Locations — shared by ALL scrapers
LOCATIONS = ["Egypt", "Cairo, Egypt"]

# LinkedIn geo IDs for post scraper
LINKEDIN_GEO_IDS = {"Egypt": "101620260", "Cairo, Egypt": "100640489"}
```

**How to update:**
- Open `config/search_queries.py` in any text editor
- Add new job titles to `SEARCH_QUERIES`
- Change locations in `LOCATIONS` (affects all scrapers at once)
- Changing titles or locations **auto-invalidates** the keyword cache — next scrape run calls Gemini to regenerate boolean keywords

**`job_uid` — Post Unique ID:**
Every LinkedIn post record contains a `job_uid` field — the LinkedIn activity ID extracted from the post URL (e.g., `7434578207858769920`). This is the **DB primary key** and guarantees no post is ever stored twice, even across multiple scrape runs.

**Smart Time Window:**
The scraper automatically switches between `past-week` and `past-24h` based on when it last ran:
- **First run / last run > 48h ago** → uses `past-week` (7 days of posts, best coverage)
- **Last run < 48h ago** → switches to `past-24h` (only fresh posts, saves Apify credits)
- Control this behavior with `smart_time_window_hours` in `config/platforms_config.py` (set to `0` to always use `hours_old`)

---

## 👤 Profile Setup

Before running Phase 5+, fill in three files in `data/profile/` (gitignored — stays private):

### `data/profile/my_cv.tex` — Your LaTeX CV
Paste your full LaTeX CV here. Phase 7 reads it as the base template and generates a tailored copy per job. Your original is never overwritten.

Generated output per job: `data/outputs/{job_uid}/cv_tailored.tex` + `.pdf`

> If this file is missing, the default `cv_template.tex` is used automatically.

**Auto-sync projects from CV:** After filling in your CV, run:
```bash
python scripts/sync_cv_projects.py
```
This reads your CV's Projects section and automatically appends any non-GitHub projects to `my_projects.json`. Projects already listed there and projects with a GitHub URL are safely skipped.

### `data/profile/my_github.py` — GitHub Settings
Controls which of your public repos get indexed (no token needed):

```python
GITHUB_URL = "https://github.com/YOUR_USERNAME"  # public API, no token

# Option A — Whitelist: only these repos (checked first)
INCLUDE_REPOS = ["my-rag-chatbot", "my-api"]

# Option B — Blacklist: all repos EXCEPT these (if INCLUDE is empty)
EXCLUDE_REPOS = ["old-uni-project", "test-repo"]

# Option C — Both empty → use ALL public repos
```

### `data/profile/my_projects.json` — Manual Projects
For projects not on GitHub (or projects you want to describe yourself):

```json
{
  "name": "My Project",
  "description": "What it does",
  "tech_stack": ["Python", "FastAPI"],
  "highlights": ["Built X doing Y", "Reduced Z by 40%"],
  "github_url": null,
  "period": "Jan 2025 - Mar 2025"
}
```

### CV Template Toggle (`config/projects_config.py`)

```python
# False (default) — use my_cv.tex; falls back to cv_template.tex if missing
# True            — always use the built-in template (good for testing)
USE_DEFAULT_CV_TEMPLATE: bool = False
```

The default template lives at `templates/cv_template.tex` (committed to the repo — always available).

To get started, rename `data/profile.example/` → `data/profile/` — files are already named correctly, no further renaming needed.

---

## 🛠 CLI Scripts

Each phase has a standalone CLI script in `scripts/` for testing and debugging:

```bash
# Scrape job listings
python scripts/run_scraper.py --platform linkedin_jobs --query "AI Engineer"

# Scrape LinkedIn posts (uses LLM-generated boolean keywords)
python scripts/run_scraper.py --platform linkedin_posts

# Generate/preview LLM boolean keywords for LinkedIn post search
python scripts/generate_keywords.py           # Generate (skip if cached)
python scripts/generate_keywords.py --force   # Regenerate (ignore cache)
python scripts/generate_keywords.py --preview # Dry run (print without saving)

# Run deduplication on raw data
python scripts/run_dedup.py --input data/raw/ --output data/processed/

# Run Phase 4 intelligence extraction
python scripts/run_intelligence.py            # Process most recent processed file
python scripts/run_intelligence.py --limit 5  # Test with only 5 new records

# Sync non-GitHub projects from your CV to my_projects.json
python scripts/sync_cv_projects.py           # Normal run
python scripts/sync_cv_projects.py --dry-run  # Preview only (no file written)
python scripts/sync_cv_projects.py --force    # Bypass duplicate check

# Phase 5 — Rebuild the profile vector index
# (reads data/profile/my_cv.tex + my_projects.json + GitHub repos)
python scripts/run_indexer.py --rebuild

# Run the full agent pipeline for a specific job
python scripts/run_agent.py --job data/processed/job_xyz.json
```

---

## 📚 Documentation

The implementation roadmap is split into 4 parts for easier reading:

| Doc | Covers |
|-----|--------|
| [Part 1 — Setup & Scraping](docs/roadmap_part1_setup_and_scraping.md) | Phase 0, 1, 2 + master file tree |
| [Part 2 — Data Processing](docs/roadmap_part2_data_processing.md) | Phase 3, 4 |
| [Part 3 — Profile & Agent](docs/roadmap_part3_profile_and_agent.md) | Phase 5, 6 |
| [Part 4 — Output & Cloud](docs/roadmap_part4_output_and_cloud.md) | Phase 7, 8, 9 + full deps list |
| [Migration Guide](docs/migration_to_full_cloud.md) | Upgrading to Azure (Option C) |
| [Tools Explained](docs/tools_and_concepts_explained.md) | Every tool & concept in simple words |

---

## ☁️ Cloud Strategy

**Current approach (Option B):** Code runs on your machine. Data syncs to [Supabase](https://supabase.com) (free tier) for backup and future analysis.

**Later (Option C):** Full Azure migration — code runs 24/7 in the cloud. See the [migration guide](docs/migration_to_full_cloud.md).

---

## 💰 Cost

| Service | Monthly Cost |
|---------|-------------|
| Gemini Flash (`gemini-2.5-flash` / `gemini-3.1-flash-lite-preview`) | **Free** (within free tier) |
| Apify (LinkedIn scraping) | **Free** ($5 free credits/month) |
| Tavily (web search) | **Free** (1000 searches/month) |
| Supabase (cloud storage) | **Free** (500 MB DB + 1 GB storage) |
| **Total (Phases 1-9)** | **$0** |

> ⚠️ **Gemini model reminder:** Always use models confirmed via `client.models.list()`. Current approved models: `gemini-2.5-flash` (primary), `gemini-3.1-flash-lite-preview` (fallback). Never hardcode model names from memory — they deprecate without notice.

---

## ✅ Current Status

| Phase | Status | Description |
|-------|--------|-------------|
| **Phase 0** | ✅ Done | Project setup, folder structure, config files |
| **Phase 1** | ✅ Done | LinkedIn job board scraper (Apify) |
| **Phase 2** | ✅ Done | LinkedIn post scraper + Gemini-powered keyword generation (Arabic + English, geo-filtered, smart time window) |
| **Phase 3** | ✅ Done | Dedup, multi-role splitting, contact extraction, LLM-based near-duplicate detection |
| **Phase 4** | ✅ Done | Intelligence extraction: Gemini parses skills, salary, exp, seniority. UID pre-filtering. Incremental writes. Crash recovery. |
| **Phase 5** | 🟡 Config ready | Profile setup files created: `my_cv.tex`, `my_github.py`, `my_projects.json`. Indexer (ChromaDB) not yet built. |
| **Phase 6** | 🔜 Coming | LangGraph matching agent — scores jobs vs. your profile, asks approval |
| **Phase 7** | 🔜 Coming | LaTeX CV + cover letter generator (tailored per job) |
| **Phase 8+** | 🔜 Coming | Company research, Telegram alerts, Supabase cloud sync |

---

## 📝 License

See [LICENSE](LICENSE) for details.
