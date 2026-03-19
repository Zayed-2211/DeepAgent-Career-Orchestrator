"""
Tests for Phase 6.5 — Full-Pipeline Loop Logic.

Covers:
  - loop_controller_node: queue pop, counter increment, routing
  - loop_controller_node: empty queue → "done" routing
  - scout_node: MOCK_SCRAPER mode with fixture file
  - scout_node: missing fixture file → success with empty list
  - dispatch_node: routing is now "loop" (not END)
  - intake_node: skip routing is now "loop" (not "skip")
  - pipeline_stats accumulation across 2 loop iterations
  - state.initial_state: job_queue pre-loaded from raw_record
  - state.pipeline_initial_state: empty queue
  - build_pipeline_graph compile check (9 nodes present)
  - build_single_job_graph compile check (7 nodes present)
"""

import json
import os
from pathlib import Path

import pytest

from src.agent.state import (
    AgentState,
    CURRENT_SCHEMA_VERSION,
    initial_state,
    pipeline_initial_state,
)


# ---------------------------------------------------------------------------
# State helpers
# ---------------------------------------------------------------------------

class TestStateHelpers:
    def test_current_schema_version_is_2(self):
        assert CURRENT_SCHEMA_VERSION == 2

    def test_initial_state_preloads_queue(self):
        record = {"job_uid": "x:1", "title": "Eng"}
        state = initial_state(raw_record=record)
        assert state["job_queue"] == [record]
        assert state["current_job"] == record
        assert state["current_job_index"] == 0
        assert state["pipeline_stats"]["total"] == 0

    def test_initial_state_no_record(self):
        state = initial_state()
        assert state["job_queue"] == []
        assert state["current_job"] == {}

    def test_pipeline_initial_state(self):
        state = pipeline_initial_state()
        assert state["raw_records"] == []
        assert state["job_queue"] == []
        assert state["schema_version"] == CURRENT_SCHEMA_VERSION


# ---------------------------------------------------------------------------
# loop_controller_node
# ---------------------------------------------------------------------------

from src.agent.nodes.loop_controller_node import (
    loop_controller_node,
    route_after_loop_controller,
)


class TestLoopControllerNode:
    def _base_state(self, queue: list) -> AgentState:
        s = initial_state()
        s["job_queue"] = queue
        s["current_job_index"] = 0
        s["pipeline_stats"] = {"total": len(queue), "approved": 0, "rejected": 0, "skipped": 0, "errors": 0}
        return s

    def test_empty_queue_routes_done(self):
        state = self._base_state([])
        result = loop_controller_node(state)
        assert result["routing"] == "done"
        assert route_after_loop_controller(result) == "done"

    def test_empty_queue_with_dev_limit_does_not_crash(self, monkeypatch):
        monkeypatch.setenv("DEV_MODE_LIMIT", "5")
        state = self._base_state([])
        result = loop_controller_node(state)
        assert result["routing"] == "done"

    def test_non_empty_queue_pops_first_record(self):
        job_a = {"job_uid": "a:1", "raw_title": "ML Eng"}
        job_b = {"job_uid": "b:2", "raw_title": "AI Eng"}
        state = self._base_state([job_a, job_b])
        result = loop_controller_node(state)

        assert result["routing"] == "next_job"
        assert result["current_job"] == job_a          # first was popped
        assert len(result["job_queue"]) == 1           # one remaining
        assert result["job_queue"][0] == job_b          # b is still there
        assert result["current_job_index"] == 1        # counter incremented

    def test_single_item_queue_leaves_empty_after_pop(self):
        job = {"job_uid": "c:3", "raw_title": "SWE"}
        state = self._base_state([job])
        result = loop_controller_node(state)

        assert result["current_job"] == job
        assert result["job_queue"] == []
        assert result["current_job_index"] == 1

    def test_per_job_fields_reset_after_pop(self):
        """loop_controller must reset per-job fields so previous iteration doesn't bleed in."""
        state = self._base_state([{"job_uid": "d:4", "title": "X"}])
        # Simulate dirty state from previous iteration
        state["human_decision"] = "approve"
        state["match_score"] = 0.95
        state["matched_projects"] = [{"name": "OldProject"}]

        result = loop_controller_node(state)
        assert result["human_decision"] == "pending"
        assert result["match_score"] == 0.0
        assert result["matched_projects"] == []

    def test_route_after_loop_controller_next_job(self):
        state = initial_state()
        state["routing"] = "next_job"
        assert route_after_loop_controller(state) == "next_job"

    def test_route_after_loop_controller_done(self):
        state = initial_state()
        state["routing"] = "done"
        assert route_after_loop_controller(state) == "done"


# ---------------------------------------------------------------------------
# scout_node — MOCK_SCRAPER mode
# ---------------------------------------------------------------------------

from src.agent.nodes.scout_node import scout_node, route_after_scout


