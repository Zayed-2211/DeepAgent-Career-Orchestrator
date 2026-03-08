"""
Unit tests for fingerprint.py — two-tier dedup system.

Tests:
  - Fingerprint determinism (same input → same hash)
  - Tier 1: job_uid fast-path dedup
  - Tier 2: content fingerprint fallback
  - Both tiers together in sequence
  - The exact scenario from real data: same post re-scraped with same job_uid
"""

import pytest

from src.dedup.fingerprint import compute_fingerprint, DedupChecker
from src.db.db_manager import DBManager


# ---------------------------------------------------------------------------
# In-memory DB for tests (fresh for each test)
# ---------------------------------------------------------------------------

@pytest.fixture
def db(tmp_path):
    """Provide a fresh in-memory DBManager backed by a temp file."""
    return DBManager(db_path=tmp_path / "test_jobs.db")


# ---------------------------------------------------------------------------
# Fingerprint computation tests
# ---------------------------------------------------------------------------

class TestComputeFingerprint:

    def test_deterministic_same_inputs(self):
        record = {"primary_contact": "hr@test.com", "company": "Acme", "title": "Engineer"}
        assert compute_fingerprint(record) == compute_fingerprint(record)

    def test_different_contacts_different_hash(self):
        r1 = {"primary_contact": "hr@company.com", "company": "ACME", "title": "Dev"}
        r2 = {"primary_contact": "cto@company.com", "company": "ACME", "title": "Dev"}
        assert compute_fingerprint(r1) != compute_fingerprint(r2)

    def test_same_contact_different_company_different_hash(self):
        r1 = {"primary_contact": "hr@same.com", "company": "CompanyA", "title": "Dev"}
        r2 = {"primary_contact": "hr@same.com", "company": "CompanyB", "title": "Dev"}
        assert compute_fingerprint(r1) != compute_fingerprint(r2)

    def test_returns_64_char_sha256(self):
        record = {"primary_contact": "a@b.com", "company": "X", "title": "Y"}
        fp = compute_fingerprint(record)
        assert len(fp) == 64
        assert all(c in "0123456789abcdef" for c in fp)

    def test_case_insensitive_normalization(self):
        r1 = {"primary_contact": "HR@CO.COM", "company": "COMPANY", "title": "ENGINEER"}
        r2 = {"primary_contact": "hr@co.com", "company": "company", "title": "engineer"}
        assert compute_fingerprint(r1) == compute_fingerprint(r2)

    def test_handles_missing_fields(self):
        # Should not crash on missing fields
        assert compute_fingerprint({}) is not None
        assert len(compute_fingerprint({})) == 64


# ---------------------------------------------------------------------------
# DedupChecker tests
# ---------------------------------------------------------------------------

class TestDedupChecker:

    @pytest.fixture
    def checker(self, db):
        return DedupChecker(db)

    @pytest.fixture
    def sample_record(self):
        return {
            "job_uid": "7434578207858769920",
            "platform": "linkedin_posts",
            "title": "AI Engineer",
            "company": "TestCorp",
            "primary_contact": "hr@testcorp.com",
            "job_url": "https://linkedin.com/posts/activity-7434578207858769920",
        }

    def test_new_record_not_duplicate(self, db, checker, sample_record):
        with db.connect() as conn:
            assert not checker.is_duplicate(conn, sample_record)

    def test_tier1_uid_duplicate_detected(self, db, checker, sample_record):
        with db.connect() as conn:
            checker.mark_seen(conn, sample_record)
        with db.connect() as conn:
            assert checker.is_duplicate(conn, sample_record)

    def test_tier2_fingerprint_duplicate_detected(self, db, checker, sample_record):
        # Same post with different job_uid (e.g. reshared)
        reshare = dict(sample_record)
        reshare["job_uid"] = "9999999999999999999"  # Different uid
        with db.connect() as conn:
            checker.mark_seen(conn, sample_record)
        with db.connect() as conn:
            # Should catch via fingerprint (same contact+company+title)
            assert checker.is_duplicate(conn, reshare)

    def test_different_contact_not_duplicate(self, db, checker, sample_record):
        different = dict(sample_record)
        different["job_uid"] = "1111111111111111111"
        different["primary_contact"] = "other@differentco.com"
        different["company"] = "DifferentCorp"
        with db.connect() as conn:
            checker.mark_seen(conn, sample_record)
        with db.connect() as conn:
            assert not checker.is_duplicate(conn, different)

    def test_null_uid_falls_to_fingerprint(self, db, checker):
        """Post with no job_uid still gets deduped via fingerprint."""
        record = {
            "job_uid": None,
            "title": "Data Scientist",
            "company": "Corp",
            "primary_contact": "data@corp.com",
        }
        with db.connect() as conn:
            assert not checker.is_duplicate(conn, record)
            checker.mark_seen(conn, record)
        with db.connect() as conn:
            assert checker.is_duplicate(conn, record)

    def test_same_uid_rejected_on_reinsert(self, db, checker, sample_record):
        """The exact requirement: same job_uid must be rejected on re-insert."""
        with db.connect() as conn:
            checker.mark_seen(conn, sample_record)
            # Even within same connection, should still detect as duplicate
            duplicate = dict(sample_record)
            duplicate["primary_contact"] = "changed@email.com"  # Contact changed
            # Tier 1 should still catch it via uid
            assert checker.is_duplicate(conn, duplicate)
