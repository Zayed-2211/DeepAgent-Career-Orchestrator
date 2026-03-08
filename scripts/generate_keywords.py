"""
Generate/preview LLM boolean keywords for LinkedIn post search.

Usage:
    python scripts/generate_keywords.py            # Generate (skip if cached)
    python scripts/generate_keywords.py --force     # Force fresh LLM call
    python scripts/generate_keywords.py --preview   # Dry run (print only)
"""

import argparse
import io
import sys
from pathlib import Path

# Fix Windows console encoding for Arabic characters
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from loguru import logger
from config.search_queries import SEARCH_QUERIES, LOCATIONS
from src.scrapers.keyword_generator import KeywordGenerator


def _parse_location(location: str) -> tuple[str, str | None]:
    """
    Parse a location string into (country, city).

    Examples:
        "Egypt"        → ("Egypt", None)
        "Cairo, Egypt" → ("Egypt", "Cairo")
    """
    parts = [p.strip() for p in location.split(",")]
    if len(parts) >= 2:
        return parts[-1], parts[0]
    return parts[0], None


def main():
    parser = argparse.ArgumentParser(
        description="Generate LLM boolean keywords for LinkedIn post search"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force fresh LLM call (ignore existing cache)",
    )
    parser.add_argument(
        "--preview",
        action="store_true",
        help="Preview keywords without saving to cache",
    )
    args = parser.parse_args()

    generator = KeywordGenerator()

    # Use the most specific location from config
    location = LOCATIONS[-1] if LOCATIONS else "Egypt"
    country, city = _parse_location(location)

    logger.info(f"Job titles:  {SEARCH_QUERIES}")
    logger.info(f"Location:    {location} -> country={country}, city={city}")

    if args.preview:
        logger.info("Mode: PREVIEW (dry run - keywords will NOT be cached)")
        keywords = generator.preview(SEARCH_QUERIES, country, city)
    else:
        keywords = generator.get_or_generate(
            SEARCH_QUERIES, country, city, force=args.force
        )

    # Print results
    print("\n" + "=" * 60)
    print(f"  Generated {len(keywords)} boolean keywords")
    print("=" * 60)
    for i, kw in enumerate(keywords, 1):
        length_indicator = f"({len(kw)} chars)"
        print(f"  {i:2d}. {kw}  {length_indicator}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
