"""
Pydantic V2 schemas for Phase 4 intelligence extraction.

These are the single source of truth for the output shape of every job record.
ALL downstream consumers (Phase 6 agent, Phase 7 CV generator, Phase 9 DB)
must read from these models and never from raw dicts.

Schema groups:
  - Group 1 (ScoutData)       : lightweight, always extractable metadata
  - Group 2 (IntelligenceData): deep AI-parsed intelligence, may be null for
                                 posts that are not actual job offers
  - ParsedJob                 : combined container holding both groups +
                                 system fields carried over from the raw record

Model notes:
  - All fields are optional / nullable unless stated otherwise. Real-world
    LinkedIn posts are often incomplete and a required field would crash parsing.
  - Use `Field(description=...)` on every field — these descriptions are injected
    into the Gemini prompt as the schema documentation.
  - `ApplicationMethod` duplicates `config/constants.py` intentionally to keep
    this module self-contained and importable independently of the scraper stack.
"""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ApplicationMethod(str, Enum):
    URL = "url"
    EMAIL = "email"
    WHATSAPP = "whatsapp"
    PHONE = "phone"
    DM = "dm"           # LinkedIn DM / comment
    UNKNOWN = "unknown"


class SeniorityLevel(str, Enum):
    INTERN = "intern"
    JUNIOR = "junior"
    MID = "mid"
    SENIOR = "senior"
    LEAD = "lead"
    MANAGER = "manager"
    DIRECTOR = "director"
    EXECUTIVE = "executive"
    UNKNOWN = "unknown"


class JobType(str, Enum):
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACT = "contract"
    FREELANCE = "freelance"
    INTERNSHIP = "internship"
    UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# Group 1 — Scout & Deduplication Metadata
# ---------------------------------------------------------------------------

class ScoutData(BaseModel):
    """
    Group 1: Lightweight, always-extractable metadata about the job.

    Fields here should be extractable from almost any job post, even a short one.
    This is what the Phase 6 agent uses to decide whether to look deeper.
    """

    is_job_posting: bool = Field(
        description=(
            "True if this post is an employer/recruiter hiring for a specific role. "
            "False for: #OpenToWork posts (candidate seeking a job), "
            "achievement posts, generic announcements, or non-hiring posts. "
            "If False, all other fields may be null."
        )
    )

    company_name: str | None = Field(
        default=None,
        description=(
            "The hiring company name. Use the company the role is AT, not the author's company. "
            "E.g. if an HR from 'Electro Pi' posts about a role at 'Electro Pi', use 'Electro Pi'. "
            "Remove suffixes like 'Inc.', 'Ltd.', 'Co.' from the name."
        ),
    )

    contact_info: str | None = Field(
        default=None,
        description=(
            "Primary way to apply: email address, WhatsApp number, or URL. "
            "Use the FIRST and most specific contact shown. "
            "If multiple exist, prefer email > phone > URL."
        ),
    )

    application_method: ApplicationMethod = Field(
        default=ApplicationMethod.UNKNOWN,
        description=(
            "How to apply. Set 'email' if an email address is given, "
            "'whatsapp' if a WhatsApp number is given, 'url' if a link is the primary method, "
            "'phone' if only a phone number is given, 'dm' if the post says DM/comment. "
            "Default to 'unknown' if unclear."
        ),
    )

    salary_min: float | None = Field(
        default=None,
        description=(
            "Minimum salary as a number. Convert ranges like '20k-30k EGP' to 20000. "
            "If only one figure is given, put it in salary_min. "
            "Null if salary is not mentioned."
        ),
    )

    salary_max: float | None = Field(
        default=None,
        description=(
            "Maximum salary as a number. E.g. 30000 for '20k-30k EGP'. "
            "Null if salary is not mentioned or only a single figure is given."
        ),
    )

    currency: str | None = Field(
        default=None,
        description=(
            "Currency code: 'EGP', 'USD', 'EUR', 'SAR', etc. "
            "Infer from context if not stated (e.g., Egyptian post with no currency = likely EGP). "
            "Null if salary is not mentioned."
        ),
    )

    city: str | None = Field(
        default=None,
        description=(
            "City where the role is located. E.g. 'Cairo', 'Nasr City', 'New Cairo'. "
            "If multiple cities are listed, use the first one. Null if not mentioned."
        ),
    )

    country: str | None = Field(
        default=None,
        description=(
            "Country of the role. Default to 'Egypt' if the city is Egyptian and no country is stated. "
            "Use ISO country names, not codes."
        ),
    )

    is_remote: bool | None = Field(
        default=None,
        description=(
            "True if the role is fully remote. False if fully onsite. "
            "Null if not mentioned. If a post says 'hybrid', set to null and note in extra_notes."
        ),
    )

    job_type: JobType = Field(
        default=JobType.UNKNOWN,
        description=(
            "Employment type. 'full_time' for standard roles, 'internship' for internships, "
            "'contract' for fixed-term, 'freelance' for project work."
        ),
    )

    seniority: SeniorityLevel = Field(
        default=SeniorityLevel.UNKNOWN,
        description=(
            "Seniority level. Infer from title and requirements if not explicitly stated. "
            "'junior' = 0-2 years, 'mid' = 2-5 years, 'senior' = 5+ years."
        ),
    )

    extra_notes: str | None = Field(
        default=None,
        description=(
            "Any specific application instructions not captured elsewhere. "
            "E.g. 'Mention ITI Intake 44 in subject', 'Apply before March 10', "
            "'Attach portfolio and Behance link'. Max 200 characters."
        ),
    )


