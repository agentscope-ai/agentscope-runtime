# -*- coding: utf-8 -*-
# pylint:disable=protected-access

from agentscope_runtime.engine.deployers.utils.app_runner_utils import (
    ensure_runner_from_app,
)


class DummyRunner:
    """Simple runner stand-in for tests."""


class DummyApp:
    """Minimal AgentApp stand-in."""

    def __init__(self):
        self._runner = None
        self._build_invocations = 0

    def _build_runner(self):
        self._build_invocations += 1
        self._runner = DummyRunner()


def test_ensure_runner_returns_existing_instance():
    """Existing runner should be returned without rebuilding."""
    app = DummyApp()
    app._runner = DummyRunner()

    result = ensure_runner_from_app(app)

    assert isinstance(result, DummyRunner)
    assert app._build_invocations == 0


def test_ensure_runner_builds_when_missing():
    """Runner should be constructed lazily when absent."""
    app = DummyApp()

    result = ensure_runner_from_app(app)

    assert isinstance(result, DummyRunner)
    assert app._build_invocations == 1


def test_ensure_runner_handles_none_input():
    """None input should return None."""
    assert ensure_runner_from_app(None) is None
