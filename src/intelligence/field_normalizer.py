"""
Post-extraction field normalization for Phase 4 parsed job records.

All normalization is deterministic (no LLM calls) and runs AFTER Gemini parsing.
Handles messy real-world patterns seen in Egyptian LinkedIn posts.

Normalizations:
  1. Salary strings → (min, max, currency) numeric values
  2. Experience strings → float years
  3. Company name cleanup (remove Inc., Ltd., Co., etc.)
  4. Location normalization (Cairo variants → 'Cairo', etc.)
  5. Tech stack deduplication and casing standardization

These mutations are applied in-place to a ParsedJob model copy.
"""

import re

from src.intelligence.schemas import (
    IntelligenceData,
    ParsedJob,
    ScoutData,
)


# ---------------------------------------------------------------------------
# Company name cleanup
# ---------------------------------------------------------------------------

# Suffixes to strip from company names (case-insensitive).
# ONLY pure legal entity registration suffixes — do NOT add words like
# Group, Holdings, International, Egypt, Misr because they are often
# part of the real company name (e.g. "Volkswagen Group", "Egypt Air").
_COMPANY_SUFFIXES = re.compile(
    r"""
    \s+
    (Inc|Incorporated|Ltd|Limited|LLC|L\.L\.C|S\.A\.E|SAE|Corp|Corporation)
    \.?\s*$
    """,
    re.VERBOSE | re.IGNORECASE,
)


def clean_company_name(name: str | None) -> str | None:
    """Remove common legal suffixes from company names."""
    if not name:
        return None
    name = name.strip()
    # Remove bracketed suffixes like "(Egypt)"
    name = re.sub(r"\s*\([^)]+\)\s*$", "", name).strip()
    # Remove trailing legal suffix
    name = _COMPANY_SUFFIXES.sub("", name).strip()
    # Remove trailing periods and commas
    name = name.rstrip(".,;").strip()
    return name or None


# ---------------------------------------------------------------------------
# Location normalization
# ---------------------------------------------------------------------------

# Cairo variant spellings → canonical
_LOCATION_MAP = {
    "nasr city": "Nasr City, Cairo",
    "new cairo": "New Cairo, Cairo",
    "maadi": "Maadi, Cairo",
    "zamalek": "Zamalek, Cairo",
    "heliopolis": "Heliopolis, Cairo",
    "6th october": "6th of October City",
    "6 october": "6th of October City",
    "sheikh zayed": "Sheikh Zayed City",
    "smart village": "Smart Village, Giza",
    "5th settlement": "5th Settlement, New Cairo",
    "fifth settlement": "5th Settlement, New Cairo",
    "el rehab": "El Rehab, Cairo",
    "rehab": "El Rehab, Cairo",
    "mokattam": "Mokattam, Cairo",
    "alex": "Alexandria",
    "alexanria": "Alexandria",  # Common typo
    "cairo egypt": "Cairo",
}


def normalize_location(city: str | None, country: str | None) -> tuple[str | None, str | None]:
    """
    Normalize city and country strings.

    Returns: (normalized_city, normalized_country)
    """
    if city:
        lower = city.lower().strip()
        city = _LOCATION_MAP.get(lower, city.strip().title())

    if country:
        country = country.strip()
        # Normalize common country aliases
        aliases = {"eg": "Egypt", "egypt": "Egypt", "ksa": "Saudi Arabia", "uae": "UAE"}
        country = aliases.get(country.lower(), country.title())

    return city, country


# ---------------------------------------------------------------------------
# Experience normalization
# ---------------------------------------------------------------------------

def normalize_experience(value: float | None) -> float | None:
    """Passthrough for a single float value. Returns None for None."""
    if value is not None:
        return float(value)
    return None


# ---------------------------------------------------------------------------
# Tech stack normalization
# ---------------------------------------------------------------------------

