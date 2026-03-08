"""
LLM-powered boolean keyword generator for LinkedIn post search.

Generates 20-40 targeted boolean search queries using Gemini,
optimized for the user's job titles, country, and city.

Caching:
    Results are cached per (job_titles + country + city) combo.
    If the same config is used again, cached keywords are loaded
    instantly without calling the LLM.

Geographic Exclusion:
    If a specific city is selected (e.g. Cairo), the LLM prompt
    auto-excludes other major cities in the same country.
"""

import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from google import genai
from loguru import logger

from config.settings import get_settings, DATA_DIR


# ---------------------------------------------------------------------------
# Geographic exclusion map
# Maps country → list of major cities (English + Arabic names).
# When a user selects a specific city, ALL OTHER cities in the same
# country are excluded from the generated keywords.
# ---------------------------------------------------------------------------
COUNTRY_CITY_MAP = {
    "Egypt": {
        "Cairo": ["Cairo", "القاهرة"],
        "Alexandria": ["Alexandria", "الإسكندرية", "اسكندرية"],
        "Giza": ["Giza", "الجيزة"],
    },
    "UAE": {
        "Dubai": ["Dubai", "دبي"],
        "Abu Dhabi": ["Abu Dhabi", "أبوظبي"],
        "Sharjah": ["Sharjah", "الشارقة"],
    },
    "Saudi Arabia": {
        "Riyadh": ["Riyadh", "الرياض"],
        "Jeddah": ["Jeddah", "جدة"],
        "Dammam": ["Dammam", "الدمام"],
    },
}

# ---------------------------------------------------------------------------
# Cache directory
# ---------------------------------------------------------------------------
CACHE_DIR = DATA_DIR / "cache" / "keywords"

# ---------------------------------------------------------------------------
# LinkedIn boolean query max length
# ---------------------------------------------------------------------------
MAX_QUERY_LENGTH = 85


