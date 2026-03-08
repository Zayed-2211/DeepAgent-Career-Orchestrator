"""
Unit tests for intelligence/schemas.py.

Tests Pydantic V2 schema validation with edge cases:
  - Required vs optional fields
  - Enum validation (ApplicationMethod, SeniorityLevel, JobType)
  - is_job_posting=False suppresses intelligence
  - Nested model construction
  - ParsedJob round-trip (model_dump → model_validate)
"""

import pytest
from pydantic import ValidationError

from src.intelligence.schemas import (
    ApplicationMethod,
    GeminiJobResponse,
    IntelligenceData,
    JobType,
    ParsedJob,
    ScoutData,
    SeniorityLevel,
)


# ---------------------------------------------------------------------------
# ScoutData tests
# ---------------------------------------------------------------------------

class TestScoutData:

    def test_minimal_non_job_posting(self):
        """is_job_posting=False with all nulls is valid."""
        scout = ScoutData(is_job_posting=False)
        assert not scout.is_job_posting
        assert scout.company_name is None
        assert scout.application_method == ApplicationMethod.UNKNOWN

    def test_full_job_posting(self):
        scout = ScoutData(
            is_job_posting=True,
            company_name="Acme Corp",
            contact_info="hr@acme.com",
            application_method=ApplicationMethod.EMAIL,
            salary_min=20000,
            salary_max=35000,
            currency="EGP",
            city="Cairo",
            country="Egypt",
            is_remote=False,
            job_type=JobType.FULL_TIME,
            seniority=SeniorityLevel.JUNIOR,
            extra_notes="Mention ITI in subject",
        )
        assert scout.company_name == "Acme Corp"
        assert scout.salary_min == 20000.0
        assert scout.job_type == JobType.FULL_TIME
        assert scout.seniority == SeniorityLevel.JUNIOR

    def test_application_method_enum_validation(self):
        scout = ScoutData(is_job_posting=True, application_method="email")
        assert scout.application_method == ApplicationMethod.EMAIL

    def test_invalid_application_method_raises(self):
        with pytest.raises(ValidationError):
            ScoutData(is_job_posting=True, application_method="fax")

    def test_seniority_default(self):
        scout = ScoutData(is_job_posting=True)
        assert scout.seniority == SeniorityLevel.UNKNOWN

    def test_remote_can_be_none(self):
        scout = ScoutData(is_job_posting=True, is_remote=None)
        assert scout.is_remote is None


# ---------------------------------------------------------------------------
# IntelligenceData tests
# ---------------------------------------------------------------------------

class TestIntelligenceData:

    def test_all_null_is_valid(self):
        intel = IntelligenceData()
        assert intel.role_summary is None
        assert intel.tech_stack is None
        assert intel.must_haves is None

    def test_tech_stack_as_list(self):
        intel = IntelligenceData(tech_stack=["Python", "TensorFlow", "Docker"])
        assert len(intel.tech_stack) == 3
        assert "Python" in intel.tech_stack

    def test_exp_breakdown_as_dict(self):
        intel = IntelligenceData(
            total_exp_required=3.0,
            exp_breakdown={"Python": 3.0, "AWS": 2.0},
        )
        assert intel.exp_breakdown["AWS"] == 2.0

    def test_must_haves_as_list(self):
        intel = IntelligenceData(
            must_haves=["Bachelor's in CS", "3+ years Python"],
            nice_to_haves=["MSc degree"],
        )
        assert len(intel.must_haves) == 2
        assert intel.nice_to_haves[0] == "MSc degree"


# ---------------------------------------------------------------------------
# ParsedJob tests
# ---------------------------------------------------------------------------

class TestParsedJob:

    def test_empty_job_is_valid(self):
        job = ParsedJob()
        assert job.scout is None
        assert job.intelligence is None
        assert job.parse_error is None

    def test_round_trip_model_dump(self):
        """ParsedJob → model_dump() → model_validate() must be lossless."""
        scout = ScoutData(
            is_job_posting=True,
            company_name="TestCo",
            application_method=ApplicationMethod.EMAIL,
        )
        intel = IntelligenceData(tech_stack=["Python"], must_haves=["CS degree"])
        job = ParsedJob(
            job_uid="12345",
            platform="linkedin_posts",
            scout=scout,
            intelligence=intel,
        )
        dumped = job.model_dump()
        restored = ParsedJob.model_validate(dumped)
        assert restored.job_uid == "12345"
        assert restored.scout.company_name == "TestCo"
        assert restored.intelligence.tech_stack == ["Python"]

    def test_non_posting_job_has_no_intelligence(self):
        job = ParsedJob(
            scout=ScoutData(is_job_posting=False),
            intelligence=None,
        )
        assert job.intelligence is None

    def test_parse_error_field(self):
        job = ParsedJob(parse_error="Gemini timeout")
        assert job.parse_error == "Gemini timeout"
        assert job.scout is None


# ---------------------------------------------------------------------------
# GeminiJobResponse tests
# ---------------------------------------------------------------------------

class TestGeminiJobResponse:

    def test_minimal_non_posting(self):
        response = GeminiJobResponse(
            scout=ScoutData(is_job_posting=False),
        )
        assert not response.scout.is_job_posting
        assert response.intelligence is None

    def test_full_posting(self):
        response = GeminiJobResponse(
            scout=ScoutData(is_job_posting=True, company_name="Corp"),
            intelligence=IntelligenceData(role_summary="AI Engineer at Corp."),
        )
        assert response.scout.is_job_posting
        assert response.intelligence.role_summary == "AI Engineer at Corp."

    def test_json_round_trip(self):
        response = GeminiJobResponse(
            scout=ScoutData(
                is_job_posting=True,
                company_name="ACME",
                application_method=ApplicationMethod.WHATSAPP,
                seniority=SeniorityLevel.SENIOR,
                job_type=JobType.FULL_TIME,
            )
        )
        json_str = response.model_dump_json()
        restored = GeminiJobResponse.model_validate_json(json_str)
        assert restored.scout.application_method == ApplicationMethod.WHATSAPP
        assert restored.scout.seniority == SeniorityLevel.SENIOR
