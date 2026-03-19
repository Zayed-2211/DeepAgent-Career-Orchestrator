"""
Tests for Phase 6 — LangGraph Agent Graph.

Tests cover:
  - AgentState initialization
  - intake_node: skip routing for known UIDs, continue for new ones
  - matching_node: keyword overlap scoring
  - planning_node: todo list creation
  - dispatch_node: approve/reject output creation
  - graph: full compile check (no runtime exceptions)
  - Tool units: todo_tool, disk_tool, search_tool
"""

import json
from pathlib import Path

import pytest

# ── Agent state ────────────────────────────────────────────────────────────────
from src.agent.state import AgentState, initial_state, CURRENT_SCHEMA_VERSION


class TestAgentState:
    def test_initial_state_defaults(self):
        state = initial_state()
        assert state["schema_version"] == CURRENT_SCHEMA_VERSION
        assert state["human_decision"] == "pending"
        assert state["routing"] == "continue"
        assert state["matched_projects"] == []
        assert state["match_score"] == 0.0
        assert state["todo_list"] == []
        assert state["error"] is None

    def test_initial_state_with_record(self):
        record = {"job_uid": "test:123", "title": "ML Engineer"}
        state = initial_state(raw_record=record)
        assert state["current_job"]["job_uid"] == "test:123"


# ── Tools — todo_tool ──────────────────────────────────────────────────────────
from src.agent.tools.todo_tool import (
    create_todo, mark_done, get_pending, get_done, progress, format_list
)


class TestTodoTool:
    def test_create_todo_all_pending(self):
        items = create_todo(["Task A", "Task B"])
        assert all(i.startswith("⬜") for i in items)

    def test_create_todo_all_done(self):
        items = create_todo(["Task A"], done=True)
        assert items[0].startswith("✓")

    def test_mark_done_finds_substring(self):
        items = create_todo(["Extract info", "Draft CV"])
        items = mark_done(items, "Extract")
        assert items[0].startswith("✓")
        assert items[1].startswith("⬜")

    def test_get_pending_only_returns_pending(self):
        items = create_todo(["A", "B", "C"])
        items = mark_done(items, "A")
        pending = get_pending(items)
        assert len(pending) == 2
        assert all(i.startswith("⬜") for i in pending)

    def test_get_done(self):
        items = create_todo(["A", "B"])
        items = mark_done(items, "A")
        done = get_done(items)
        assert len(done) == 1

    def test_progress_string(self):
        items = create_todo(["A", "B", "C", "D"])
        items = mark_done(items, "A")
        items = mark_done(items, "B")
        p = progress(items)
        assert p == "2/4 tasks completed"

    def test_format_list(self):
        items = create_todo(["A"])
        out = format_list(items)
        assert "A" in out


# ── Tools — disk_tool ──────────────────────────────────────────────────────────
from src.agent.tools.disk_tool import read_json, write_json


class TestDiskTool:
    def test_write_and_read_json(self, tmp_path):
        p = tmp_path / "test.json"
        data = {"key": "value", "num": 42}
        assert write_json(p, data)
        loaded = read_json(p)
        assert loaded == data

    def test_read_missing_returns_none(self, tmp_path):
        result = read_json(tmp_path / "nonexistent.json")
        assert result is None

    def test_write_creates_parent_dirs(self, tmp_path):
        p = tmp_path / "nested" / "dir" / "file.json"
        assert write_json(p, {"a": 1})
        assert p.exists()


# ── Tools — search_tool ───────────────────────────────────────────────────────
from src.agent.tools.search_tool import (
    _extract_keywords, score_project, search_projects, overall_match_score
)


SAMPLE_PROJECT = {
    "name": "LangGraph CRAG Agent",
    "description": "A stateful RAG agent built with LangGraph and Gemini.",
    "tech_stack": ["LangGraph", "Python", "Gemini", "Pinecone"],
    "domains": ["AI", "NLP"],
    "highlights": [
        {"text": "Built stateful workflow", "tools": ["LangGraph"]},
        {"text": "Integrated Gemini 1.5", "tools": ["Gemini"]},
    ],
}

SAMPLE_JOB = {
    "raw_title": "AI Engineer",
    "intelligence": {
        "tech_stack": ["Python", "LangGraph", "FastAPI"],
        "technical_skills": ["RAG", "Agentic AI"],
        "specializations": ["LLM Fine-tuning"],
    },
    "scout": {"company_name": "TestCo"},
}


class TestSearchTool:
    def test_extract_keywords_from_intelligence(self):
        kw = _extract_keywords(SAMPLE_JOB)
        assert "python" in kw
        assert "langgraph" in kw
        assert "rag" in kw

    def test_extract_keywords_fallback_to_title(self):
        job = {"raw_title": "Senior Python Developer"}
        kw = _extract_keywords(job)
        assert "python" in kw

    def test_score_project_perfect_match(self):
        job_kw = {"python", "langgraph", "gemini"}
        score = score_project(SAMPLE_PROJECT, job_kw)
        assert score == 1.0  # all 3 job keywords in project

    def test_score_project_no_match(self):
        job_kw = {"java", "spring", "kafka"}
        score = score_project(SAMPLE_PROJECT, job_kw)
        assert score == 0.0

    def test_score_project_partial_match(self):
        job_kw = {"python", "java"}
        score = score_project(SAMPLE_PROJECT, job_kw)
        assert 0.0 < score < 1.0

    def test_search_projects_with_fixture(self, tmp_path):
        projects_file = tmp_path / "my_projects.json"
        projects_file.write_text(json.dumps([SAMPLE_PROJECT]), encoding="utf-8")
        results = search_projects(SAMPLE_JOB, top_k=3, projects_file=projects_file)
        assert len(results) == 1
        assert results[0]["name"] == "LangGraph CRAG Agent"
        assert results[0]["_match_score"] > 0.0

    def test_search_projects_missing_file(self, tmp_path):
        results = search_projects(SAMPLE_JOB, projects_file=tmp_path / "missing.json")
        assert results == []

    def test_overall_match_score(self):
        projects = [
            {"_match_score": 0.8},
            {"_match_score": 0.6},
            {"_match_score": 0.4},
        ]
        score = overall_match_score(projects)
        # 0.8*0.6 + 0.6*0.3 + 0.4*0.1 = 0.48+0.18+0.04 = 0.70
        assert abs(score - 0.70) < 0.01

    def test_overall_match_score_empty(self):
        assert overall_match_score([]) == 0.0


