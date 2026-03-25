# Pending Tasks (Technical Debt & Features)

## 🛠️ High Priority (Bug Fixes)
- [ ] **Standardize Field Access:** Update `research_node`, `generator_node`, `cv_tailor`, and `prep_pack_builder` to use `scout.company_name` and `intelligence.*` correctly.
- [ ] **Fix Generator Schemas:** Align `cv_tailor` and `cover_letter_gen` prompts with the actual `IntelligenceData` Pydantic model.
- [ ] **Real Profile Loading:** Replace hardcoded placeholder data in `generator_node` with data from `my_projects.json` and CV extraction.
- [ ] **Model String Fix:** Update `glassdoor_researcher.py` to use `gemini-1.5-flash` instead of `gemini-2.5-flash`.

## 🏗️ Medium Priority (Refactoring)
- [ ] **Centralize Config:** Remove local `_load_config` methods; use `AppConfig` everywhere.
- [ ] **Centralize Prompts:** Move `JobParser` prompt to `config/prompts.py`.
- [ ] **Path Safety:** Add real directory traversal checks to `disk_tool.py`.
- [ ] **Cleanup Schemas:** Remove unused `CoverLetterSection` and redundant config classes.

## 🚀 Low Priority (Features/Improvements)
- [ ] **Pluggable Scrapers:** Refactor `ScraperManager` to allow dynamic scraper registration.
- [ ] **Advanced Tech Detection:** Use LLM in `github_parser` for better tech stack extraction.
- [ ] **Supabase Migration:** Prepare SQL schemas for PostgreSQL migration.
- [ ] **Enhanced Logging:** Clean up redundant logging in `intelligence_artifacts.py`.