class KeywordGenerator:
    """Generates and caches LLM-powered boolean search keywords."""

    def __init__(self):
        settings = get_settings()
        self._client = genai.Client(api_key=settings.gemini_api_key)
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

    # -------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------
    def get_or_generate(
        self,
        job_titles: list[str],
        country: str,
        city: str | None = None,
        force: bool = False,
    ) -> list[str]:
        """
        Return boolean keywords for the given config.

        If a cache file exists and force=False, returns cached keywords.
        Otherwise calls Gemini, saves to cache, and returns fresh keywords.
        """
        cache_key = self._build_cache_key(job_titles, country, city)
        cache_path = CACHE_DIR / f"kw_{cache_key[:16]}.json"

        # Check cache (unless force refresh)
        if not force and cache_path.exists():
            cached = self._load_cache(cache_path)
            if cached:
                logger.info(
                    f"[keyword_gen] Cache HIT — loaded {len(cached)} keywords "
                    f"from {cache_path.name}"
                )
                return cached

        # Cache miss — generate fresh keywords
        logger.info(
            f"[keyword_gen] Cache MISS — generating keywords for "
            f"{job_titles} in {city or country}"
        )
        keywords = self._generate(job_titles, country, city)

        # Save to cache
        self._save_cache(cache_path, cache_key, job_titles, country, city, keywords)
        logger.info(
            f"[keyword_gen] Saved {len(keywords)} keywords to {cache_path.name}"
        )
        return keywords

    def preview(
        self,
        job_titles: list[str],
        country: str,
        city: str | None = None,
    ) -> list[str]:
        """Generate keywords without saving to cache (dry run)."""
        return self._generate(job_titles, country, city)

    # -------------------------------------------------------------------
    # Core generation (with retry + fallback model)
    # -------------------------------------------------------------------
    # Models to try in order. If the first is rate-limited, the next is tried.
    # IMPORTANT: Only use models confirmed available via `client.models.list()`.
    # To check: python -c "from google import genai; c = genai.Client(api_key='...')
    #   ; [print(m.name) for m in c.models.list()]"
    # Do NOT hardcode model names from memory — they change and deprecate.
    _MODELS = ["gemini-2.5-flash", "gemini-3.1-flash-lite-preview"]
    _MAX_RETRIES = 3
    _RETRY_DELAY = 5  # seconds between retries

    def _generate(
        self,
        job_titles: list[str],
        country: str,
        city: str | None = None,
    ) -> list[str]:
        """Call Gemini to generate boolean search queries with retry logic."""
        excluded_cities = self._get_excluded_cities(country, city)
        prompt = self._build_prompt(job_titles, country, city, excluded_cities)

        # Try each model with retries
        for model in self._MODELS:
            for attempt in range(1, self._MAX_RETRIES + 1):
                try:
                    logger.info(
                        f"[keyword_gen] Calling {model} "
                        f"(attempt {attempt}/{self._MAX_RETRIES})"
                    )
                    response = self._client.models.generate_content(
                        model=model,
                        contents=prompt,
                    )
                    raw_text = response.text.strip()

                    # Parse and validate
                    keywords = self._parse_response(raw_text)
                    keywords = self._enforce_length_limit(keywords)

                    if keywords:
                        logger.info(
                            f"[keyword_gen] Generated {len(keywords)} "
                            f"boolean keywords via {model}"
                        )
                        return keywords

                    logger.warning(
                        f"[keyword_gen] {model} returned no valid keywords"
                    )
                    break  # don't retry same model if it gave empty output

                except Exception as e:
                    error_str = str(e)
                    if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                        delay = self._RETRY_DELAY * attempt
                        logger.warning(
                            f"[keyword_gen] Rate limited on {model}, "
                            f"waiting {delay}s before retry..."
                        )
                        time.sleep(delay)
                        continue
                    else:
                        logger.error(
                            f"[keyword_gen] {model} error: {error_str[:200]}"
                        )
                        break  # non-rate-limit error, try next model

        logger.warning("[keyword_gen] All models failed — using fallback keywords")
        return self._fallback_keywords(job_titles, country, city)

    # -------------------------------------------------------------------
    # Prompt engineering
    # -------------------------------------------------------------------
    def _build_prompt(
        self,
        job_titles: list[str],
        country: str,
        city: str | None,
        excluded_cities: list[str],
    ) -> str:
        """Build the Gemini prompt for keyword generation."""
        titles_str = ", ".join(f'"{t}"' for t in job_titles)
        location_str = f"{city}, {country}" if city else country

        exclusion_block = ""
        if excluded_cities:
            cities_str = ", ".join(excluded_cities)
            exclusion_block = (
                f"\n- EXCLUDE posts specifically about these other cities: {cities_str}"
                f"\n  Use NOT clauses where helpful (e.g. NOT Alexandria, NOT الإسكندرية)"
                f"\n  But do NOT add a NOT clause to every single query — only when it helps precision"
            )

        return f"""You are a LinkedIn search query expert specializing in job hunting in {country}.

I am looking for LinkedIn HIRING POSTS (not articles, not news, not opinions) for these job titles: {titles_str}
Target location: {location_str}

Generate exactly 30 boolean search queries for LinkedIn's content search that will find real hiring posts.

CRITICAL RULES:
1. Use exact phrases in double quotes for job titles: "AI engineer"
2. Use boolean operators AND, OR, NOT in UPPERCASE
3. EVERY query MUST be 85 characters or less (LinkedIn truncates longer queries)
4. Generate queries in BOTH English AND Arabic (Egyptian dialect)
5. Include hiring-intent words: hiring, مطلوب, وظيفة, فرصة عمل, looking for, join, apply, نبحث عن, تقدم
6. Mix SPECIFIC queries (exact job title) with BROADER queries (field-level like "AI" or "machine learning")
7. Include common Egyptian hiring phrases: مطلوب للتعيين, فرص عمل, وظائف شاغرة, ابعت cv
8. Include some queries with the company/startup angle: "we're hiring", "join our team", "انضم لفريقنا"
9. DO NOT over-filter — some informal posts won't use exact job titles, we still want those
10. Include Franco-Arabic variants where common: "matlob", "3ayzen"{exclusion_block}

IMPORTANT: Output ONLY the queries, one per line. No numbering, no bullets, no explanation, no markdown.
Each line should be a complete boolean search query ready to paste into LinkedIn's search bar.
"""

    # -------------------------------------------------------------------
    # Response parsing
    # -------------------------------------------------------------------
    def _parse_response(self, raw_text: str) -> list[str]:
        """Parse LLM response into a list of keyword strings."""
        lines = raw_text.strip().split("\n")
        keywords = []
        for line in lines:
            # Strip numbering, bullets, whitespace
            cleaned = line.strip()
            cleaned = cleaned.lstrip("0123456789.-) ")
            cleaned = cleaned.strip()
            # Skip empty lines or markdown artifacts
            if not cleaned or cleaned.startswith("```") or cleaned.startswith("#"):
                continue
            keywords.append(cleaned)
        return keywords

    def _enforce_length_limit(self, keywords: list[str]) -> list[str]:
        """Remove keywords that exceed LinkedIn's 85-char limit."""
        valid = []
        for kw in keywords:
            if len(kw) <= MAX_QUERY_LENGTH:
                valid.append(kw)
            else:
                logger.debug(
                    f"[keyword_gen] Trimmed keyword ({len(kw)} chars): {kw[:50]}..."
                )
        return valid

    # -------------------------------------------------------------------
    # Geographic exclusion
    # -------------------------------------------------------------------
    def _get_excluded_cities(
        self, country: str, city: str | None
    ) -> list[str]:
        """
        Get cities to exclude based on selected country and city.

        If a specific city is selected, exclude all OTHER major cities
        in the same country (both English and Arabic names).
        If no city is selected, exclude nothing.
        """
        if not city or country not in COUNTRY_CITY_MAP:
            return []

        country_cities = COUNTRY_CITY_MAP[country]
        excluded = []
        for city_name, variants in country_cities.items():
            # Skip the selected city
            if city_name.lower() == city.lower():
                continue
            excluded.extend(variants)
        return excluded

    # -------------------------------------------------------------------
    # Fallback keywords (no LLM available)
    # -------------------------------------------------------------------
    def _fallback_keywords(
        self, job_titles: list[str], country: str, city: str | None
    ) -> list[str]:
        """Generate simple fallback keywords when LLM is unavailable."""
        location = city or country
        keywords = []
        for title in job_titles:
            keywords.append(f'"{title}" AND hiring AND {location}')
            keywords.append(f'"{title}" AND (مطلوب OR وظيفة)')
        keywords.append(f"hiring AND {location}")
        keywords.append(f"مطلوب AND {location}")
        return [kw for kw in keywords if len(kw) <= MAX_QUERY_LENGTH]

    # -------------------------------------------------------------------
    # Cache management
    # -------------------------------------------------------------------
    @staticmethod
    def _build_cache_key(
        job_titles: list[str], country: str, city: str | None
    ) -> str:
        """Build a deterministic SHA256 hash from the inputs."""
        parts = sorted(t.lower().strip() for t in job_titles)
        parts.append(country.lower().strip())
        if city:
            parts.append(city.lower().strip())
        raw = "|".join(parts)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @staticmethod
    def _load_cache(cache_path: Path) -> list[str] | None:
        """Load keywords from a cache file. Returns None if invalid."""
        try:
            data = json.loads(cache_path.read_text(encoding="utf-8"))
            return data.get("keywords", [])
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"[keyword_gen] Failed to read cache: {e}")
            return None

    @staticmethod
    def _save_cache(
        cache_path: Path,
        cache_key: str,
        job_titles: list[str],
        country: str,
        city: str | None,
        keywords: list[str],
    ) -> None:
        """Save keywords to a JSON cache file."""
        data = {
            "cache_key": cache_key,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "inputs": {
                "job_titles": job_titles,
                "country": country,
                "city": city,
            },
            "keywords": keywords,
        }
        cache_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
