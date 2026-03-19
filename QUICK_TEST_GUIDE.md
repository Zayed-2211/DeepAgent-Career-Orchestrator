# Quick Test Guide

## Prerequisites

### 1. Virtual Environment Setup
```powershell
# Create virtual environment (one-time setup)
python -m venv .venv

# Activate virtual environment
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # macOS/Linux

# Install dependencies
pip install -r requirements.txt
```

### 2. Environment Variables
Create a `.env` file in the project root with the following:

```env
# Required API Keys
GEMINI_API_KEY=your-gemini-api-key-here
APIFY_API_TOKEN=your-apify-token-here
TAVILY_API_KEY=your-tavily-key-here

# Optional
GITHUB_TOKEN=your-github-token
```

**Get API Keys:**
- **Gemini**: https://aistudio.google.com/app/apikey
- **Apify**: https://console.apify.com/account/integrations
- **Tavily**: https://tavily.com

### 3. LaTeX Installation (for PDF generation)
- **Windows**: Install [MiKTeX](https://miktex.org/download)
- **macOS**: Install MacTeX
- **Linux**: Install TeX Live

Verify installation:
```powershell
pdflatex --version
```

## Running a Full Dev Test

### Step 1: Activate Virtual Environment
```powershell
.venv\Scripts\activate
```

### Step 2: Set Dev Mode Limit
```powershell
$env:DEV_MODE_LIMIT="5"
```

### Step 3: Run Pipeline
```powershell
python scripts/run_agent.py --pipeline
```

## Expected Output

### Console Output
You should see:
1. **Scout** - Scrapes 5 jobs from LinkedIn
2. **Dedup** - Removes duplicates
3. **Loop** - Processes each job
4. **Intake** - Validates job UIDs
5. **Analysis** - Extracts intelligence with Gemini
6. **Matching** - Finds relevant projects
7. **Review** - Auto-approves jobs
8. **Dispatch** - Saves approved jobs
9. **Research** - Company research (if TAVILY_API_KEY set)
10. **Generator** - Creates CVs and cover letters

### File Outputs

#### Intelligence Data
```
data/intelligence/{date}/
└── parsed_jobs.json  # All analyzed jobs with extracted intelligence
```

#### Generated Documents (for each approved job)
```
data/outputs/{job_uid}/
├── dispatch.json           # Job approval metadata
├── tailored_cv.pdf         # Generated CV (if no errors)
├── tailored_cv.tex         # LaTeX source
├── cover_letter.pdf        # Generated cover letter (if no errors)
├── cover_letter.tex        # LaTeX source
└── research_prep_pack.md   # Company research (if TAVILY_API_KEY set)
```

#### Database
```
data/db/jobs.db
├── raw_jobs          # All scraped jobs
├── processed_jobs    # Jobs that went through pipeline
└── seen_post_ids     # Deduplication tracking
```

## Verifying the Run

### Check Intelligence Files
```powershell
Get-ChildItem data/intelligence -Recurse
```

### Check Generated CVs
```powershell
Get-ChildItem data/outputs -Recurse -Filter "*.pdf"
```

### Check Database
```powershell
# Install sqlite3 if needed
sqlite3 data/db/jobs.db "SELECT COUNT(*) FROM processed_jobs;"
```

### Check Logs
Logs are printed to console. Look for:
- ✓ Success indicators
- ✗ Error indicators
- Progress bars for job processing

## Common Issues

### Issue: "No module named 'google.generativeai'"
**Solution**: Activate the virtual environment
```powershell
.venv\Scripts\activate
pip install google-generativeai
```

### Issue: "GEMINI_API_KEY not set"
**Solution**: Create `.env` file with your API key
```env
GEMINI_API_KEY=your-key-here
```

### Issue: "pdflatex: command not found"
**Solution**: Install LaTeX (MiKTeX for Windows)
- Download: https://miktex.org/download
- Verify: `pdflatex --version`

### Issue: All jobs are duplicates (0 processed)
**Solution**: Clear the database
```powershell
Remove-Item -Path "data/db" -Recurse -Force
```

### Issue: Rate limiting errors
**Solution**: Gemini has rate limits. The system includes 4-second delays between calls. If you hit limits:
- Wait a few minutes
- Reduce `DEV_MODE_LIMIT` to 3 or less

## Current Known Issues

### Schema Validation Error
There's a Pydantic schema validation error with the deprecated `google.generativeai` package:
```
Unknown field for Schema: maxLength
```

**Status**: Being migrated to the new `google.genai` package
**Workaround**: The pipeline completes successfully, but CV generation may fail. Jobs are still approved and dispatch.json files are created.

## Dev Mode Features

### What DEV_MODE_LIMIT Does
- Limits scraping to exactly N jobs
- Uses only 1 search query and 1 location
- Skips CV sync to preserve Gemini quota
- Truncates job queue to N jobs

### Recommended Values
- **Quick test**: `DEV_MODE_LIMIT=3`
- **Full test**: `DEV_MODE_LIMIT=5`
- **Production**: Don't set (processes all jobs)

## Next Steps After Successful Run

1. **Review Outputs**: Check `data/outputs/` for generated files
2. **Inspect Intelligence**: Review `data/intelligence/{date}/parsed_jobs.json`
3. **Verify Database**: Check `data/db/jobs.db` for processed jobs
4. **Adjust Config**: Modify `config/` files for your preferences
5. **Production Run**: Remove `DEV_MODE_LIMIT` for full pipeline

## Performance Metrics

### Expected Timing (DEV_MODE_LIMIT=5)
- **Scout**: ~5-10 seconds
- **Dedup**: ~30-40 seconds (includes Gemini calls for multi-role splitting)
- **Per Job Analysis**: ~10-15 seconds
- **Per Job Matching**: ~2-3 seconds
- **Per Job CV Generation**: ~10-15 seconds (if working)
- **Total**: ~5-7 minutes for 5 jobs

### API Quota Usage (DEV_MODE_LIMIT=5)
- **Gemini Calls**: ~15-25 calls
  - Multi-role splitting: 0-5 calls
  - Intelligence extraction: 5 calls
  - CV tailoring: 5 calls (if working)
  - Cover letter: 5 calls (if enabled)
- **Apify**: 1 scraper run
- **Tavily**: 5 searches (if enabled)

## Support

For issues or questions:
1. Check logs for error messages
2. Review `docs/architecture_deep_dive.md`
3. Check `docs/workflow_visual_guide.md`
4. Review `PRE_RUN_STATUS.md` for setup validation
