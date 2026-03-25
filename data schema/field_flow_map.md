# Field Flow Map — Where Data Breaks

This document traces how key fields flow between nodes and **where inconsistencies exist**.

## Company Name Flow

```
scout_node → raw record has `company` field
  ↓
dedup_node → passes through
  ↓
intake_node → reads raw record
  ↓
analysis_node → JobParser puts company in `scout.company_name`
  ↓
matching_node → reads `current_job` (uses `intelligence` sub-dict)
  ↓
review_node → reads `scout.company_name` ✓ (line 39)
  ↓
dispatch_node → reads `scout.company_name` ✓
  ↓
research_node → reads `current_job.get("company")` ✗ BUG — should be `scout.company_name`
  ↓
generator_node → reads `current_job.get("company")` ✗ BUG — should be `scout.company_name`
  ↓
cv_tailor → reads `job.get("company")` ✗ BUG — same issue
  ↓
cover_letter_gen → reads `job.get("company")` ✗ BUG — same issue
```

> **⚠️ CRITICAL**: After analysis_node, the company name lives at `current_job["scout"]["company_name"]`, NOT at `current_job["company"]`. The research_node, generator_node, cv_tailor, and cover_letter_gen all read the wrong field and will get `None`.

## Intelligence Fields Flow

```
analysis_node → JobParser returns ParsedJob with scout + intelligence
  intelligence has: must_haves, nice_to_haves, tech_stack, technical_skills
  ↓
cv_tailor._build_prompt() → reads:
  - `intelligence.get("required_skills")` ✗ WRONG — should be `must_haves`
  - `intelligence.get("preferred_skills")` ✗ WRONG — should be `nice_to_haves`
  - `intelligence.get("responsibilities")` ✗ WRONG — field doesn't exist
  ↓
cover_letter_gen._build_prompt() → same wrong field names
```

> **⚠️ CRITICAL**: The generators use field names that don't exist in the schema. `required_skills`, `preferred_skills`, and `responsibilities` are NOT fields in `IntelligenceData`. The correct fields are `must_haves`, `nice_to_haves`, and `role_summary`.

## User Profile Flow

```
generator_node._load_user_profile() → Returns hardcoded placeholder data:
  - name: "Your Name"
  - email: "your.email@example.com"
  - experience: [{"company": "Previous Company", ...}]
```

> **⚠️ CRITICAL**: The profile loader returns placeholder/dummy data even when `my_projects.json` exists. It only extracts `tech_stack` from projects but fills everything else with fake data. This means **every generated CV and cover letter has placeholder personal info**.

## Job Record Structure (current_job)

After `analysis_node`, `current_job` is a `ParsedJob.model_dump()` dict with:

```python
{
    "job_uid": "...",
    "raw_title": "...",     # ← title is here, NOT at "title"
    "source_url": "...",    # ← URL is here
    "scout": {
        "company_name": "...",  # ← company is HERE
        "city": "...",
        "is_remote": True/False/None,
        ...
    },
    "intelligence": {
        "tech_stack": [...],
        "must_haves": [...],   # ← NOT "required_skills"
        "nice_to_haves": [...], # ← NOT "preferred_skills"
        ...
    }
}
```

But downstream code (generator_node, cv_tailor, cover_letter_gen) reads:
- `job.get("title")` — should be `raw_title`
- `job.get("company")` — should be `scout.company_name`
- `intelligence.get("required_skills")` — should be `must_haves`
- `intelligence.get("preferred_skills")` — should be `nice_to_haves`
