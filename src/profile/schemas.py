"""
Pydantic schemas for Phase 5 — Profile.

These are used for structured LLM output when extracting data from
the user's LaTeX CV.
"""

from typing import List, Optional

from pydantic import BaseModel, Field


class ProjectHighlight(BaseModel):
    """A single bullet point highlight from a project with tool attribution."""
    text: str = Field(description="The clean, formatting-stripped text of the bullet point.")
    tools: List[str] = Field(
        default_factory=list,
        description="List of specific tools, frameworks, or languages explicitly used in THIS specific highlight/bullet point (e.g. ['YOLOv8'], ['LangGraph', 'Gemini'])."
    )


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
    highlights: List[ProjectHighlight] = Field(
        default_factory=list,
        description=(
            "The bullet point achievements from the CV. Each highlight should "
            "be a self-contained statement under 120 characters, with an array of "
            "tools used for that specific highlight."
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
    original_latex: str = Field(
        description=(
            "The exact, raw, unmodified LaTeX code chunk from the CV that "
            "corresponds to this specific project. Include the heading and all bullet points."
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
