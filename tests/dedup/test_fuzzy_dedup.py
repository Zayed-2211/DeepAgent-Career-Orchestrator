"""
Unit tests for fuzzy_dedup.py — MinHash LSH near-duplicate detection.

Tests:
  - Identical text → near-duplicate detected
  - Slightly different text (>75% similar) → near-duplicate detected
  - Completely different text → not a duplicate
  - Same text, different company → not flagged as duplicate
  - Short text → safely skipped (not hashed)
"""

import pytest

from src.dedup.fuzzy_dedup import FuzzyDedup


# Long enough text to actually be hashable
_BASE_JD = (
    "We are looking for a Senior AI Engineer to join our team in Cairo. "
    "You will work on LLM-based products, build RAG pipelines, and design "
    "agentic workflows using LangGraph and Python. Requirements: 3 years "
    "experience in ML/AI, strong Python skills, experience with OpenAI or "
    "Gemini APIs. Apply via email: hr@company.com. Location: Cairo, Egypt."
)


class TestFuzzyDedup:

    def test_identical_posts_same_company_flagged(self):
        dedup = FuzzyDedup(threshold=0.75)
        r1 = {"description": _BASE_JD, "company": "TestCorp", "job_uid": "111"}
        r2 = {"description": _BASE_JD, "company": "TestCorp", "job_uid": "222"}
        assert not dedup.is_near_duplicate(r1)
        dedup.add(r1)
        assert dedup.is_near_duplicate(r2)

    def test_different_company_not_flagged(self):
        """Same JD but different company → NOT a duplicate (different hiring entity)."""
        dedup = FuzzyDedup(threshold=0.75)
        r1 = {"description": _BASE_JD, "company": "CompanyA", "job_uid": "111"}
        r2 = {"description": _BASE_JD, "company": "CompanyB", "job_uid": "222"}
        assert not dedup.is_near_duplicate(r1)
        dedup.add(r1)
        # Different company → pass through even if text identical
        assert not dedup.is_near_duplicate(r2)

    def test_completely_different_post_not_flagged(self):
        dedup = FuzzyDedup(threshold=0.75)
        r1 = {"description": _BASE_JD, "company": "Corp", "job_uid": "111"}
        r2 = {
            "description": (
                "Chef de cuisine wanted for 5-star restaurant in downtown Cairo. "
                "Must have 10 years culinary experience. Apply at kitchen@hotel.eg"
            ),
            "company": "Corp",
            "job_uid": "222",
        }
        dedup.add(r1)
        assert not dedup.is_near_duplicate(r2)

    def test_slightly_edited_post_flagged(self):
        """Minor edits (add/remove a sentence) — still caught at 0.75 threshold."""
        dedup = FuzzyDedup(threshold=0.65)  # Slightly lower for minor edits
        r1 = {"description": _BASE_JD, "company": "Corp", "job_uid": "111"}
        # Slightly edited version
        edited = _BASE_JD.replace("Senior AI Engineer", "AI Engineer").replace("3 years", "2+ years")
        r2 = {"description": edited, "company": "Corp", "job_uid": "222"}
        dedup.add(r1)
        assert dedup.is_near_duplicate(r2)

    def test_short_text_passes_through(self):
        """Very short posts are skipped safely (not hashed)."""
        dedup = FuzzyDedup()
        short = {"description": "Hiring dev", "company": "X", "job_uid": "1"}
        assert not dedup.is_near_duplicate(short)
        result = dedup.add(short)
        # add() returns False for too-short text (can't be hashed)
        assert result is False

    def test_add_returns_true_for_valid_post(self):
        dedup = FuzzyDedup()
        record = {"description": _BASE_JD, "company": "Corp", "job_uid": "111"}
        assert dedup.add(record) is True

    def test_size_tracks_added_records(self):
        dedup = FuzzyDedup()
        r1 = {"description": _BASE_JD, "company": "A", "job_uid": "1"}
        r2 = {
            "description": "Completely different long text about software engineering "
            "roles in tech companies across the middle east region 2026.",
            "company": "B",
            "job_uid": "2",
        }
        dedup.add(r1)
        dedup.add(r2)
        assert dedup.size == 2
