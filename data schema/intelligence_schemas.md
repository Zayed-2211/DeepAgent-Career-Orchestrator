# Intelligence Schemas

> Source: `src/intelligence/schemas.py`

## ScoutData (Group 1 — Lightweight Metadata)

Always extracted, even for non-job-postings.

| Field | Type | Description | Notes |
|-------|------|-------------|-------|
| `is_job_posting` | `bool` | True if employer is hiring | Gate for all downstream processing |
| `company_name` | `str \| None` | Hiring company name | Suffixes like Inc/Ltd removed |
| `contact_info` | `str \| None` | Email, phone, or URL | Priority: email > phone > URL |
| `application_method` | `ApplicationMethod` | How to apply | Enum: url, email, whatsapp, phone, dm, unknown |
| `salary_min` | `float \| None` | Min salary (number) | EGP/USD/EUR etc. |
| `salary_max` | `float \| None` | Max salary (number) | Null if single figure |
| `currency` | `str \| None` | Currency code | EGP, USD, EUR, SAR |
| `city` | `str \| None` | Job location city | First city if multiple |
| `country` | `str \| None` | Country name | Defaults to "Egypt" for Egyptian cities |
| `is_remote` | `bool \| None` | Remote work flag | True=remote, False=onsite, None=hybrid/unknown |
| `job_type` | `JobType` | Employment type | Enum: full_time, part_time, contract, freelance, internship, unknown |
| `seniority` | `SeniorityLevel` | Level of role | Enum: intern→executive + unknown |
| `extra_notes` | `str \| None` | Application instructions | Max 200 chars |

## IntelligenceData (Group 2 — Deep Parsed Insights)

Only populated when `is_job_posting=True`.

| Field | Type | Description | Notes |
|-------|------|-------------|-------|
| `role_summary` | `str \| None` | 2-sentence role description | Max 150 chars |
| `exp_min_years` | `float \| None` | Min experience required | 0.0 for fresh grads |
| `exp_max_years` | `float \| None` | Max experience required | Null if open-ended (5+) |
| `exp_breakdown` | `dict[str, float] \| None` | Per-skill experience | e.g. `{"Python": 3.0}` |
| `tech_stack` | `list[str] \| None` | Specific tools/platforms | Python, Docker, TensorFlow — NOT concepts |
| `technical_skills` | `list[str] \| None` | Conceptual skills | ML, NLP, System Design — NOT tools |
| `work_domains` | `list[str] \| None` | Industry focus | FinTech, E-commerce, etc. |
| `specializations` | `list[str] \| None` | Niche focus areas | Agentic AI, RAG Pipelines, etc. |
| `must_haves` | `list[str] \| None` | Hard requirements | Max 60 chars each |
| `nice_to_haves` | `list[str] \| None` | Bonus qualifications | No overlap with must_haves |

## ParsedJob (Combined Container)

| Field | Type | Source |
|-------|------|--------|
| `job_uid` | `str \| None` | `uid_extractor.py` (code-based, not LLM) |
| `record_type` | `str \| None` | `"job_posting"`, `"non_posting"`, `"error"` |
| `platform` | `str \| None` | Raw record |
| `posting_type` | `str \| None` | Raw record |
| `source_url` | `str \| None` | Raw record |
| `author_name` | `str \| None` | Raw record |
| `raw_title` | `str \| None` | Raw record |
| `date_posted` | `str \| None` | Raw record |
| `reactions` | `int \| None` | Raw record |
| `phones` | `list[str] \| None` | Phase 3 contact extraction |
| `emails` | `list[str] \| None` | Phase 3 contact extraction |
| `primary_contact` | `str \| None` | Phase 3 contact extraction |
| `scout` | `ScoutData \| None` | Gemini structured output |
| `intelligence` | `IntelligenceData \| None` | Gemini structured output |
| `parsed_at` | `str \| None` | Timestamp |
| `model_used` | `str \| None` | Which Gemini model succeeded |
| `parse_error` | `str \| None` | Non-null = failed parse |

## GeminiJobResponse

The exact shape returned by Gemini's `with_structured_output()`. Contains only `scout` and `intelligence` — system fields are merged afterward by `JobParser._build_parsed_job()`.

## ⚠️ Known Inconsistency

- `cv_tailor.py` and `cover_letter_gen.py` access `job.get("company")` and `job.get("intelligence", {}).get("required_skills")` / `"responsibilities"`. But in `ParsedJob`, company is at `scout.company_name`, and the correct intelligence fields are `must_haves`/`nice_to_haves` — there is no `required_skills` or `responsibilities` field.
