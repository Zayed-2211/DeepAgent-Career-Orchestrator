"""
Post-extraction quality validation for Phase 4 parsed job records.

Validates that Gemini's output makes sense and flags low-quality parses.
Runs AFTER field_normalizer. No LLM calls — all checks are deterministic.

Checks:
  1. If is_job_posting=True, company_name should not be null (soft warning)
  2. tech_stack should contain actual tools, not generic concepts
  3. exp_breakdown values should not exceed total_exp_required significantly
  4. must_haves and nice_to_haves should not share items
  5. role_summary should not be empty for actual job postings

Returns a list of QualityIssue objects (warnings/errors) and an overall score.
"""

import re
from dataclasses import dataclass, field
from enum import Enum

from src.intelligence.schemas import ParsedJob


# ---------------------------------------------------------------------------
# Issue severity
# ---------------------------------------------------------------------------

class IssueSeverity(str, Enum):
    WARNING = "warning"   # Data might be wrong but usable
    ERROR = "error"       # Data is definitely wrong or missing critical field


@dataclass
class QualityIssue:
    code: str
    message: str
    severity: IssueSeverity


@dataclass
class ValidationResult:
    issues: list[QualityIssue] = field(default_factory=list)
    quality_score: float = 1.0   # 0.0–1.0; 1.0 = perfect

    @property
    def is_acceptable(self) -> bool:
        """True if quality score >= 0.5 and no ERROR-level issues."""
        has_errors = any(i.severity == IssueSeverity.ERROR for i in self.issues)
        return not has_errors and self.quality_score >= 0.5

    def add(self, code: str, message: str, severity: IssueSeverity, penalty: float = 0.1):
        self.issues.append(QualityIssue(code=code, message=message, severity=severity))
        self.quality_score = max(0.0, self.quality_score - penalty)


# ---------------------------------------------------------------------------
# Generic concept words that should NOT appear in tech_stack
# ---------------------------------------------------------------------------
_GENERIC_CONCEPTS = {
    "machine learning", "deep learning", "artificial intelligence", "ai", "ml",
    "data science", "data analysis", "programming", "cloud computing", "cloud",
    "software development", "web development", "backend", "frontend", "devops",
    "algorithms", "statistics", "mathematics", "big data", "analytics",
    "communication", "teamwork", "problem solving", "nlp", "computer vision",
}


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------

def validate(job: ParsedJob) -> ValidationResult:
    """
    Run all quality checks on a ParsedJob.

    Returns a ValidationResult with issues and a quality score.
    """
    result = ValidationResult()

    # No scout data at all → skip (parse error handled elsewhere)
    if job.scout is None:
        result.add(
            code="NO_SCOUT",
            message="ParsedJob has no ScoutData — likely a parse error",
            severity=IssueSeverity.ERROR,
            penalty=1.0,
        )
        return result

    # Non-job-posting: all we can check is that other fields ARE null
    if not job.scout.is_job_posting:
        return result  # Non-postings are always valid (nothing to validate)

    # --- Job posting checks ---

    # 1. Company name
    if not job.scout.company_name:
        result.add(
            code="MISSING_COMPANY",
            message="is_job_posting=True but company_name is null. "
                    "Author name may need to be used instead.",
            severity=IssueSeverity.WARNING,
            penalty=0.1,
        )

    # 2. Role summary
    intel = job.intelligence
    if intel:
        if not intel.role_summary:
            result.add(
                code="MISSING_ROLE_SUMMARY",
                message="role_summary is null for a job posting",
                severity=IssueSeverity.WARNING,
                penalty=0.05,
            )

        # 3. Tech stack quality
        if intel.tech_stack:
            for item in intel.tech_stack:
                if item.lower().strip() in _GENERIC_CONCEPTS:
                    result.add(
                        code="GENERIC_IN_TECH_STACK",
                        message=(
                            f"'{item}' is a concept, not a tool. "
                            f"It should be in technical_skills, not tech_stack."
                        ),
                        severity=IssueSeverity.WARNING,
                        penalty=0.05,
                    )

        # 4. Experience consistency
        if intel.exp_min_years is not None and intel.exp_breakdown:
            max_breakdown = max(intel.exp_breakdown.values(), default=0)
            if max_breakdown > (intel.exp_min_years or 0) + 2:
                result.add(
                    code="EXP_BREAKDOWN_TOO_HIGH",
                    message=(
                        f"exp_breakdown max ({max_breakdown}) is much higher than "
                        f"exp_min_years ({intel.exp_min_years})"
                    ),
                    severity=IssueSeverity.WARNING,
                    penalty=0.1,
                )

        # 5. Must-haves vs nice-to-haves overlap
        if intel.must_haves and intel.nice_to_haves:
            must_lower = {m.lower().strip() for m in intel.must_haves}
            for item in intel.nice_to_haves:
                if item.lower().strip() in must_lower:
                    result.add(
                        code="MUST_NICE_OVERLAP",
                        message=f"'{item}' appears in both must_haves and nice_to_haves",
                        severity=IssueSeverity.WARNING,
                        penalty=0.05,
                    )

    # 6. Application method vs contact_info consistency
    if job.scout.contact_info:
        method = job.scout.application_method.value
        contact = job.scout.contact_info.lower()
        if "@" in contact and method not in ("email", "unknown"):
            result.add(
                code="METHOD_CONTACT_MISMATCH",
                message=(
                    f"contact_info looks like an email but application_method='{method}'"
                ),
                severity=IssueSeverity.WARNING,
                penalty=0.05,
            )

    return result
