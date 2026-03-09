"""
Tests for Phase 5 profile module — schemas and sync logic.

These tests cover:
  - ParsedCVProject schema validation
  - Duplicate name detection logic
  - Placeholder entry detection
  - Project-to-dict serialization

The LLM extraction (cv_extractor.py) is not tested here (requires API key).
"""

import json
from difflib import SequenceMatcher
from pathlib import Path

import pytest

from src.profile.schemas import CVProjectExtractionResult, ParsedCVProject, ProjectHighlight


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_project():
    return ParsedCVProject(
        name="Secure Agentic CRAG",
        description="A stateful CRAG system using LangGraph and Gemini.",
        tech_stack=["LangGraph", "LangChain", "Pinecone", "Python"],
        domains=["AI", "NLP"],
        highlights=[
            ProjectHighlight(
                text="Built a stateful CRAG system using LangGraph and Gemini 1.5 Flash",
                tools=["LangGraph", "Gemini 1.5 Flash"]
            ),
            ProjectHighlight(
                text="Integrated Pydantic guardrails for strict domain compliance",
                tools=["Pydantic"]
            ),
        ],
        github_url="https://github.com/Zayed-2211/Secure-Agentic-CRAG",
        period=None,
        original_latex="\\resumeProjectHeading{\\textbf{Secure Agentic CRAG}}...",
    )


@pytest.fixture
def private_project():
    return ParsedCVProject(
        name="Internal Retail Analytics Dashboard",
        description="Power BI dashboard for retail sales trend analysis.",
        tech_stack=["Power BI", "Python", "SQL"],
        domains=["FinTech", "Retail"],
        highlights=[
            ProjectHighlight(text="Built real-time dashboard for 50+ stores", tools=["Power BI", "SQL"])
        ],
        github_url=None,
        period="Jun 2024 - Nov 2024",
        original_latex="\\resumeProjectHeading{\\textbf{Internal Retail Dashboard}}...",
    )


@pytest.fixture
def existing_projects_json(tmp_path) -> Path:
    data = [
        {
            "_comment": "=== MANUAL PROJECTS FILE ===",
            "_instructions": ["Add projects here."]
        },
        {
            "name": "Internal Retail Analytics Dashboard",
            "description": "Power BI dashboard for retail.",
            "tech_stack": ["Power BI"],
            "domains": ["Retail"],
            "highlights": [{"text": "Built real-time dashboard", "tools": ["Power BI"]}],
            "github_url": None,
            "period": "2024",
            "original_latex": "RAW TEX",
        }
    ]
    p = tmp_path / "my_projects.json"
    p.write_text(json.dumps(data, indent=4), encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------

class TestParsedCVProject:
    def test_full_project_valid(self, sample_project):
        assert sample_project.name == "Secure Agentic CRAG"
        assert "LangGraph" in sample_project.tech_stack
        assert sample_project.github_url is not None

    def test_private_project_no_github(self, private_project):
        assert private_project.github_url is None
        assert private_project.period == "Jun 2024 - Nov 2024"

    def test_defaults_are_lists(self):
        p = ParsedCVProject(name="Minimal", description="A project.", original_latex="RAW")
        assert isinstance(p.tech_stack, list)
        assert isinstance(p.domains, list)
        assert isinstance(p.highlights, list)
        assert p.github_url is None
        assert p.period is None

    def test_extraction_result_wrapper(self, sample_project, private_project):
        result = CVProjectExtractionResult(projects=[sample_project, private_project])
        assert len(result.projects) == 2

    def test_empty_extraction_result(self):
        result = CVProjectExtractionResult(projects=[])
        assert result.projects == []


# ---------------------------------------------------------------------------
# Sync logic helpers (extracted inline to avoid importing the full script)
# ---------------------------------------------------------------------------

def _is_placeholder(entry: dict) -> bool:
    return "_comment" in entry or "_instructions" in entry


def _names_similar(a: str, b: str, threshold: float = 0.85) -> bool:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio() >= threshold


def _is_duplicate(name: str, existing: list[str], threshold: float = 0.85) -> bool:
    return any(_names_similar(name, e, threshold) for e in existing)


def _is_real_repo_url(url):
    """Import the real implementation from the sync script."""
    import importlib.util
    from pathlib import Path
    script = Path(__file__).resolve().parent.parent.parent / "scripts" / "sync_cv_projects.py"
    spec = importlib.util.spec_from_file_location("sync_cv_projects", script)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.is_real_repo_url(url)


class TestDuplicateDetection:
    def test_exact_match_is_duplicate(self):
        assert _is_duplicate("My RAG Chatbot", ["my rag chatbot"])

    def test_case_insensitive(self):
        assert _is_duplicate("Secure Agentic CRAG", ["secure agentic crag"])

    def test_near_match_is_duplicate(self):
        # 90%+ similar
        assert _is_duplicate("Video to Video Translation", ["Video-to-Video Translation"])

    def test_different_name_not_duplicate(self):
        assert not _is_duplicate("New Unique Project", ["completely different thing"])

    def test_empty_existing_list(self):
        assert not _is_duplicate("Any Name", [])


class TestPlaceholderDetection:
    def test_comment_entry_is_placeholder(self):
        assert _is_placeholder({"_comment": "header", "_instructions": []})

    def test_real_project_not_placeholder(self):
        assert not _is_placeholder({"name": "My Project", "description": "desc"})

    def test_partial_placeholder_key(self):
        assert _is_placeholder({"_instructions": ["some instruction"]})


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

class TestIsRealRepoUrl:
    """Tests for the GitHub URL validator — the core fix."""

    def test_real_repo_url_is_true(self):
        assert _is_real_repo_url("https://github.com/Zayed-2211/Secure-Agentic-CRAG")

    def test_profile_root_with_trailing_slash_is_false(self):
        # This is the exact case from the user's CV for Video to Video Translation
        assert not _is_real_repo_url("https://github.com/Zayed-2211/")

    def test_profile_root_without_trailing_slash_is_false(self):
        assert not _is_real_repo_url("https://github.com/Zayed-2211")

    def test_none_is_false(self):
        assert not _is_real_repo_url(None)

    def test_empty_string_is_false(self):
        assert not _is_real_repo_url("")

    def test_non_github_url_is_false(self):
        assert not _is_real_repo_url("https://gitlab.com/user/repo")

    def test_deep_repo_path_is_true(self):
        # e.g. github.com/user/repo/tree/main — still a real repo
        assert _is_real_repo_url("https://github.com/user/repo/tree/main")


class TestProjectSerialization:
    def test_project_to_dict(self, private_project):
        d = {
            "name": private_project.name,
            "description": private_project.description,
            "tech_stack": private_project.tech_stack,
            "domains": private_project.domains,
            "highlights": [h.model_dump() for h in private_project.highlights],
            "github_url": private_project.github_url,
            "period": private_project.period,
            "original_latex": private_project.original_latex,
        }
        assert d["name"] == "Internal Retail Analytics Dashboard"
        assert d["github_url"] is None
        assert d["highlights"][0]["tools"] == ["Power BI", "SQL"]
        # Verify it round-trips through JSON cleanly
        serialised = json.dumps(d, ensure_ascii=False)
        loaded = json.loads(serialised)
        assert loaded["name"] == d["name"]