# Canonical casing for common tools
_TECH_CASING = {
    "python": "Python",
    "pytorch": "PyTorch",
    "tensorflow": "TensorFlow",
    "langchain": "LangChain",
    "langgraph": "LangGraph",
    "huggingface": "HuggingFace",
    "hugging face": "HuggingFace",
    "openai": "OpenAI",
    "fastapi": "FastAPI",
    "postgresql": "PostgreSQL",
    "mongo": "MongoDB",
    "mongodb": "MongoDB",
    "elasticsearch": "Elasticsearch",
    "docker": "Docker",
    "kubernetes": "Kubernetes",
    "aws": "AWS",
    "gcp": "GCP",
    "azure": "Azure",
    "sql": "SQL",
    "nosql": "NoSQL",
    "react": "React",
    "nodejs": "Node.js",
    "node.js": "Node.js",
    "golang": "Go",
    "nextjs": "Next.js",
    "next.js": "Next.js",
    "django": "Django",
    "flask": "Flask",
    "scikit-learn": "Scikit-learn",
    "scrapy": "Scrapy",
    "selenium": "Selenium",
    "pandas": "Pandas",
    "numpy": "NumPy",
}


def normalize_tech_stack(stack: list[str] | None) -> list[str] | None:
    """Apply canonical casing to tech stack items and deduplicate."""
    if not stack:
        return None
    seen = set()
    result = []
    for item in stack:
        normalized = _TECH_CASING.get(item.lower().strip(), item.strip())
        key = normalized.lower()
        if key not in seen:
            seen.add(key)
            result.append(normalized)
    return result or None


def clean_list_field(items: list[str] | None) -> list[str] | None:
    """
    Remove garbage from LLM list outputs:
      - Strip leading/trailing whitespace and newlines from each item
      - Drop items that are empty, only whitespace, or only newline characters
      - Drop items that are suspiciously long (> 200 chars, likely LLM runaway)
      - Deduplicate (case-insensitive)

    This prevents the '\\n\\n\\n...' repeated newline artifact from Gemini.
    """
    if not items:
        return None
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        cleaned = item.strip().replace("\r", "").replace("\n", " ")
        # Collapse multiple spaces left by newline replacement
        cleaned = " ".join(cleaned.split())
        if not cleaned:
            continue
        if len(cleaned) > 200:
            # Truncate runaway items rather than drop entirely
            cleaned = cleaned[:197] + "..."
        key = cleaned.lower()
        if key not in seen:
            seen.add(key)
            result.append(cleaned)
    return result or None


# ---------------------------------------------------------------------------
# Main normalizer
# ---------------------------------------------------------------------------

def normalize(job: ParsedJob) -> ParsedJob:
    """
    Apply all normalizations to a ParsedJob and return a new copy.

    Safe to call multiple times — idempotent.
    """
    scout = job.scout
    intel = job.intelligence

    if scout is None:
        return job

    # --- Company name ---
    cleaned_company = clean_company_name(scout.company_name)

    # --- Location ---
    city, country = normalize_location(scout.city, scout.country)

    # --- Intelligence fields ---
    if intel:
        normalized_stack = normalize_tech_stack(intel.tech_stack)

        intel = intel.model_copy(update={
            # exp fields are already floats from Gemini — just passthrough
            "exp_min_years": normalize_experience(intel.exp_min_years),
            "exp_max_years": normalize_experience(intel.exp_max_years),
            # Tech stack: canonical casing + dedup
            "tech_stack": normalized_stack,
            # All other list fields: strip \n garbage and dedup
            "technical_skills": clean_list_field(intel.technical_skills),
            "work_domains": clean_list_field(intel.work_domains),
            "specializations": clean_list_field(intel.specializations),
            "must_haves": clean_list_field(intel.must_haves),
            "nice_to_haves": clean_list_field(intel.nice_to_haves),
        })

    scout = scout.model_copy(update={
        "company_name": cleaned_company,
        "city": city,
        "country": country,
    })

    return job.model_copy(update={
        "scout": scout,
        "intelligence": intel,
    })
