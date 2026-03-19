# DeepAgent Career Orchestrator

> **AI-powered job application automation** — Automatically scrape jobs, extract intelligence, match your skills, and generate tailored CVs and cover letters.

[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2+-green.svg)](https://github.com/langchain-ai/langgraph)
[![Gemini](https://img.shields.io/badge/Gemini-2.5--flash-orange.svg)](https://ai.google.dev/)

## 🎯 What It Does

**Complete Job Application Automation Pipeline:**

1. **🔍 Scrapes** jobs from LinkedIn (Glassdoor, Indeed support available)
2. **🔄 Deduplicates** using fingerprints, fuzzy matching, and multi-role splitting
3. **🧠 Extracts Intelligence** using Gemini AI (tech stack, skills, requirements, seniority)
4. **🎯 Matches Projects** from your CV and GitHub (hybrid keyword + vector similarity)
5. **✅ Auto-Reviews** jobs based on match score with configurable thresholds
6. **📄 Generates Tailored CVs** using Gemini + LaTeX for each approved job
7. **✉️ Creates Cover Letters** personalized to the role and company
8. **🔬 Researches Companies** using Tavily API (optional)

**Status: ✅ Production Ready** - All 11 pipeline nodes tested and working

## ✨ Key Features

- **LangGraph Orchestration** - State machine with 11 nodes, conditional routing, and error handling
- **Modern Gemini API** - Uses `langchain_google_genai` with structured output
- **Hybrid Matching** - Keyword overlap + ChromaDB vector similarity for project selection
- **Dev Mode** - Test with limited jobs to preserve API quotas
- **Deduplication Pipeline** - UID-based, fingerprint, and fuzzy dedup with multi-role splitting
- **LaTeX PDF Generation** - Professional CVs and cover letters
- **SQLite Database** - Track all jobs, avoid duplicates, maintain history
- **Rich Console UI** - Beautiful progress bars and status displays

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.13+**
- **LaTeX** (for PDF generation): [MiKTeX](https://miktex.org/download) (Windows) or TeX Live (Linux/macOS)
- **API Keys**:
  - [Gemini API](https://aistudio.google.com/app/apikey) (required)
  - [Apify](https://console.apify.com/account/integrations) (for scraping)
  - [Tavily](https://tavily.com) (optional, for company research)

### 1. Installation

```bash
# Clone repository
git clone https://github.com/Zayed-2211/DeepAgent-Career-Orchestrator.git
cd DeepAgent-Career-Orchestrator

# Create and activate virtual environment
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment

Create a `.env` file in the project root:

```env
# Required
GEMINI_API_KEY=your-gemini-api-key-here
APIFY_API_TOKEN=your-apify-token-here

# Optional
TAVILY_API_KEY=your-tavily-key-here
GITHUB_TOKEN=your-github-token
```

**Get API Keys:**
- **Gemini**: https://aistudio.google.com/app/apikey (Free tier: 20 requests/day)
- **Apify**: https://console.apify.com/account/integrations
- **Tavily**: https://tavily.com (for company research)

**Verify LaTeX Installation:**
```bash
pdflatex --version
```

### 3. Configure Your Profile

**Required Files:**

1. **`data/profile/my_cv.tex`** - Your LaTeX CV template
2. **`data/profile/my_projects.json`** - Your projects (auto-synced from CV/GitHub)
3. **`data/profile/my_github.py`** - GitHub username and repo filters

**Search Configuration:**

4. **`config/search_queries.json`** - Job titles and locations to search
   ```json
   {
     "queries": ["AI Engineer", "Machine Learning Engineer"],
     "locations": ["Egypt", "Remote"]
   }
   ```

5. **`config/platforms.json`** - Enable/disable job platforms
   ```json
   {
     "linkedin": {"enabled": true},
     "glassdoor": {"enabled": false}
   }
   ```

### 4. Run Your First Test

```bash
# Activate virtual environment
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # macOS/Linux

# Set dev mode (limits to 3 jobs to preserve API quota)
$env:DEV_MODE_LIMIT="3"  # Windows PowerShell
export DEV_MODE_LIMIT=3  # macOS/Linux

# Run the full pipeline
python scripts/run_agent.py --pipeline
```

**What Happens:**
1. ✅ Scrapes 3 jobs from LinkedIn
2. ✅ Removes duplicates
3. ✅ Extracts intelligence with Gemini
4. ✅ Matches your projects
5. ✅ Auto-approves jobs (based on match score)
6. ✅ Generates tailored CVs and cover letters
7. ✅ Creates company research (if Tavily API key set)

**Output Locations:**
```
data/
├── intelligence/{date}/
│   └── parsed_jobs.json          # All analyzed jobs
├── outputs/{job_uid}/
│   ├── tailored_cv.pdf           # Generated CV
│   ├── cover_letter.pdf          # Generated cover letter
│   ├── research_prep_pack.md     # Company research
│   └── dispatch.json             # Job metadata
└── db/jobs.db                     # SQLite database
```

📖 **See [QUICK_TEST_GUIDE.md](QUICK_TEST_GUIDE.md) for detailed instructions**
📊 **See [FINAL_TEST_RESULTS.md](FINAL_TEST_RESULTS.md) for test results**

#### CV Generation Testing
**`scripts/test_cv_generation.py`** - Test CV/cover letter generation on already-scraped jobs

```bash
# Test on 2 jobs from already-scraped data
python scripts/test_cv_generation.py --jobs 2

# Skip rate limiting delays (use with caution)
python scripts/test_cv_generation.py --jobs 2 --skip-delay
```

**Features:**
- ✅ Uses already-scraped jobs (no re-scraping)
- ✅ Organized output with progress tracking
- ✅ Detailed summary table
- ✅ Rate limiting built-in (5min before start, 1min between calls)
- ✅ Configurable delays via `config/generators.json`

---

## ⚙️ Configuration

### Editable Prompts

You can customize the AI prompts used for CV and cover letter generation in `config/generators.json`:

```json
{
  "cv_generation": {
    "system_prompt": "You are an expert CV writer...",
    "custom_instructions": "Focus on quantifiable achievements..."
  },
  "cover_letter_generation": {
    "system_prompt": "You are an expert cover letter writer...",
    "custom_instructions": "Show enthusiasm for the role..."
  }
}
```

**Edit `custom_instructions` to add your preferences:**
- Specific writing style
- Industry-specific terminology
- Emphasis on certain skills
- Formatting preferences

### Rate Limiting

Control API call delays in `config/generators.json`:

```json
{
  "rate_limiting": {
    "delay_before_cv_generation_seconds": 300,
    "delay_between_gemini_calls_seconds": 60,
    "enabled": true
  }
}
```

**Why delays?**
- Gemini free tier: 20 requests/day
- Prevents quota exhaustion
- Allows multiple jobs to be processed

---

### 🤖 Pipeline Runners

#### Full Pipeline
**`scripts/run_agent.py`** - Complete pipeline from scraping to CV generation

```bash
# ✅ RECOMMENDED: Dev mode with 3 jobs (preserves API quota)
python scripts/run_agent.py --pipeline --dev 3

# Full production run (scrapes all enabled platforms)
python scripts/run_agent.py --pipeline

# Custom dev limit
python scripts/run_agent.py --pipeline --dev 10

# Custom thread ID for checkpointing
python scripts/run_agent.py --pipeline --thread-id daily-run-2026-03-18
```

**What it does:**
1. Scrapes jobs from enabled platforms
2. Deduplicates using fingerprints + fuzzy matching
3. Extracts intelligence with Gemini AI
4. Matches your projects (keyword + vector search)
5. Reviews each job (auto-approve in unattended mode)
6. Creates dispatch files for approved jobs

**Output files:**
- `data/intelligence/{date}/agent_run_{timestamp}_{thread_id}.json` - Per-run jobs
- `data/intelligence/{date}/parsed_jobs.json` - Daily aggregated
- `data/intelligence/{date}/run_status.json` - Pipeline stats
- `data/intelligence/{date}/run_log.txt` - Timestamped events
- `data/outputs/{job_uid}/dispatch.json` - Approved job details

---

### 🔍 Profile Indexer

**`scripts/run_indexer.py`** - Build ChromaDB vector index (Phase 5)

```bash
# Index GitHub repos + manual projects
python scripts/run_indexer.py

# Clear and rebuild index
python scripts/run_indexer.py --rebuild

# Only index GitHub repos (skip my_projects.json)
python scripts/run_indexer.py --github-only
```

**What it does:**
- Clones/pulls your GitHub repositories
- Extracts README, tech stack, and domains
- Indexes into ChromaDB for semantic search
- Combines with manual projects from `my_projects.json`

**When to run:**
- After adding new GitHub repos
- After updating `my_projects.json`
- When match scores are low (improves semantic matching)

---

### 📝 CV Project Sync

**`scripts/sync_cv_projects.py`** - Extract projects from LaTeX CV (Phase 5)

```bash
# Sync non-GitHub projects from CV to my_projects.json
python scripts/sync_cv_projects.py

# Preview changes without writing
python scripts/sync_cv_projects.py --dry-run

# Force re-extraction even if no changes
python scripts/sync_cv_projects.py --force
```

**What it does:**
- Parses `data/profile/my_cv.tex` using Gemini
- Extracts project name, description, tech stack, highlights
- Skips projects with real GitHub URLs (handled by indexer)
- Avoids duplicates in `my_projects.json`

**Note:** Automatically runs before pipeline (skipped in dev mode to save quota)

---

### 🔧 Individual Phase Runners

**For manual phase-by-phase execution:**

#### 1. Generate Keywords (Phase 2)

```bash
# Generate LinkedIn post search keywords
python scripts/generate_keywords.py

# Force regeneration
python scripts/generate_keywords.py --force

# Preview without saving
python scripts/generate_keywords.py --preview
```

#### 2. Run Scrapers (Phase 1 & 2)

```bash
# All enabled platforms
python scripts/run_scraper.py

# Single platform
python scripts/run_scraper.py --platform linkedin
python scripts/run_scraper.py --platform linkedin_posts

# Override search query
python scripts/run_scraper.py --platform linkedin --query "AI Engineer"
```

#### 3. Run Deduplication (Phase 3)

```bash
# Auto-detect latest raw folder
python scripts/run_dedup.py

# Specific input folder
python scripts/run_dedup.py --input data/raw/2026-03-18

# Custom output location
python scripts/run_dedup.py --output data/processed/custom

# Stricter fuzzy threshold (default 0.75)
python scripts/run_dedup.py --fuzzy-threshold 0.85

# Preview changes only
python scripts/run_dedup.py --dry-run
```

#### 4. Run Intelligence Extraction (Phase 4)

```bash
# Auto-detect latest processed file
python scripts/run_intelligence.py

# Specific input file
python scripts/run_intelligence.py --input data/processed/2026-03-18/deduped_jobs.json

# Limit number of jobs (for testing)
python scripts/run_intelligence.py --limit 5

# Custom output directory
python scripts/run_intelligence.py --output data/intelligence/test_run
```

#### 5. Run Agent on Existing File (Phase 6)

```bash
# Process first job in file
python scripts/run_agent.py --job-file data/intelligence/2026-03-18/parsed_jobs.json

# Process specific job by index (0-based)
python scripts/run_agent.py --job-file data/intelligence/2026-03-18/parsed_jobs.json --index 2

# Process all jobs in file
python scripts/run_agent.py --job-file data/intelligence/2026-03-18/parsed_jobs.json --all
```

---

## 🔄 Common Workflows

### Daily Production Run

```bash
# Full automated pipeline
python scripts/run_agent.py --pipeline
```

### Quick Testing (Recommended)

```bash
# Test with 5 jobs only
python scripts/run_agent.py --pipeline --dev 5
```

### Manual Phase-by-Phase

```bash
# 1. Generate keywords for LinkedIn posts
python scripts/generate_keywords.py

# 2. Scrape all platforms
python scripts/run_scraper.py

# 3. Deduplicate
python scripts/run_dedup.py

# 4. Extract intelligence (limit for testing)
python scripts/run_intelligence.py --limit 10

# 5. Run agent on extracted jobs
python scripts/run_agent.py --job-file data/intelligence/2026-03-18/parsed_jobs.json --all
```

### Update Profile Index

```bash
# 1. Sync CV projects
python scripts/sync_cv_projects.py

# 2. Index GitHub repos + projects
python scripts/run_indexer.py --rebuild

# 3. Test matching with dev run
python scripts/run_agent.py --pipeline --dev 5
```

---

## 📂 Output Structure

```
data/
├── raw/                          # Phase 1 & 2: Raw scraped data
│   └── {date}/
│       ├── linkedin_{timestamp}.json
│       └── linkedin_posts_{timestamp}.json
│
├── processed/                    # Phase 3: Deduplicated data
│   └── {date}/
│       └── deduped_jobs.json
│
├── intelligence/                 # Phase 4-6: Analyzed jobs
│   └── {date}/
│       ├── agent_run_{time}_{thread}.json  # Per-run jobs
│       ├── parsed_jobs.json                # Daily aggregated
│       ├── run_status.json                 # Pipeline stats
│       └── run_log.txt                     # Event log
│
├── outputs/                      # Phase 6: Approved jobs
│   └── {job_uid}/
│       ├── dispatch.json         # Approved job details
│       └── archived.json         # Rejected job details
│
├── profile/                      # Phase 5: Your profile
│   ├── my_cv.tex                 # Your LaTeX CV
│   ├── my_projects.json          # Manual + CV projects
│   ├── my_github.py              # GitHub config
│   ├── vector_index/             # ChromaDB index
│   └── .github_cache/            # Cloned repos
│
└── db/
    └── jobs.db                   # SQLite dedup database
```

---

## 🧪 Testing

```bash
# Run all tests
python -m pytest tests/ -v

# Test specific module
python -m pytest tests/agent/ -v

# Test specific pattern
python -m pytest tests/agent/ -v -k "loop"

# Test with coverage
python -m pytest tests/ --cov=src --cov-report=html
```

---

## 🛠️ Troubleshooting

### Gemini Quota Exhausted

**Error:** `429 RESOURCE_EXHAUSTED`

**Solution:**
- Use `--dev 5` mode to limit API calls
- Wait 60 seconds between runs
- Free tier: 15 requests/minute, 1500/day

### No Jobs Scraped

**Check:**
1. `APIFY_API_TOKEN` is set in `.env`
2. Platforms are enabled in `config/platforms.json`
3. Queries exist in `config/search_queries.json`

### All Jobs Skipped (Duplicates)

**Solution:**
```bash
# Clear database to allow re-processing
Remove-Item data/db/jobs.db -Force  # Windows
rm data/db/jobs.db                  # macOS/Linux

# Run again
python scripts/run_agent.py --pipeline --dev 5
```

### Low Match Scores

**Solution:**
```bash
# 1. Index your GitHub repos
python scripts/run_indexer.py --rebuild

# 2. Update my_projects.json with detailed descriptions
# 3. Re-run pipeline
python scripts/run_agent.py --pipeline --dev 5
```

---

## 📖 Documentation

### Quick Guides
- **[Quick Test Guide](QUICK_TEST_GUIDE.md)** - Step-by-step testing instructions
- **[Final Test Results](FINAL_TEST_RESULTS.md)** - Latest test results and verification
- **[Session Summary](SESSION_SUMMARY.md)** - Recent development session details

### Architecture & Workflow
- **[Architecture Deep Dive](docs/architecture_deep_dive.md)** - Complete system architecture
- **[Workflow Visual Guide](docs/workflow_visual_guide.md)** - Node-by-node execution flow
- **[Output Structure](docs/output_structure.md)** - Where to find generated files
- **[Workflow Validation](docs/workflow_validation.md)** - Pipeline validation checklist

### Enhancement Plans
- **[Professional Enhancements](docs/professional_enhancements.md)** - Production improvements
- **[Advanced Enhancements Research](docs/advanced_enhancements_research.md)** - Phase 1-3 roadmap

---

## 🎯 Project Status

| Phase | Status | Description |
|-------|--------|-------------|
| **0** | ✅ Complete | Project setup, config, dependencies |
| **1** | ✅ Complete | Job board scraping (LinkedIn, Glassdoor, Indeed) |
| **2** | ✅ Complete | LinkedIn post scraping with AI keywords |
| **3** | ✅ Complete | Deduplication (fingerprints, fuzzy, multi-role) |
| **4** | ✅ Complete | Intelligence extraction (Gemini structured output) |
| **5** | ✅ Complete | Profile indexing (ChromaDB + GitHub parser) |
| **6** | ✅ Complete | LangGraph agent core |
| **6.5** | ✅ Complete | Full pipeline integration |
| **7** | ✅ Complete | LaTeX CV & cover letter generation |
| **8** | ✅ Complete | Company research (Tavily + Glassdoor) |
| **Phase 1** | 🔄 Next | Adaptive rate limiting, retry, circuit breaker, caching |
| **9** | ⏳ Planned | Cloud deployment (Azure) |

## 🆕 Recent Improvements (March 2026)

### API Migration
- ✅ Migrated from deprecated `google.generativeai` to modern `langchain_google_genai`
- ✅ All generators now use `ChatGoogleGenerativeAI` with `.with_structured_output()`
- ✅ Consistent API pattern across all Gemini integrations

### Bug Fixes
- ✅ Fixed Pydantic schema validation (`max_length` → `max_items` for lists)
- ✅ Fixed Windows file path bug (sanitize `:` in job_uid)
- ✅ Increased schema limits to realistic values (500 chars for summary)

### Code Quality
- ✅ Improved logging with ✓/✗/→ symbols
- ✅ Added detailed metrics in log messages
- ✅ Moved verbose logs to DEBUG level
- ✅ Better error messages with context

### Infrastructure
- ✅ Clean `.venv` virtual environment setup
- ✅ Removed old `.career-env` venv
- ✅ Updated all documentation
- ✅ Full end-to-end testing verified

---

## � Comprehensive Documentation

### Core Documentation

**📖 [Architecture Deep Dive](docs/architecture_deep_dive.md)**
- Complete system architecture
- Technology stack breakdown
- LangGraph vs non-LangGraph components
- Data flow through all phases
- Database architecture
- **Answers:** "How does everything work? What's used for each part?"

**🔄 [Workflow Visual Guide](docs/workflow_visual_guide.md)**
- Full pipeline execution flow (node-by-node)
- LangGraph state flow with visual diagrams
- Dev mode execution details
- Error handling & recovery
- **Answers:** "What's the complete workflow? Where does LangGraph fit?"

**📁 [Output Structure](docs/output_structure.md)**
- Where ALL files are saved
- Per-job output organization
- **How to find your generated CVs** ⭐
- Database files explained
- Profile data locations
- **Answers:** "Where are my generated CVs? Where is everything saved?"

**🚀 [Professional Enhancements](docs/professional_enhancements.md)**
- Recommendations for production-grade system
- Code quality improvements
- Architecture enhancements
- Advanced features roadmap
- Testing strategy
- **Answers:** "How to make this enterprise-level?"

### Implementation Documentation

**📋 [Phase 7 & 8 Implementation](docs/phase7_8_implementation.md)**
- LaTeX CV & cover letter generation
- Company research with Tavily
- Configuration examples
- Testing instructions

**🗺️ [Roadmap Documentation](docs/)**
- Part 1: Setup & Scraping
- Part 2: Data Processing
- Part 3: Profile & Agent
- Part 4: Output & Cloud

---

## �� License

MIT License - See LICENSE file for details
