"""
Mode-level tests for scripts/run_agent.py.
"""

import os
import shutil
import sys
import types
from datetime import date
from pathlib import Path

import scripts.run_agent as run_agent
import src.agent.intelligence_artifacts as artifacts


def _install_fake_agent_modules(monkeypatch):
    fake_pipeline_graph = types.SimpleNamespace(
        invoke=lambda state, config: {
            "pipeline_stats": {"total": 0, "approved": 0, "rejected": 0, "skipped": 0}
        }
    )
    fake_single_job_graph = types.SimpleNamespace(invoke=lambda state, config: state)
    fake_graph_module = types.SimpleNamespace(
        pipeline_graph=fake_pipeline_graph,
        single_job_graph=fake_single_job_graph,
        export_graph_png=lambda: None,
    )
    fake_state_module = types.SimpleNamespace(
        pipeline_initial_state=lambda: {"pipeline_stats": {}},
        initial_state=lambda raw_record=None: {
            "job_queue": [raw_record] if raw_record else [],
            "pipeline_stats": {},
        },
    )
    monkeypatch.setitem(sys.modules, "src.agent.graph", fake_graph_module)
    monkeypatch.setitem(sys.modules, "src.agent.state", fake_state_module)


def test_pipeline_mode_ignores_mock_env_and_creates_intelligence_artifacts(monkeypatch):
    _install_fake_agent_modules(monkeypatch)
    monkeypatch.setattr(run_agent, "_auto_sync_cv_projects", lambda: None)
    monkeypatch.setenv("MOCK_SCRAPER", "1")
    monkeypatch.setenv("MOCK_SCRAPER_FILE", "data/raw/fake.json")
    monkeypatch.setenv("DEV_FORCE_RESCRAPE", "1")

    data_dir = Path("data/test_run_agent_temp")
    shutil.rmtree(data_dir, ignore_errors=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(artifacts, "DATA_DIR", data_dir)

    try:
        run_agent.run_pipeline(dev_limit=5)

        assert os.environ.get("MOCK_SCRAPER") is None
        assert os.environ.get("MOCK_SCRAPER_FILE") is None
        assert os.environ.get("DEV_FORCE_RESCRAPE") is None

        today_dir = data_dir / "intelligence" / date.today().isoformat()
        assert today_dir.exists()
        assert (today_dir / "run_log.txt").exists()
        assert (today_dir / "run_status.json").exists()
    finally:
        artifacts.clear_agent_run()
        shutil.rmtree(data_dir, ignore_errors=True)


def test_sync_systemexit_warns_and_pipeline_continues(monkeypatch):
    _install_fake_agent_modules(monkeypatch)

    fake_sync_module = types.SimpleNamespace(
        sync_cv_projects=lambda dry_run, force: (_ for _ in ()).throw(SystemExit(2))
    )
    monkeypatch.setitem(sys.modules, "scripts.sync_cv_projects", fake_sync_module)

    warnings = []

    class _FakeLogger:
        def info(self, *args, **kwargs):
            pass

        def warning(self, message, *args, **kwargs):
            warnings.append(str(message))

        def error(self, *args, **kwargs):
            pass

    data_dir = Path("data/test_run_agent_temp")
    shutil.rmtree(data_dir, ignore_errors=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(artifacts, "DATA_DIR", data_dir)
    monkeypatch.setattr(run_agent, "logger", _FakeLogger())

    try:
        result = run_agent.run_pipeline(dev_limit=None)
        assert result["pipeline_stats"]["total"] == 0
        assert any("CV sync exited early" in msg for msg in warnings)
    finally:
        artifacts.clear_agent_run()
        shutil.rmtree(data_dir, ignore_errors=True)
