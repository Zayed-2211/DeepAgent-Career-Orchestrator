"""
Multi-role post splitter using Gemini Flash.

Many LinkedIn job posts contain multiple roles in a single post (e.g.
"We're hiring: Python Dev, Data Analyst, ML Engineer — DM me for details").

This module:
  1. Detects whether a post likely contains multiple roles (heuristic pre-check)
  2. If yes, calls Gemini Flash with a strict Pydantic schema to split it
  3. Returns a list of individual job dictionaries (one per role)
  4. If the post has only one role, returns it as-is (passthrough)

Model policy:
  Only use gemini-2.5-flash or gemini-3.1-flash-lite-preview.
  Verified via client.models.list() on 2026-03-07.
  Never hardcode a model name from memory — add to _MODELS below instead.
"""

import json
import re
from typing import Any

from google import genai
from loguru import logger
from pydantic import BaseModel, Field

from config.settings import get_settings
from config.models_config import JOB_SPLITTING_PRIMARY, JOB_SPLITTING_FALLBACK


# ---------------------------------------------------------------------------
# Approved models — verified via client.models.list() on 2026-03-07
# ---------------------------------------------------------------------------
_MODELS = [
    JOB_SPLITTING_PRIMARY,
    JOB_SPLITTING_FALLBACK,
]


# ---------------------------------------------------------------------------
# Pydantic schema for structured output
# ---------------------------------------------------------------------------

class SingleJobPost(BaseModel):
    """One extracted job role from a multi-role post."""
    title: str = Field(description="Job title for this specific role")
    description: str = Field(
        description=(
            "Full description of this specific role only. "
            "Include requirements, responsibilities, and apply instructions "
            "that apply to this role. Do NOT include roles from other positions."
        )
    )
    company: str | None = Field(
        default=None,
        description="Company name, if mentioned for this specific role",
    )


class SplitResult(BaseModel):
    """Result of splitting a multi-role post."""
    roles: list[SingleJobPost] = Field(
        description=(
            "List of individual job roles found in the post. "
            "If the post has exactly one role, return a list with one item."
        )
    )


# ---------------------------------------------------------------------------
# Heuristic pre-check (fast, no API call)
# ---------------------------------------------------------------------------

# Patterns that suggest multiple roles in one post
_MULTI_ROLE_PATTERNS = [
    r"(?m)^\s*[\•\-\*]\s+\w",              # Bulleted list items
    r"(?m)^\s*\d+[\.\)]\s+\w",             # Numbered list items
    r"(?i)(we.re hiring|مطلوب).{0,200}(we.re hiring|مطلوب)",  # Two hiring signals
    r"(?i)(position|role|vacancy|وظيف).{0,50}(position|role|vacancy|وظيف)",
]

# Roles/titles that, if appearing 3+ times, suggest a multi-role post
_ROLE_TITLE_RE = re.compile(
    r"\b(engineer|developer|analyst|manager|designer|scientist|specialist|lead|"
    r"مهندس|محلل|مطور|مدير|مصمم)\b",
    re.IGNORECASE,
)


def is_multi_role(text: str) -> bool:
    """
    Heuristic check: does this post likely contain multiple job roles?

    Returns True if the text shows strong signals of being a multi-role post.
    This avoids unnecessary Gemini API calls for simple single-role posts.
    """
    if not text:
        return False

    # Count role title mentions — 3+ strongly suggests multiple roles
    role_count = len(_ROLE_TITLE_RE.findall(text))
    if role_count >= 3:
        return True

    # Check for lists (bullets or numbered) — typical in multi-role posts
    for pattern in _MULTI_ROLE_PATTERNS:
        if re.search(pattern, text):
            return True

    return False


# ---------------------------------------------------------------------------
# Gemini splitter
# ---------------------------------------------------------------------------

class MultiJobSplitter:
    """
    Splits multi-role LinkedIn posts into individual job records using Gemini Flash.

    Usage:
        splitter = MultiJobSplitter()
        jobs = splitter.split(raw_record)
        # jobs is a list[dict] — always at least 1 item
    """

    _PROMPT_TEMPLATE = """You are a job post parser. A recruiter has published a LinkedIn post that may contain one or more job openings.

Your task: Extract each distinct job role as a separate item.

Rules:
1. If the post contains ONE role → return exactly one item with the full description.
2. If the post contains MULTIPLE roles → return one item per role.
3. Each item must have: title, description (for that role only), and company (if mentioned).
4. Do NOT invent information. Only use what is in the post.
5. Keep apply instructions (email, phone, WhatsApp) in EVERY split item since they apply to all roles.
6. Keep requirements specific to a role only in that role's description.
7. If a requirement applies to all roles, include it in ALL items.

POST TEXT:
---
{post_text}
---
"""

    def __init__(self):
        self._client = self._init_client()

    @staticmethod
    def _init_client() -> genai.Client | None:
        """Initialize Gemini client."""
        key = get_settings().gemini_api_key
        if not key:
            logger.error("[splitter] GEMINI_API_KEY not set — multi-job splitting disabled")
            return None
        return genai.Client(api_key=key)

    def split(self, record: dict) -> list[dict]:
        """
        Split a raw post record into one or more individual job records.

        Returns:
            A list of dicts in the same format as the input record,
            one per detected role. Passthrough if Gemini is unavailable
            or the post contains only a single role.
        """
        text = record.get("description") or ""

        # Fast path: single-role post or no client
        if not self._client or not is_multi_role(text):
            return [record]

        logger.info("[splitter] Multi-role detected — calling Gemini")
        roles = self._call_gemini(text)

        if not roles or len(roles) <= 1:
            # Gemini found 0 or 1 roles — treat as passthrough
            return [record]

        logger.info(f"[splitter] Split into {len(roles)} individual records")
        return [self._build_record(record, role, idx) for idx, role in enumerate(roles)]

    def _call_gemini(self, post_text: str) -> list[SingleJobPost]:
        """Call Gemini with structured output schema. Returns list of roles."""
        import time
        
        prompt = self._PROMPT_TEMPLATE.format(post_text=post_text[:4000])

        for model in _MODELS:
            try:
                response = self._client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=genai.types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=SplitResult,
                        temperature=0.1,   # Low temp for consistent extraction
                    ),
                )
                result = SplitResult.model_validate_json(response.text)
                
                # Rate limit: sleep 4s between calls (free tier: 15 req/min)
                time.sleep(4)
                
                return result.roles
                
            except Exception as e:
                error_str = str(e).lower()
                
                # Handle quota exhaustion gracefully
                if "429" in error_str or "quota" in error_str or "resource_exhausted" in error_str:
                    logger.warning(f"[splitter] Quota exhausted on {model}. Returning original post (no split).")
                    return []  # Don't try other models - quota is account-wide
                
                logger.warning(f"[splitter] Model {model} failed: {e}")
                continue

        logger.error("[splitter] All models failed — returning original post")
        return []

    @staticmethod
    def _build_record(original: dict, role: SingleJobPost, idx: int) -> dict:
        """Build an individual job record from a split role."""
        record = dict(original)
        record["title"] = role.title
        record["description"] = role.description
        record["company"] = role.company or original.get("company")
        record["_split_index"] = idx          # Internal: which split this came from
        record["_split_from"] = original.get("job_uid") or original.get("job_url", "")
        return record
