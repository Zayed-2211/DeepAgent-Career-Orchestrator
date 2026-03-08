"""
Unit tests for field_normalizer.py and validation.py.

All tests are deterministic (no Gemini calls).
"""

import pytest

from src.intelligence.field_normalizer import (
    clean_company_name,
    normalize,
    normalize_experience,
    normalize_location,
    normalize_tech_stack,
)
from src.intelligence.schemas import (
    ApplicationMethod,
    IntelligenceData,
    ParsedJob,
    ScoutData,
    SeniorityLevel,
)
from src.intelligence.validation import IssueSeverity, validate


# ---------------------------------------------------------------------------
# field_normalizer tests
# ---------------------------------------------------------------------------

class TestCleanCompanyName:
    def test_removes_ltd(self):
        assert clean_company_name("Acme Ltd") == "Acme"

    def test_removes_inc(self):
        assert clean_company_name("TechCorp Inc.") == "TechCorp"

    def test_removes_sae(self):
        assert clean_company_name("Global Corp S.A.E") == "Global Corp"

    def test_removes_parenthetical_country(self):
        assert clean_company_name("Volkswagen Group (Egypt)") == "Volkswagen Group"

    def test_handles_none(self):
        assert clean_company_name(None) is None

    def test_plain_name_unchanged(self):
        assert clean_company_name("Electro Pi") == "Electro Pi"


class TestNormalizeLocation:
    def test_nasr_city_expands(self):
        city, country = normalize_location("Nasr City", None)
        assert "Cairo" in city

    def test_new_cairo_expands(self):
        city, country = normalize_location("New Cairo", "Egypt")
        assert "Cairo" in city
        assert country == "Egypt"

    def test_country_alias_ksa(self):
        _, country = normalize_location(None, "ksa")
        assert country == "Saudi Arabia"

    def test_none_inputs(self):
        city, country = normalize_location(None, None)
        assert city is None
        assert country is None


class TestNormalizeExperience:
    def test_passthrough_float(self):
        assert normalize_experience(3.0) == 3.0

    def test_none_returns_none(self):
        assert normalize_experience(None) is None


class TestNormalizeTechStack:
    def test_canonical_casing(self):
        result = normalize_tech_stack(["python", "PYTORCH", "fastapi"])
        assert "Python" in result
        assert "PyTorch" in result
        assert "FastAPI" in result

    def test_deduplication(self):
        result = normalize_tech_stack(["Python", "python", "PYTHON"])
        assert len(result) == 1
        assert result[0] == "Python"

    def test_none_returns_none(self):
        assert normalize_tech_stack(None) is None

    def test_empty_returns_none(self):
        assert normalize_tech_stack([]) is None


class TestNormalize:
    """Test the full normalize() function on a ParsedJob."""

    def test_company_cleaned(self):
        job = ParsedJob(
            scout=ScoutData(is_job_posting=True, company_name="Acme Ltd"),
        )
        normalized = normalize(job)
        assert normalized.scout.company_name == "Acme"

    def test_tech_stack_cased(self):
        job = ParsedJob(
            scout=ScoutData(is_job_posting=True),
            intelligence=IntelligenceData(tech_stack=["tensorflow", "docker"]),
        )
        normalized = normalize(job)
        assert "TensorFlow" in normalized.intelligence.tech_stack
        assert "Docker" in normalized.intelligence.tech_stack


# ---------------------------------------------------------------------------
# validation tests
# ---------------------------------------------------------------------------

class TestValidation:

    def test_non_posting_always_valid(self):
        job = ParsedJob(scout=ScoutData(is_job_posting=False))
        result = validate(job)
        assert result.is_acceptable
        assert len(result.issues) == 0

    def test_missing_company_warning(self):
        job = ParsedJob(
            scout=ScoutData(is_job_posting=True, company_name=None),
        )
        result = validate(job)
        codes = [i.code for i in result.issues]
        assert "MISSING_COMPANY" in codes
        # Warning, not error — still acceptable
        assert result.is_acceptable

    def test_generic_concept_in_tech_stack_warning(self):
        job = ParsedJob(
            scout=ScoutData(is_job_posting=True, company_name="Corp"),
            intelligence=IntelligenceData(
                tech_stack=["Python", "machine learning"],  # generic concept in stack
                role_summary="AI role.",
            ),
        )
        result = validate(job)
        codes = [i.code for i in result.issues]
        assert "GENERIC_IN_TECH_STACK" in codes

    def test_must_nice_overlap_warning(self):
        job = ParsedJob(
            scout=ScoutData(is_job_posting=True, company_name="Corp"),
            intelligence=IntelligenceData(
                must_haves=["Python", "CS degree"],
                nice_to_haves=["Python", "Azure cert"],  # Python in both!
                role_summary="Dev role.",
            ),
        )
        result = validate(job)
        codes = [i.code for i in result.issues]
        assert "MUST_NICE_OVERLAP" in codes

    def test_email_contact_method_mismatch_warning(self):
        job = ParsedJob(
            scout=ScoutData(
                is_job_posting=True,
                company_name="Corp",
                contact_info="hr@corp.com",
                application_method=ApplicationMethod.WHATSAPP,  # Wrong method!
            ),
        )
        result = validate(job)
        codes = [i.code for i in result.issues]
        assert "METHOD_CONTACT_MISMATCH" in codes

    def test_no_scout_gives_error(self):
        job = ParsedJob(scout=None)
        result = validate(job)
        assert not result.is_acceptable
        assert any(i.severity == IssueSeverity.ERROR for i in result.issues)

    def test_quality_score_degraded_by_warnings(self):
        job = ParsedJob(
            scout=ScoutData(is_job_posting=True, company_name=None),
            intelligence=IntelligenceData(
                tech_stack=["cloud computing", "machine learning"],  # 2 generic concepts
                role_summary=None,  # Missing summary
            ),
        )
        result = validate(job)
        assert result.quality_score < 1.0