class TestScoutNode:
    def test_mock_scraper_loads_from_file(self, tmp_path, monkeypatch):
        fixture = [{"job_uid": "x:1", "title": "AI Eng"}]
        f = tmp_path / "raw.json"
        f.write_text(json.dumps(fixture))

        monkeypatch.setenv("MOCK_SCRAPER", "1")
        monkeypatch.setenv("MOCK_SCRAPER_FILE", str(f))

        state = pipeline_initial_state()
        result = scout_node(state)

        assert result["routing"] == "success"
        assert result["raw_records"] == fixture

    def test_mock_scraper_missing_file_returns_empty(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MOCK_SCRAPER", "1")
        monkeypatch.setenv("MOCK_SCRAPER_FILE", str(tmp_path / "missing.json"))

        state = pipeline_initial_state()
        result = scout_node(state)

        assert result["routing"] == "success"
        assert result["raw_records"] == []

    def test_route_after_scout_success(self):
        state = pipeline_initial_state()
        state["routing"] = "success"
        assert route_after_scout(state) == "success"

    def test_route_after_scout_error(self):
        state = pipeline_initial_state()
        state["routing"] = "error"
        assert route_after_scout(state) == "error"


# ---------------------------------------------------------------------------
# intake_node — skip now routes to "loop"
# ---------------------------------------------------------------------------

from src.agent.nodes.intake_node import intake_node, route_after_intake


class TestIntakeNodePhase65:
    def test_skip_routes_to_loop_not_end(self, monkeypatch):
        """intake_node skip routing must return 'loop' for the batch to continue."""
        monkeypatch.setattr(
            "src.agent.nodes.intake_node.DBManager",
            _MockDBManager(exists_return=True),
        )
        record = {"job_uid": "dup:999", "platform": "linkedin_posts", "title": "Dup"}
        state = initial_state(raw_record=record)
        result = intake_node(state)

        assert result["routing"] == "loop"
        assert route_after_intake(result) == "loop"

    def test_skip_increments_skipped_stats(self, monkeypatch):
        monkeypatch.setattr(
            "src.agent.nodes.intake_node.DBManager",
            _MockDBManager(exists_return=True),
        )
        state = initial_state(raw_record={"job_uid": "dup:111", "title": "X"})
        state["pipeline_stats"] = {"skipped": 2, "approved": 1, "rejected": 0, "total": 10, "errors": 0}
        result = intake_node(state)

        assert result["pipeline_stats"]["skipped"] == 3


# ---------------------------------------------------------------------------
# dispatch_node — routing should be "loop", stats should accumulate
# ---------------------------------------------------------------------------

from src.agent.nodes.dispatch_node import dispatch_node


class TestDispatchNodePhase65:
    def test_approve_routing_is_loop(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.agent.nodes.dispatch_node._OUTPUTS_DIR", tmp_path)
        state = initial_state(raw_record={"scout": {}, "intelligence": {}})
        state["job_uid"] = "loop:approve:1"
        state["human_decision"] = "approve"
        state["matched_projects"] = []
        state["match_score"] = 0.5
        state["todo_list"] = []

        result = dispatch_node(state)
        assert result["routing"] == "loop"

    def test_reject_routing_is_loop(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.agent.nodes.dispatch_node._OUTPUTS_DIR", tmp_path)
        state = initial_state(raw_record={"scout": {}, "intelligence": {}})
        state["job_uid"] = "loop:reject:2"
        state["human_decision"] = "reject"
        state["matched_projects"] = []
        state["match_score"] = 0.1
        state["todo_list"] = []

        result = dispatch_node(state)
        assert result["routing"] == "loop"

    def test_approve_increments_approved_stats(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.agent.nodes.dispatch_node._OUTPUTS_DIR", tmp_path)
        state = initial_state(raw_record={"scout": {}, "intelligence": {}})
        state["job_uid"] = "stats:approve"
        state["human_decision"] = "approve"
        state["matched_projects"] = []
        state["match_score"] = 0.7
        state["todo_list"] = []
        state["pipeline_stats"] = {"approved": 1, "rejected": 0, "skipped": 0, "total": 5, "errors": 0}

        result = dispatch_node(state)
        assert result["pipeline_stats"]["approved"] == 2

    def test_reject_increments_rejected_stats(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.agent.nodes.dispatch_node._OUTPUTS_DIR", tmp_path)
        state = initial_state(raw_record={"scout": {}, "intelligence": {}})
        state["job_uid"] = "stats:reject"
        state["human_decision"] = "reject"
        state["matched_projects"] = []
        state["match_score"] = 0.2
        state["todo_list"] = []
        state["pipeline_stats"] = {"approved": 0, "rejected": 2, "skipped": 1, "total": 5, "errors": 0}

        result = dispatch_node(state)
        assert result["pipeline_stats"]["rejected"] == 3


# ---------------------------------------------------------------------------
# Graph compile checks
# ---------------------------------------------------------------------------

class TestGraphCompilePhase65:
    def test_pipeline_graph_compiles(self):
        from src.agent.graph import pipeline_graph
        assert pipeline_graph is not None

    def test_single_job_graph_compiles(self):
        from src.agent.graph import single_job_graph
        assert single_job_graph is not None

    def test_pipeline_graph_has_all_9_nodes(self):
        from src.agent.graph import pipeline_graph
        nodes_str = str(pipeline_graph.get_graph().nodes)
        expected = ["scout", "dedup", "loop_controller", "intake",
                    "analysis", "matching", "planning", "review", "dispatch"]
        for node in expected:
            assert node in nodes_str, f"Node '{node}' missing from pipeline graph"

    def test_single_job_graph_has_7_nodes(self):
        from src.agent.graph import single_job_graph
        nodes_str = str(single_job_graph.get_graph().nodes)
        expected = ["loop_controller", "intake", "analysis",
                    "matching", "planning", "review", "dispatch"]
        for node in expected:
            assert node in nodes_str, f"Node '{node}' missing from single-job graph"

    def test_compiled_graph_alias_is_single_job(self):
        from src.agent.graph import compiled_graph, single_job_graph
        assert compiled_graph is single_job_graph


# ---------------------------------------------------------------------------
# Test helper (DB mock)
# ---------------------------------------------------------------------------

class _MockDB:
    def __enter__(self): return self
    def __exit__(self, *a): pass


class _MockDBManager:
    def __init__(self, exists_return: bool):
        self._return = exists_return

    def __call__(self):
        manager = self
        class _M:
            def connect(self_): return _MockDB()
            def exists(self_, conn, table, col, val): return manager._return
        return _M()
