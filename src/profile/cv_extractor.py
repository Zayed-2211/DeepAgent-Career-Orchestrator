"""
CV Project Extractor — Phase 5.

Uses Gemini (via LangChain structured output) to extract all projects from
the user's LaTeX CV and return them as validated Pydantic objects.

Only the projects listed in the CV's "Projects" section are extracted.
GitHub URL detection is done here so the caller can decide what to skip.
"""

from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from loguru import logger

from config.settings import get_settings
from src.profile.schemas import CVProjectExtractionResult, ParsedCVProject


# ---------------------------------------------------------------------------
# Approved Gemini models (verified available 2026-03-07)
# NOTE: Only use these two models. Do not change to older/unverified model IDs.
# ---------------------------------------------------------------------------
_MODELS = [
    "gemini-2.5-flash",               # Primary
    "gemini-3.1-flash-lite-preview",  # Fallback
]

_MAX_CV_LENGTH = 12_000  # chars — LaTeX CVs can be verbose, allow more than job posts


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

_SYSTEM_MESSAGE = """You are an expert CV parser specialising in LaTeX-formatted resumes.
Your task is to extract every project listed in the 'Projects' section of the given LaTeX CV.

EXTRACTION RULES:
  PROJECT NAME:
    - Use the exact title shown in the CV (strip LaTeX formatting like \\textbf{} \\textit{}).
    - Do NOT fabricate titles.

  DESCRIPTION:
    - Write 1-2 clear sentences describing what the project does and the problem it solves.
    - Infer from the bullet points if no explicit description is given.

  TECH STACK:
    - Extract specific tools/languages/frameworks from the tech line or bullet points.
    - Strip LaTeX formatting characters.
    - Examples: LangGraph, Pinecone, Python, FastAPI, PostgreSQL.

  DOMAINS:
    - Infer high-level domain tags from context.
    - Examples: AI, NLP, Healthcare, FinTech, Computer Vision, Backend, RAG.

  HIGHLIGHTS:
    - Copy the bullet points verbatim, stripping LaTeX formatting.
    - Each highlight should be a single clear statement under 120 characters.

  GITHUB URL:
    - Extract the raw URL if a GitHub link appears next to the project heading.
    - Set to null if there is no GitHub link for this project.

  PERIOD:
    - Extract the date range shown next to the project heading (e.g. "Jan 2025 - Mar 2025").
    - Set to null if no period is shown.

IMPORTANT:
  - Only extract from the Projects section. Ignore work experience, education, and activities.
  - If there is no Projects section, return an empty projects list.
  - Do not hallucinate any information not present in the CV.
"""

_USER_MESSAGE = """Here is the LaTeX CV content:

{cv_content}

Extract all projects from the Projects section."""

_PROMPT = ChatPromptTemplate.from_messages([
    ("system", _SYSTEM_MESSAGE),
    ("human", _USER_MESSAGE),
])


# ---------------------------------------------------------------------------
# Extractor
# ---------------------------------------------------------------------------

def extract_projects_from_cv(cv_content: str) -> list[ParsedCVProject]:
    """
    Parse the user's LaTeX CV and return all projects found in the
    Projects section as a list of ParsedCVProject objects.

    Returns an empty list if:
      - The CV content is blank / too short (< 50 chars).
      - The LLM finds no Projects section.
      - All models fail after retries.

    GitHub URL presence is preserved for the caller to handle:
    projects with github_url set should be skipped by the sync script,
    as the GitHub indexer will handle those.
    """
    cv_content = cv_content.strip()
    if len(cv_content) < 50:
        logger.warning("CV content appears empty or too short — skipping extraction.")
        return []

    # Truncate gracefully if extremely long
    if len(cv_content) > _MAX_CV_LENGTH:
        logger.warning(
            f"CV content truncated from {len(cv_content)} to {_MAX_CV_LENGTH} chars."
        )
        cv_content = cv_content[:_MAX_CV_LENGTH]

    settings = get_settings()
    last_error: Exception | None = None

    for model_id in _MODELS:
        try:
            logger.info(f"Extracting CV projects using model: {model_id}")
            llm = ChatGoogleGenerativeAI(
                model=model_id,
                google_api_key=settings.GEMINI_API_KEY,
                temperature=0,
            )
            chain = _PROMPT | llm.with_structured_output(CVProjectExtractionResult)
            result: CVProjectExtractionResult = chain.invoke({"cv_content": cv_content})
            logger.info(f"Extracted {len(result.projects)} project(s) from CV.")
            return result.projects

        except Exception as exc:
            logger.warning(f"Model {model_id} failed: {exc}. Trying next...")
            last_error = exc

    logger.error(f"All models failed for CV extraction. Last error: {last_error}")
    return []
