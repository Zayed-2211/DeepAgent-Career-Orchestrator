"""
Pydantic schemas for Phase 5 — Profile.

These are used for structured LLM output when extracting data from
the user's LaTeX CV.
"""

from typing import List, Optional

from pydantic import BaseModel, Field


class ParsedCVProject(BaseModel):
    """A single project extracted from the user's LaTeX CV by the LLM."""

    name: str = Field(
        description="The exact project title as it appears in the CV."
    )
    description: str = Field(
        description=(
            "A concise 1-2 sentence description of what the project does "
            "and the problem it solves. Infer from context if not explicit."
        )
    )
    tech_stack: List[str] = Field(
        default_factory=list,
        description=(
            "Specific tools, frameworks, and languages used. "
            "Extract from the tech line or bullet points (e.g. LangGraph, Pinecone, Python)."
        )
    )
    domains: List[str] = Field(
        default_factory=list,
        description=(
            "Industry or domain tags inferred from the project context. "
            "Examples: AI, NLP, Healthcare, FinTech, Computer Vision, Backend."
        )
    )
    highlights: List[str] = Field(
        default_factory=list,
        description=(
            "The bullet point achievements from the CV, verbatim or lightly cleaned. "
            "Each highlight should be a self-contained statement under 120 characters."
        )
    )
    github_url: Optional[str] = Field(
        default=None,
        description=(
            "The GitHub URL if one is linked to this project in the CV. "
            "Set to null if no GitHub link is present."
        )
    )
    period: Optional[str] = Field(
        default=None,
        description=(
            "The time period shown next to the project heading, e.g. 'Jan 2025 - Mar 2025'. "
            "Set to null if no period is listed."
        )
    )


class CVProjectExtractionResult(BaseModel):
    """Wrapper returned by the LLM for the full extraction run."""

    projects: List[ParsedCVProject] = Field(
        description=(
            "All projects found in the Projects section of the LaTeX CV. "
            "If no Projects section exists, return an empty list."
        )
    )
