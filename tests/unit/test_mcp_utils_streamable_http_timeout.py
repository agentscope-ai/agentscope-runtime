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
    path = root / Path(
        "src/agentscope_runtime/sandbox/box/shared/routers/mcp_utils.py",
    )
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
        url: str,
        headers: dict[str, Any] | None = None,
        timeout: Any = None,
        sse_read_timeout: Any = None,
        **kwargs: Any,
    ):
        seen["url"] = url
        seen["headers"] = headers
        seen["kwargs"] = kwargs
        seen["timeout"] = timeout
        seen["sse_read_timeout"] = sse_read_timeout
        yield (object(), object(), (lambda: None))

    class FakeClientSession:
        def __init__(self, *streams: Any) -> None:  # noqa: ARG002
            pass

        async def __aenter__(self) -> "FakeClientSession":
            return self

        async def __aexit__(
            self,
            exc_type,
            exc,
            tb,
        ) -> bool:  # noqa: ANN001, ARG002
            return False

        async def initialize(self) -> None:
            return None

    mcp_utils.streamablehttp_client = fake_streamablehttp_client
    mcp_utils.ClientSession = FakeClientSession

    async def run_case(config: dict[str, Any]) -> tuple[timedelta, timedelta]:
        seen.clear()
        handler = mcp_utils.MCPSessionHandler("sandbox_mcp_server", config)
        await handler.initialize()
        return seen["timeout"], seen["sse_read_timeout"]

    timeout, sse_read_timeout = await run_case(
        {
            "type": "streamable_http",
            "url": "http://127.0.0.1:18000/mcp",
            "timeout": 10,
            "sse_read_timeout": 5.5,
        },
    )
    assert isinstance(timeout, timedelta)
    assert timeout.total_seconds() == pytest.approx(10.0)
    assert isinstance(sse_read_timeout, timedelta)
    assert sse_read_timeout.total_seconds() == pytest.approx(5.5)

    original_timeout = timedelta(seconds=12)
    original_sse_timeout = timedelta(seconds=34)
    timeout, sse_read_timeout = await run_case(
        {
            "type": "streamable_http",
            "url": "http://127.0.0.1:18000/mcp",
            "timeout": original_timeout,
            "sse_read_timeout": original_sse_timeout,
        },
    )
    assert timeout is original_timeout
    assert sse_read_timeout is original_sse_timeout

    timeout, sse_read_timeout = await run_case(
        {
            "type": "streamable_http",
            "url": "http://127.0.0.1:18000/mcp",
        },
    )
    assert timeout.total_seconds() == pytest.approx(30.0)
    assert sse_read_timeout.total_seconds() == pytest.approx(300.0)

    timeout, sse_read_timeout = await run_case(
        {
            "type": "streamable_http",
            "url": "http://127.0.0.1:18000/mcp",
            "timeout": "not-a-number",
            "sse_read_timeout": "also-not-a-number",
        },
    )
    assert timeout.total_seconds() == pytest.approx(30.0)
    assert sse_read_timeout.total_seconds() == pytest.approx(300.0)
