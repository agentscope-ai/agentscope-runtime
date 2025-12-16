# -*- coding: utf-8 -*-
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import timedelta
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from typing import Any

import pytest


def _load_mcp_utils_module() -> Any:
    root = Path(__file__).resolve().parents[2]
    path = root / "src/agentscope_runtime/sandbox/box/shared/routers/mcp_utils.py"
    spec = spec_from_file_location("agentscope_runtime_test_mcp_utils", path)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.asyncio
async def test_streamable_http_timeout_coerces_timedelta() -> None:
    mcp_utils = _load_mcp_utils_module()

    seen: dict[str, Any] = {}

    @asynccontextmanager
    async def fake_streamablehttp_client(
        *,
        url: str,  # noqa: ARG001
        headers: dict[str, Any] | None = None,  # noqa: ARG001
        timeout: Any = None,
        sse_read_timeout: Any = None,
        **kwargs: Any,  # noqa: ARG001
    ):
        seen["timeout"] = timeout
        seen["sse_read_timeout"] = sse_read_timeout
        yield (object(), object(), (lambda: None))

    class FakeClientSession:
        def __init__(self, *streams: Any) -> None:  # noqa: ARG002
            pass

        async def __aenter__(self) -> "FakeClientSession":
            return self

        async def __aexit__(self, exc_type, exc, tb) -> bool:  # noqa: ANN001, ARG002
            return False

        async def initialize(self) -> None:
            return None

    mcp_utils.streamablehttp_client = fake_streamablehttp_client
    mcp_utils.ClientSession = FakeClientSession

    handler = mcp_utils.MCPSessionHandler(
        "sandbox_mcp_server",
        {
            "type": "streamable_http",
            "url": "http://127.0.0.1:18000/mcp",
            "timeout": 10,
            "sse_read_timeout": 5.5,
        },
    )
    await handler.initialize()

    assert isinstance(seen["timeout"], timedelta)
    assert seen["timeout"].total_seconds() == pytest.approx(10.0)
    assert isinstance(seen["sse_read_timeout"], timedelta)
    assert seen["sse_read_timeout"].total_seconds() == pytest.approx(5.5)

