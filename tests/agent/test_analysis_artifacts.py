"""
Tests for agent-run intelligence artifacts written by analysis_node.
"""

import json
import shutil
from pathlib import Path

import src.agent.intelligence_artifacts as artifacts
import src.agent.nodes.analysis_node as analysis_module
from src.agent.state import initial_state


class _FakeModel:
    def __init__(self, payload: dict):
        self._payload = payload
        for key, value in payload.items():
            setattr(self, key, value)

    def model_dump(self) -> dict:
        return self._payload


class _FakeParsedJob:
    def __init__(self):
        self.scout = _FakeModel({"is_job_posting": True, "company_name": "ACME"})
        self.intelligence = _FakeModel({"tech_stack": ["Python"]})
        self.record_type = "job_posting"
        self.parse_error = None
        self.model_used = "test-model"


def test_analysis_node_writes_parsed_jobs_file(monkeypatch):
    data_dir = Path("data/test_analysis_artifacts")
    shutil.rmtree(data_dir, ignore_errors=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(artifacts, "DATA_DIR", data_dir)
    monkeypatch.setattr(analysis_module, "_get_parser", lambda: type("P", (), {"parse": lambda self, record: _FakeParsedJob()})())

    artifacts.prepare_agent_run("analysis-test", mode="pipeline")
    try:
        state = initial_state(raw_record={"job_uid": "job-1", "title": "AI Engineer"})
        result = analysis_module.analysis_node(state)

        assert result["current_job"]["scout"]["is_job_posting"] is True

        day_dir = data_dir / "intelligence"
        day_dir = next(day_dir.iterdir())
        parsed_jobs = json.loads((day_dir / "parsed_jobs.json").read_text(encoding="utf-8"))
        assert len(parsed_jobs) == 1
        assert parsed_jobs[0]["job_uid"] == "job-1"
    finally:
        artifacts.clear_agent_run()
        shutil.rmtree(data_dir, ignore_errors=True)
