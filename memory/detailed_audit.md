# Detailed Project Audit & Bug Report

**Date:** 2026-03-25  
**Status:** Analysis Complete  
**Scope:** Full Codebase (~60 files)

---

## 🔴 Critical Bugs (Runtime Failures)

### 1. Data Access Mismatches (Widespread)
The pipeline extracts highly structured data using `JobParser` (Phase 4), but downstream nodes still use old key names from raw records.
- **Problem:** After `analysis_node`, the company name is in `scout.company_name`. However, `research_node`, `generator_node`, `cv_tailor`, and `prep_pack_builder` all look for `job.get("company")`.
- **Impact:** Every per-job node except the first few will receive `None` for company name, job title, and required skills.

### 2. Generator Field Name Inconsistency
- **Problem:** `cv_tailor.py` and `cover_letter_gen.py` look for `required_skills`, `preferred_skills`, and `responsibilities` in the intelligence dict.
- **Schema:** The actual `IntelligenceData` schema uses `must_haves`, `nice_to_haves`, and `role_summary`.
- **Impact:** LLM prompts for CV/CL generation will be missing the core job requirements, leading to generic, untailored output.

### 3. Hardcoded Placeholder Profile Data
- **Problem:** `generator_node.py` contains a `_load_user_profile` function that returns hardcoded "Your Name", "your.email@example.com", and placeholder experiences.
- **Impact:** Even if the user has a perfect LaTeX CV and `my_projects.json`, the generated CVs will contain dummy data.

### 4. Invalid Model String
- **Problem:** `src/research/glassdoor_researcher.py` (Line 75) and `_default_config` (Line 113) use `gemini-2.5-flash`.
- **Context:** Gemini 2.5 does not exist. This will likely cause a 404/Invalid Model error at runtime. Should be `gemini-1.5-flash` or `gemini-2.0-flash`.

---

## 🟡 Architectural Inconsistencies

### 1. Local Config Loading (Bypassing AppConfig)
- **Problem:** Multiple modules (`JobParser`, `CVTailor`, `LaTeXEngine`, `GlassdoorResearcher`, etc.) implement their own `_load_config` functions.
- **Impact:** Centralized settings in `AppConfig` are ignored. Changing a setting in one place won't affect these modules.

### 2. Redundant Prompt Templates
- **Problem:** `src/intelligence/job_parser.py` has a massive hardcoded prompt, while `config/prompts.py` also exists.
- **Impact:** Maintenance nightmare. Updates to prompts are likely to be missed in one of the locations.

### 3. Hardcoded Platform Configuration
- **Problem:** `src/scrapers/scraper_manager.py` hardcodes the mapping of platforms to scraper classes.
- **Impact:** Adding a new scraper (e.g. Facebook) requires modifying the core manager instead of being a pluggable registration.

---

## ⚪ Dead Code & Redundancies

1. **`src/generators/schemas.py`**: `CoverLetterSection` model is defined but never used.
2. **`config/settings.py`**: `ApifyConfig` class is defined but `AppConfig` just loads the token directly.
3. **`src/scrapers/keyword_generator.py`**: Contains its own `_MODELS` list instead of using `config/models_config.py`.
4. **`src/agent/intelligence_artifacts.py`**: Contains complex logging logic that overlaps with what LangGraph already tracks in state checkpoints.

---

## 🟢 Recommendations

1. **Unify Data Schema:** Standardize on `scout` and `intelligence` sub-objects across the entire pipeline.
2. **Centralize Config:** Refactor all `_load_config` calls to use `get_settings()` and move all JSON defaults to `config/schemas.py`.
3. **Profile Sync:** Fix `generator_node` to actually load the user's analyzed profile data from `my_projects.json` and the CV extraction results.
4. **Security Hardening:** Implement real path validation in `disk_tool.py` to prevent directory traversal.
5. **Prompt Consolidation:** Move the `JobParser` prompt into `config/prompts.py`.
