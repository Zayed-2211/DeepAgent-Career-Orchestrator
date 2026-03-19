"""
Pydantic schemas for CV and cover letter generation.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class TailoredExperience(BaseModel):
    """Single experience entry with tailored bullets."""
    
    company: str = Field(description="Company name")
    position: str = Field(description="Job title/position")
    period: str = Field(description="Time period (e.g., 'Jan 2023 - Present')")
    bullets: list[str] = Field(
        description="Tailored bullet points highlighting relevant achievements",
        max_items=5,
    )


class TailoredProject(BaseModel):
    """Single project entry with tailored description."""
    
    name: str = Field(description="Project name")
    tech_stack: list[str] = Field(description="Technologies used")
    bullets: list[str] = Field(
        description="Tailored bullet points emphasizing job-relevant aspects",
        max_items=3,
    )
    github_url: str | None = Field(default=None, description="GitHub repository URL")


class TailoredCV(BaseModel):
    """Complete tailored CV structure for Gemini output."""
    
    professional_summary: str = Field(
        description="2-3 sentence summary tailored to the job (max 500 chars)",
        max_length=500,
    )
    
    experience: list[TailoredExperience] = Field(
        description="Work experience entries (most recent first)",
        max_items=3,
    )
    
    projects: list[TailoredProject] = Field(
        description="Top matched projects tailored to job requirements",
        max_items=3,
    )
    
    technical_skills: list[str] = Field(
        description="Technical skills relevant to the job",
        max_items=15,
    )
    
    soft_skills: list[str] = Field(
        description="Soft skills mentioned in job description",
        max_items=5,
    )


class CoverLetterSection(BaseModel):
    """Single paragraph in cover letter."""
    
    content: str = Field(description="Paragraph content")


class TailoredCoverLetter(BaseModel):
    """Complete tailored cover letter structure."""
    
    opening: str = Field(
        description="Opening paragraph - introduce yourself and express interest (max 400 chars)",
        max_length=400,
    )
    
    body_paragraph_1: str = Field(
        description="First body paragraph - highlight relevant experience/projects (max 600 chars)",
        max_length=600,
    )
    
    body_paragraph_2: str = Field(
        description="Second body paragraph - explain why you're a great fit (max 600 chars)",
        max_length=600,
    )
    
    closing: str = Field(
        description="Closing paragraph - call to action and thank you (max 300 chars)",
        max_length=300,
    )
    
    tone: str = Field(
        default="professional",
        description="Overall tone of the letter",
    )
