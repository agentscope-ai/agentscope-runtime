# -*- coding: utf-8 -*-
"""Helpers for working with AgentApp objects inside deployers."""

from __future__ import annotations

from typing import Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from ...runner import Runner


def ensure_runner_from_app(app: Any) -> Optional["Runner"]:
    """Return a Runner extracted from an AgentApp instance.

    Builds the runner lazily if the app hasn't initialized it yet.
    """
    if app is None:
        return None

    runner = getattr(app, "_runner", None)
    if runner is not None:
        return runner

    build_runner = getattr(app, "_build_runner", None)
    if callable(build_runner):
        build_runner()
        runner = getattr(app, "_runner", None)

    return runner
