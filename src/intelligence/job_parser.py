"""
Gemini-powered job intelligence extractor.

Uses LangChain's ChatGoogleGenerativeAI with .with_structured_output() so that:
  - Gemini is called via the LangChain interface (consistent with the rest of the project)
  - Pydantic V2 handles schema enforcement and validation automatically
  - .with_structured_output() manages the JSON schema conversion correctly

Model policy (verified 2026-03-07):
  - Primary:  gemini-2.5-flash
  - Fallback: gemini-3.1-flash-lite-preview
  NOTE: Always use these exact model IDs. Do NOT use outdated names like
  gemini-pro, gemini-1.5-flash, etc.

Retry behaviour:
  - Up to 2 retries on validation or structured output failure
  - On retry, the prompt includes the previous error to guide correction
  - After all retries fail, returns a ParsedJob with parse_error set
"""

from datetime import datetime, timezone

from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from loguru import logger

from config.settings import get_settings
from src.intelligence.schemas import GeminiJobResponse, ParsedJob
from src.intelligence.uid_extractor import uid_from_url


# ---------------------------------------------------------------------------
# Approved Gemini models (verified available 2026-03-07)
# NOTE: Only use these two models. Do not change to older/unverified model IDs.
# ---------------------------------------------------------------------------
_MODELS = [
    "gemini-2.5-flash",               # Primary
    "gemini-3.1-flash-lite-preview",  # Fallback
]

_MAX_RETRIES = 2
_MAX_TEXT_LENGTH = 6000  # Truncate very long posts before sending to Gemini


# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

_SYSTEM_MESSAGE = """You are an expert job posting analyst specializing in Egyptian and Arab LinkedIn posts.
Your task is to extract structured information from LinkedIn posts.

CLASSIFICATION RULES — is_job_posting:
  Set is_job_posting=FALSE for:
    - Posts with #OpenToWork, #LookingForWork, #JobSeeker, #OpenForOpportunities
    - Posts where the AUTHOR says "I am looking for", "I am seeking", "available for hire"
    - Graduation/thesis/achievement announcements ("I just graduated", "proud to share my thesis")
    - General opinion or educational posts ("5 tips for...", "Why AI matters...")
    - Congratulation posts with no hiring intent
    - Event or webinar announcements
  Set is_job_posting=TRUE when a company or recruiter is explicitly hiring for a specific role.

EXTRACTION RULES:
  COMPANY NAME:
    - Use the company the role is AT, not necessarily the post author's company
    - If only an author name is given with no company, set company_name=null
    - Do NOT add legal suffixes (Inc., Ltd., SAE, Co.) to company_name

  SALARY:
    - Only extract if a number is explicitly stated. Do NOT guess or infer.
    - If multiple salaries are listed for different roles, use the FIRST one
    - Convert shorthand: 20k = 20000, 20K EGP = 20000 EGP
    - Sanity check: EGP salaries are typically 5,000-100,000/month. If you see 200,000+/month EGP it may be annual — note in extra_notes

  EXPERIENCE:
    - exp_min_years and exp_max_years are always a PAIR:
      - "0-2 years" → min=0.0, max=2.0
      - "3 years" or "3+ years" → min=3.0, max=3.0 (same value)
      - "5+ years" → min=5.0, max=null (open-ended)
      - "fresh graduate" / "no experience" → min=0.0, max=0.0
    - Null BOTH if experience is not mentioned at all

  MUST HAVES:
    - Extract ALL explicit requirements including from bullet points and numbered lists
    - Look for: "required", "must", "mandatory", "essential", "minimum", or bullet/numbered items in a requirements section
    - Each item should be 1 concise line (max 60 chars)
    - Include: degree requirements, year of experience, key skills that are listed as required

  TECH STACK vs TECHNICAL SKILLS:
    - tech_stack = ONLY specific software products (Python, Docker, TensorFlow, PostgreSQL)
    - technical_skills = conceptual skills (Machine Learning, NLP, System Design, Data Analysis)
    - NEVER put a concept in tech_stack or a specific tool in technical_skills

  CONTACT INFO:
    - Prefer in order: email > Egyptian phone > international phone > URL > DM
    - WhatsApp links like wa.me/2010xxx → extract phone number as contact_info"""

_PROMPT = ChatPromptTemplate.from_messages([
    ("system", _SYSTEM_MESSAGE),
    ("human", (
        "Extract structured job information from the following LinkedIn post.\n\n"
        "POST TITLE: {title}\n"
        "POST AUTHOR: {author}\n"
        "POST TEXT:\n---\n{text}\n---\n\n"
        "Remember: set is_job_posting=False if this is NOT an employer actively hiring."
    )),
])

_RETRY_PROMPT = ChatPromptTemplate.from_messages([
    ("system", _SYSTEM_MESSAGE),
    ("human", (
        "The previous extraction failed with this error:\n{error}\n\n"
        "Please try again with the same post, ensuring valid output.\n\n"
        "POST TITLE: {title}\n"
        "POST AUTHOR: {author}\n"
        "POST TEXT:\n---\n{text}\n---"
    )),
])


# ---------------------------------------------------------------------------
# Parser class
# ---------------------------------------------------------------------------