# ── Node — intake_node ────────────────────────────────────────────────────────
from src.agent.nodes.intake_node import intake_node, route_after_intake


class TestIntakeNode:
    def test_new_job_routes_continue(self, monkeypatch):
        # Monkeypatch DBManager.exists to return False (not a duplicate)
        monkeypatch.setattr(
            "src.agent.nodes.intake_node.DBManager",
            _MockDBManager(exists_return=False),
        )
        record = {
            "job_uid": "test:9999999",
            "platform": "linkedin_posts",
            "job_url": "https://linkedin.com/feed/update/urn:li:activity:9999999",
            "title": "ML Engineer",
        }
        state = initial_state(raw_record=record)
        result = intake_node(state)
        assert result["routing"] == "continue"
        assert route_after_intake(result) == "continue"

    def test_duplicate_job_routes_loop(self, monkeypatch):
        """Phase 6.5: duplicate skip now routes to 'loop' to keep the batch going."""
        monkeypatch.setattr(
            "src.agent.nodes.intake_node.DBManager",
            _MockDBManager(exists_return=True),
        )
        record = {"job_uid": "test:111", "platform": "linkedin_posts", "title": "Dup"}
        state = initial_state(raw_record=record)
        result = intake_node(state)
        assert result["routing"] == "loop"
        assert route_after_intake(result) == "loop"


# ── Node — planning_node ──────────────────────────────────────────────────────
from src.agent.nodes.planning_node import planning_node


class TestPlanningNode:
    def test_planning_creates_todo_list(self):
        state = initial_state(raw_record={
            "scout": {"is_job_posting": True, "company_name": "AcmeCorp"},
            "intelligence": {},
        })
        state["matched_projects"] = [{"name": "P1", "_match_score": 0.7}]
        state["match_score"] = 0.7
        result = planning_node(state)
        assert len(result["todo_list"]) > 0
        # Some items should be marked done (intake + analysis + matching)
        done = [i for i in result["todo_list"] if i.startswith("✓")]
        assert len(done) >= 1


# ── Node — dispatch_node ──────────────────────────────────────────────────────
from src.agent.nodes.dispatch_node import dispatch_node


class TestDispatchNode:
    def test_approve_writes_dispatch_json(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "src.agent.nodes.dispatch_node._OUTPUTS_DIR", tmp_path / "outputs"
        )
        state = initial_state(raw_record={
            "scout": {"company_name": "AcmeCorp"},
            "intelligence": {"tech_stack": ["Python"]},
        })
        state["job_uid"] = "test:approve123"
        state["human_decision"] = "approve"
        state["matched_projects"] = []
        state["match_score"] = 0.5
        state["todo_list"] = []

        result = dispatch_node(state)
        assert "dispatch" in result["generated_docs"]
        path = Path(result["generated_docs"]["dispatch"])
        assert path.exists()
        data = json.loads(path.read_text())
        assert data["status"] == "approved"

    def test_reject_writes_archived_json(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "src.agent.nodes.dispatch_node._OUTPUTS_DIR", tmp_path / "outputs"
        )
        state = initial_state(raw_record={"scout": {}, "intelligence": {}})
        state["job_uid"] = "test:reject456"
        state["human_decision"] = "reject"
        state["matched_projects"] = []
        state["match_score"] = 0.1
        state["todo_list"] = []

        result = dispatch_node(state)
        assert "archived" in result["generated_docs"]
        path = Path(result["generated_docs"]["archived"])
        assert path.exists()
        data = json.loads(path.read_text())
        assert data["status"] == "rejected"


# ── Graph compile check ────────────────────────────────────────────────────────
class TestGraphCompile:
    def test_compiled_graph_exists(self):
        from src.agent.graph import compiled_graph
        assert compiled_graph is not None

    def test_graph_has_expected_nodes(self):
        from src.agent.graph import compiled_graph
        graph_repr = str(compiled_graph.get_graph().nodes)
        for node in ("intake", "analysis", "matching", "planning", "review", "dispatch"):
            assert node in graph_repr, f"Node '{node}' missing from graph"


# ── Test helper ───────────────────────────────────────────────────────────────

class _MockDB:
    """Minimal mock of sqlite3 connection context."""
    def __enter__(self):
        return self
    def __exit__(self, *a):
        pass


class _MockDBManager:
    """Monkeypatch factory for DBManager — controls exists() return value."""
    def __init__(self, exists_return: bool):
        self._return = exists_return

    def __call__(self):
        manager = self
        class _M:
            def connect(self_):
                return _MockDB()
            def exists(self_, conn, table, col, val):
                return manager._return
        return _M()
