"""
Unit tests for contact_extractor.py.

Tests all Egyptian phone formats, email extraction,
and negative cases that should NOT match.
Uses real fixture data from tests/fixtures/sample_contact_extraction.json.
"""

import json
from pathlib import Path

import pytest

from src.dedup.contact_extractor import (
    extract_all,
    extract_emails,
    extract_phones,
    extract_telegram,
    extract_whatsapp,
    primary_contact,
)

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


# ---------------------------------------------------------------------------
# Phone number extraction tests
# ---------------------------------------------------------------------------

class TestExtractPhones:
    """Test Egyptian mobile phone number extraction."""

    def test_standard_11_digit(self):
        assert extract_phones("Call: 01115742429") == ["01115742429"]

    def test_vodafone_prefix(self):
        assert extract_phones("WhatsApp: 01012345678") == ["01012345678"]

    def test_orange_prefix(self):
        assert extract_phones("Send CV to 01212345678") == ["01212345678"]

    def test_we_telecom_prefix(self):
        assert extract_phones("Contact: 01512345678") == ["01512345678"]

    def test_international_plus20(self):
        assert extract_phones("Phone: +201115742429") == ["01115742429"]

    def test_international_0020(self):
        assert extract_phones("Tel: 00201115742429") == ["01115742429"]

    def test_arabic_indic_numerals(self):
        # ٠١١١٥٧٤٢٤٢٩ == 01115742429
        assert extract_phones("📱 ٠١١١٥٧٤٢٤٢٩") == ["01115742429"]

    def test_multiple_phones(self):
        text = "HR: 01115742429 or 01557801754"
        result = extract_phones(text)
        assert "01115742429" in result
        assert "01557801754" in result

    def test_no_match_landline(self):
        # Cairo landline (02x) — should NOT match
        assert extract_phones("Call: 0223456789") == []

    def test_no_match_short_number(self):
        assert extract_phones("Team of 01234567 members") == []

    def test_empty_text(self):
        assert extract_phones("") == []
        assert extract_phones(None) == []

    def test_real_electro_pi_post(self):
        text = "📱 01115742429\n🚀 Join Electro Pi"
        assert extract_phones(text) == ["01115742429"]

    def test_real_tots_college_post(self):
        text = "📲 Send your CV now: 01557801754\n📧 Or email: hr.totscollege@gmail.com"
        assert extract_phones(text) == ["01557801754"]


# ---------------------------------------------------------------------------
# Email extraction tests
# ---------------------------------------------------------------------------

class TestExtractEmails:
    """Test email address extraction."""

    def test_basic_email(self):
        assert extract_emails("Send to hr@company.com") == ["hr@company.com"]

    def test_email_lowercased(self):
        assert extract_emails("Email: HR@Company.COM") == ["hr@company.com"]

    def test_subdomain_email(self):
        result = extract_emails("jasmin.okwieka@volkswagengroupco.com")
        assert "jasmin.okwieka@volkswagengroupco.com" in result

    def test_multiple_emails(self):
        text = "Primary: a@b.com, also cc@dd.eg"
        result = extract_emails(text)
        assert len(result) == 2

    def test_no_email(self):
        assert extract_emails("No contact info here.") == []

    def test_real_yozo_post(self):
        text = "Email: ziad@yozo.ai\n\nAttach your Behance link"
        assert extract_emails(text) == ["ziad@yozo.ai"]

    def test_real_tots_college_email(self):
        text = "📧 Or email: hr.totscollege@gmail.com"
        assert extract_emails(text) == ["hr.totscollege@gmail.com"]


# ---------------------------------------------------------------------------
# extract_all + primary_contact tests
# ---------------------------------------------------------------------------

class TestExtractAll:
    """Test combined extraction and primary contact resolution."""

    def test_extract_all_returns_all_fields(self):
        result = extract_all("📱 01115742429 | hr@company.com")
        assert "phones" in result
        assert "emails" in result
        assert "whatsapp" in result
        assert "telegram" in result

    def test_primary_prefers_email_over_phone(self):
        contacts = {
            "emails": ["hr@company.com"],
            "phones": ["01115742429"],
            "whatsapp": [],
            "telegram": [],
        }
        assert primary_contact(contacts) == "hr@company.com"

    def test_primary_fallback_to_phone(self):
        contacts = {"emails": [], "phones": ["01115742429"], "whatsapp": [], "telegram": []}
        assert primary_contact(contacts) == "01115742429"

    def test_primary_returns_none_when_empty(self):
        contacts = {"emails": [], "phones": [], "whatsapp": [], "telegram": []}
        assert primary_contact(contacts) is None


# ---------------------------------------------------------------------------
# Fixture-based tests
# ---------------------------------------------------------------------------

class TestFixtures:
    """Integration tests using real fixture data."""

    @pytest.fixture
    def fixture_data(self):
        path = FIXTURES_DIR / "sample_contact_extraction.json"
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def test_fixture_phone_posts(self, fixture_data):
        for case in fixture_data["test_posts_with_phones"]:
            phones = extract_phones(case["text_snippet"])
            for expected_phone in case["expected_phones"]:
                assert expected_phone in phones, (
                    f"Expected {expected_phone!r} in phones for: {case['text_snippet'][:80]!r}"
                )

    def test_fixture_email_posts(self, fixture_data):
        for case in fixture_data["test_posts_with_phones"]:
            emails = extract_emails(case["text_snippet"])
            for expected_email in case["expected_emails"]:
                assert expected_email in emails, (
                    f"Expected {expected_email!r} in emails for: {case['text_snippet'][:80]!r}"
                )

    def test_fixture_negative_cases(self, fixture_data):
        for case in fixture_data["negative_cases"]:
            phones = extract_phones(case["text"])
            assert phones == [], (
                f"Expected no phones for: {case['text']!r} but got {phones!r}"
            )