# ---------------------------------------------------------------------------
# Group 2 — Intelligence Layer (Deep Parsed Insights)
# ---------------------------------------------------------------------------

class IntelligenceData(BaseModel):
    """
    Group 2: Deep AI-parsed intelligence. Only populated for is_job_posting=True posts.

    Fields here require careful reading of the full JD. These feed Phase 6's
    matching engine and Phase 7's CV tailoring.
    """

    role_summary: str | None = Field(
        default=None,
        description=(
            "2-sentence summary of the role for quick scanning. "
            "Sentence 1: what the role IS and WHO it's at. "
            "Sentence 2: the most important technical requirement or focus area. "
            "Max 150 characters total."
        ),
    )

    exp_min_years: float | None = Field(
        default=None,
        description=(
            "Minimum years of experience required. "
            "For a range like '3-5 years experience' → set to 3.0. "
            "For a single value like '3 years' or '3+ years' → set BOTH exp_min_years AND exp_max_years to 3.0. "
            "For '0-2 years' or 'fresh graduates' or '0-1 year' → set to 0.0. "
            "Null if experience is not mentioned."
        ),
    )

    exp_max_years: float | None = Field(
        default=None,
        description=(
            "Maximum years of experience required. "
            "For '3-5 years' → 5.0. For '5+ years' → set to null (open-ended). "
            "For a single value like '3 years' → same as exp_min_years (3.0). "
            "For '0-2 years' → 2.0. Null if experience is not mentioned."
        ),
    )

    exp_breakdown: dict[str, float] | None = Field(
        default=None,
        description=(
            "Years of experience required per skill or technology. "
            "Only include where a SPECIFIC year count is stated. "
            "E.g. {'Python': 3.0, 'AWS': 2.0}. Null if no specific breakdowns given."
        ),
    )

    tech_stack: list[str] | None = Field(
        default=None,
        description=(
            "List of SPECIFIC tools, frameworks, and platforms mentioned. "
            "Only actual software products, not generic concepts. "
            "E.g. ['Python', 'TensorFlow', 'Docker', 'AWS'] NOT ['programming', 'cloud']."
        ),
    )

    technical_skills: list[str] | None = Field(
        default=None,
        description=(
            "List of conceptual/domain skills that are NOT specific tools. "
            "E.g. ['Machine Learning', 'RAG', 'System Design', 'NLP']. "
            "Do NOT duplicate items from tech_stack here."
        ),
    )

    work_domains: list[str] | None = Field(
        default=None,
        description=(
            "Industry or domain focus. E.g. ['FinTech', 'E-commerce', 'Construction Tech']. "
            "Use the industry the COMPANY is in, or explicitly mentioned domain. "
            "Null if not clear."
        ),
    )

    specializations: list[str] | None = Field(
        default=None,
        description=(
            "Niche focus areas within the role. More specific than technical_skills. "
            "E.g. ['Agentic AI', 'LLM Fine-tuning', 'RAG Pipelines', 'Computer Vision']. "
            "Include ALL specializations even if ambiguous (e.g. 'AI/ML' = include both)."
        ),
    )

    must_haves: list[str] | None = Field(
        default=None,
        description=(
            "Hard requirements — absolute minimums the candidate MUST have. "
            "Extract from words like 'required', 'must have', 'minimum'. "
            "E.g. ['Bachelor in CS', '3+ years Python', 'Strong English']. "
            "Keep each item concise (max 60 chars)."
        ),
    )

    nice_to_haves: list[str] | None = Field(
        default=None,
        description=(
            "Bonus qualifications — things that HELP but are not required. "
            "Extract from: 'preferred', 'nice to have', 'plus', 'bonus'. "
            "E.g. ['MSc degree', 'Azure certification', 'SaaS experience']. "
            "Do NOT repeat items from must_haves."
        ),
    )


# ---------------------------------------------------------------------------
# ParsedJob — Combined container
# ---------------------------------------------------------------------------

class ParsedJob(BaseModel):
    """
    Full parsed job record combining system fields, Group 1, and Group 2.

    This is what gets written to:
      - data/intelligence/{date}/parsed_jobs.json
      - processed_jobs table in SQLite (as JSON columns)
    """

    # System fields (carried from the raw record)
    job_uid: str | None = None           # Platform-native UID (e.g. linkedin_posts:7434510034866294785)
    record_type: str | None = None       # 'job_posting' | 'non_posting' | 'error'
    platform: str | None = None
    posting_type: str | None = None
    source_url: str | None = None
    author_name: str | None = None
    raw_title: str | None = None         # Original title from scraper
    date_posted: str | None = None
    reactions: int | None = None

    # Contact info extracted by Phase 3
    phones: list[str] | None = None
    emails: list[str] | None = None
    primary_contact: str | None = None

    # Group 1 — always attempted
    scout: ScoutData | None = None

    # Group 2 — only for actual job postings
    intelligence: IntelligenceData | None = None

    # Metadata
    parsed_at: str | None = None
    model_used: str | None = None
    parse_error: str | None = None    # Non-null means this record had a problem


# ---------------------------------------------------------------------------
# Gemini response schema (subset of ParsedJob — what Gemini fills in)
# ---------------------------------------------------------------------------

class GeminiJobResponse(BaseModel):
    """
    The exact shape Gemini returns when called with structured output.

    Separated from ParsedJob so Gemini only sees the fields it's responsible for.
    System fields (job_uid, platform, etc.) are merged in afterward.
    """
    scout: ScoutData
    intelligence: IntelligenceData | None = None
