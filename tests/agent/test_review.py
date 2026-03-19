"""
Tests for unattended review node behavior.
"""

import src.agent.nodes.review_node as review_module
from src.agent.state import initial_state


def test_review_node_auto_approves():
    state = initial_state(raw_record={"title": "AI Engineer"})
    result = review_module.review_node(state)
    assert result["human_decision"] == "approve"
    assert result["routing"] == "approve"


def test_review_node_does_not_read_console_input(monkeypatch):
    def _fail_if_called(*args, **kwargs):
        raise AssertionError("console.input must not be called in unattended mode")

    monkeypatch.setattr(review_module.console, "input", _fail_if_called)
    state = initial_state(raw_record={"title": "Data Engineer"})
    result = review_module.review_node(state)
    assert result["human_decision"] == "approve"
    assert result["routing"] == "approve"