class JobParser:
    """
    Extracts Group 1 + Group 2 intelligence from raw job post records.

    Uses LangChain's ChatGoogleGenerativeAI with .with_structured_output()
    to enforce the GeminiJobResponse Pydantic schema.

    Usage:
        parser = JobParser()
        parsed = parser.parse(raw_record)  # returns ParsedJob
    """

    def __init__(self):
        self._chains = self._build_chains()

    def _build_chains(self) -> list[tuple[str, object]]:
        """Build one LangChain chain per model with structured output."""
        key = get_settings().gemini_api_key
        if not key:
            logger.error("[parser] GEMINI_API_KEY not set — parsing disabled")
            return []

        chains = []
        for model_id in _MODELS:
            llm = ChatGoogleGenerativeAI(
                model=model_id,
                google_api_key=key,
                temperature=0.1,
            ).with_structured_output(GeminiJobResponse)
            chains.append((model_id, llm))
        return chains

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def parse(self, record: dict) -> ParsedJob:
        """
        Parse a single raw job record.

        Returns a ParsedJob. On failure, returns a ParsedJob with parse_error set.
        Never raises — always returns something.
        """
        if not self._chains:
            return self._error_job(record, "No Gemini client — GEMINI_API_KEY missing")

        text = (record.get("description") or "")[:_MAX_TEXT_LENGTH]
        title = record.get("title") or ""
        author = record.get("author_name") or record.get("company") or "Unknown"

        gemini_result, model_id = self._call_with_retries(text, title, author)
        return self._build_parsed_job(record, gemini_result, model_id)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _call_with_retries(
        self, text: str, title: str, author: str
    ) -> tuple[GeminiJobResponse, str] | tuple[None, None]:
        """
        Call Gemini with up to _MAX_RETRIES retries on failure.

        Returns: (GeminiJobResponse, model_id_that_succeeded) or (None, None).
        """
        last_error: str | None = None

        for attempt in range(_MAX_RETRIES + 1):
            for model_id, chain in self._chains:
                try:
                    if attempt == 0:
                        prompt_vars = {"title": title, "author": author, "text": text}
                        result = (_PROMPT | chain).invoke(prompt_vars)
                    else:
                        prompt_vars = {
                            "error": last_error,
                            "title": title,
                            "author": author,
                            "text": text,
                        }
                        result = (_RETRY_PROMPT | chain).invoke(prompt_vars)

                    if not isinstance(result, GeminiJobResponse):
                        last_error = f"Unexpected return type: {type(result)}"
                        logger.warning(f"[parser] {model_id} bad type: {last_error}")
                        continue

                    logger.debug(
                        f"[parser] OK — is_job={result.scout.is_job_posting!r} "
                        f"model={model_id} attempt={attempt + 1}"
                    )
                    return result, model_id

                except Exception as e:
                    err = str(e)[:300]
                    last_error = err

                    if "429" in err or "RESOURCE_EXHAUSTED" in err:
                        logger.warning(f"[parser] Rate limit on {model_id}: {err[:80]}")
                        continue  # Try next model

                    logger.warning(
                        f"[parser] attempt={attempt + 1} model={model_id} error: {err[:120]}"
                    )
                    break  # Move to next attempt (retry with error context)

        logger.error(f"[parser] All retries exhausted: {title[:60]}")
        return None, None

    def _build_parsed_job(
        self, record: dict, gemini_result: GeminiJobResponse | None, model_id: str | None = None
    ) -> ParsedJob:
        """Merge Gemini output with system fields from the raw record."""
        now = datetime.now(timezone.utc).isoformat()

        # Always extract job_uid from URL (code-based, not LLM)
        source_url = record.get("job_url")
        platform = record.get("platform")
        extracted_uid = uid_from_url(source_url, platform) or record.get("job_uid")

        if gemini_result is None:
            return self._error_job(record, "All Gemini models failed or returned invalid output", extracted_uid)

        # If it's a real job posting, try to fill contact_info from Phase 3 data
        scout = gemini_result.scout
        if scout.is_job_posting and not scout.contact_info and record.get("primary_contact"):
            scout = scout.model_copy(update={"contact_info": record["primary_contact"]})

        # Only keep intelligence for actual job postings
        intelligence = gemini_result.intelligence if scout.is_job_posting else None
        record_type = "job_posting" if scout.is_job_posting else "non_posting"

        return ParsedJob(
            # System fields carried from raw record
            job_uid=extracted_uid,
            record_type=record_type,
            platform=platform,
            posting_type=record.get("posting_type"),
            source_url=source_url,
            author_name=record.get("author_name"),
            raw_title=record.get("title"),
            date_posted=record.get("date_posted"),
            reactions=record.get("reactions"),
            # Phase 3 contact fields
            phones=record.get("phones"),
            emails=record.get("emails"),
            primary_contact=record.get("primary_contact"),
            # Parsed groups
            scout=scout,
            intelligence=intelligence,
            # Metadata — model_id is the one that actually succeeded
            parsed_at=now,
            model_used=model_id or _MODELS[0],
            parse_error=None,
        )

    @staticmethod
    def _error_job(record: dict, error: str, uid: str | None = None) -> ParsedJob:
        """Return a ParsedJob with parse_error set."""
        source_url = record.get("job_url")
        platform = record.get("platform")
        extracted_uid = uid or uid_from_url(source_url, platform) or record.get("job_uid")
        return ParsedJob(
            job_uid=extracted_uid,
            record_type="error",
            platform=platform,
            source_url=source_url,
            raw_title=record.get("title"),
            parse_error=error,
            parsed_at=datetime.now(timezone.utc).isoformat(),
        )
