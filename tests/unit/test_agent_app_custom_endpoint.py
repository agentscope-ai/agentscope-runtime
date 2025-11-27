# -*- coding: utf-8 -*-
# pylint:disable=redefined-outer-name, unused-argument
import json
import multiprocessing
import time
from typing import List

import aiohttp
from fastapi import Request
from pydantic import BaseModel
import pytest

from agentscope_runtime.engine import AgentApp
from agentscope_runtime.engine.schemas.agent_schemas import AgentRequest

PORT = 8090


async def _collect_sse_payloads(resp: aiohttp.ClientResponse):
    """Collect streaming Server-Sent Events payloads and decode JSON."""
    buffer = ""
    payloads: List[str] = []

    async for chunk, _ in resp.content.iter_chunks():
        if not chunk:
            continue
        buffer += chunk.decode("utf-8")

        while "\n\n" in buffer:
            event, buffer = buffer.split("\n\n", 1)
            data_lines: List[str] = []
            for line in event.splitlines():
                if not line.startswith("data:"):
                    continue
                value = line[5:]
                if value.startswith(" "):
                    value = value[1:]
                data_lines.append(value)

            if data_lines:
                data_str = "\n".join(data_lines)
                payloads.append(json.loads(data_str))

    return payloads


class Messages(BaseModel):
    role: str
    content: str


def run_app():
    """Start AgentApp with streaming output enabled."""
    app = AgentApp()

    @app.endpoint("/sync")
    def sync_handler():
        return {"status": "ok"}

    @app.endpoint("/async")
    async def async_handler():
        return {"status": "ok"}

    @app.endpoint("/stream_async")
    async def stream_async_handler():
        for i in range(5):
            yield f"async chunk {i}\n"

    @app.endpoint("/stream_sync")
    def stream_sync_handler():
        for i in range(5):
            yield f"sync chunk {i}\n"

    @app.endpoint("/stream_async_error")
    async def stream_async_error_handler():
        for i in range(2):
            yield f"async chunk {i}\n"
        raise ValueError("Async streaming failure")

    @app.endpoint("/stream_sync_error")
    def stream_sync_error_handler():
        for i in range(2):
            yield f"sync chunk {i}\n"
        raise ValueError("Sync streaming failure")

    @app.endpoint(path="/stream_with_query_params")
    def stream_with_query_params_handler(first: int, second: str):
        assert first == 1
        assert second == "test"
        for i in range(5):
            yield f"sync chunk {i}, foo: {first}, bar: {second}\n"

    @app.endpoint(path="/stream_with_request")
    async def stream_with_query_params_async_handler(request: Request):
        query_params = request.query_params
        param_first = query_params.get("foo")
        param_second = query_params.get("bar")
        assert int(param_first) == 1
        assert param_second == "test"
        for i in range(5):
            yield f"async chunk {i}, foo: {param_first}, bar: {param_second}\n"

    @app.endpoint(path="/stream_with_messages")
    async def stream_with_messages_handler(messages: List[Messages]):
        for i, message in enumerate(messages):
            assert message.role == "user"
            assert message.content == f"Hello, world! {i}"
            yield f"async chunk {message.role}, message: {message.content}\n"

    @app.endpoint(path="/stream_with_agent_request")
    async def stream_with_agent_request(request: AgentRequest):
        for i in range(10):
            yield {
                "messages": "hello",
                "index": i,
            }

    @app.endpoint(path="/stream_with_agent_request_direct_return")
    async def stream_with_agent_request_direct_return(request: AgentRequest):
        return {"hello": "world"}

    app.run(host="127.0.0.1", port=PORT)


@pytest.fixture(scope="module")
def start_app():
    """Launch AgentApp in a separate process before the async tests."""
    proc = multiprocessing.Process(target=run_app)
    proc.start()
    import socket

    for _ in range(50):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.connect(("localhost", PORT))
            s.close()
            break
        except OSError:
            time.sleep(0.1)
    else:
        proc.terminate()
        pytest.fail("Server did not start within timeout")

    yield
    proc.terminate()
    proc.join()


@pytest.mark.asyncio
async def test_sync_endpoint(start_app):
    """Test /sync returns correct static JSON."""
    url = f"http://localhost:{PORT}/sync"
    async with aiohttp.ClientSession() as session:
        async with session.post(url) as resp:
            assert resp.status == 200
            data = await resp.json()
            assert data == {"status": "ok"}


@pytest.mark.asyncio
async def test_async_endpoint(start_app):
    """Test /async returns correct static JSON asynchronously."""
    url = f"http://localhost:{PORT}/async"
    async with aiohttp.ClientSession() as session:
        async with session.post(url) as resp:
            assert resp.status == 200
            data = await resp.json()
            assert data == {"status": "ok"}


@pytest.mark.asyncio
async def test_stream_async_endpoint(start_app):
    """
    Test /stream_async streaming chunks.
    """
    url = f"http://localhost:{PORT}/stream_async"
    async with aiohttp.ClientSession() as session:
        async with session.post(url) as resp:
            assert resp.status == 200
            assert resp.content_type == "text/event-stream"

            text_chunks = await _collect_sse_payloads(resp)

    assert [chunk.rstrip("\n") for chunk in text_chunks] == [
        f"async chunk {i}" for i in range(5)
    ]


@pytest.mark.asyncio
async def test_stream_sync_endpoint(start_app):
    """
    Test /stream_sync streaming chunks (sync-style handler).
    """
    url = f"http://localhost:{PORT}/stream_sync"
    async with aiohttp.ClientSession() as session:
        async with session.post(url) as resp:
            assert resp.status == 200
            assert resp.content_type == "text/event-stream"
            text_chunks = await _collect_sse_payloads(resp)

    assert [chunk.rstrip("\n") for chunk in text_chunks] == [
        f"sync chunk {i}" for i in range(5)
    ]


@pytest.mark.asyncio
async def test_stream_async_error_endpoint(start_app):
    """
    Test /stream_async_error yields SSE error payload when handler fails.
    """
    url = f"http://localhost:{PORT}/stream_async_error"
    async with aiohttp.ClientSession() as session:
        async with session.post(url) as resp:
            assert resp.status == 200
            assert resp.content_type == "text/event-stream"
            payloads = await _collect_sse_payloads(resp)

    assert [chunk.rstrip("\n") for chunk in payloads[:-1]] == [
        f"async chunk {i}" for i in range(2)
    ]
    assert payloads[-1] == {
        "error": "Async streaming failure",
        "error_type": "ValueError",
        "message": "Error in streaming generator",
    }


@pytest.mark.asyncio
async def test_stream_sync_error_endpoint(start_app):
    """
    Test /stream_sync_error yields SSE error payload when handler fails.
    """
    url = f"http://localhost:{PORT}/stream_sync_error"
    async with aiohttp.ClientSession() as session:
        async with session.post(url) as resp:
            assert resp.status == 200
            assert resp.content_type == "text/event-stream"
            payloads = await _collect_sse_payloads(resp)

    assert [chunk.rstrip("\n") for chunk in payloads[:-1]] == [
        f"sync chunk {i}" for i in range(2)
    ]
    assert payloads[-1] == {
        "error": "Sync streaming failure",
        "error_type": "ValueError",
        "message": "Error in streaming generator",
    }


@pytest.mark.asyncio
async def test_stream_with_query_params_endpoint(start_app):
    """
    Test /stream_with_query_params streaming chunks with query params.
    """
    url = (
        f"http://localhost:{PORT}/stream_with_query_params?first=1&second=test"
    )
    async with aiohttp.ClientSession() as session:
        async with session.post(url) as resp:
            assert resp.status == 200
            assert resp.content_type == "text/event-stream"
            text_chunks = await _collect_sse_payloads(resp)

    assert [chunk.rstrip("\n") for chunk in text_chunks] == [
        f"sync chunk {i}, foo: 1, bar: test" for i in range(5)
    ]


@pytest.mark.asyncio
async def test_stream_with_request_endpoint(start_app):
    """
    Test /stream_with_request streaming chunks with request.
    """
    url = f"http://localhost:{PORT}/stream_with_request?foo=1&bar=test"
    async with aiohttp.ClientSession() as session:
        async with session.post(url) as resp:
            assert resp.status == 200
            assert resp.content_type == "text/event-stream"
            text_chunks = await _collect_sse_payloads(resp)

    assert [chunk.rstrip("\n") for chunk in text_chunks] == [
        f"async chunk {i}, foo: 1, bar: test" for i in range(5)
    ]


@pytest.mark.asyncio
async def test_stream_with_messages_endpoint(start_app):
    """
    Test /stream_with_messages streaming chunks with messages.
    """
    url = f"http://localhost:{PORT}/stream_with_messages"
    async with aiohttp.ClientSession() as session:
        messages = [
            Messages(role="user", content=f"Hello, world! {i}").model_dump()
            for i in range(5)
        ]
        async with session.post(url, json=messages) as resp:
            assert resp.status == 200
            assert resp.content_type == "text/event-stream"
            text_chunks = await _collect_sse_payloads(resp)

    assert [chunk.rstrip("\n") for chunk in text_chunks] == [
        f"async chunk user, message: Hello, world! {i}" for i in range(5)
    ]


@pytest.mark.asyncio
async def test_stream_with_agent_request_endpoint(start_app):
    """
    Test /stream_with_agent_request streaming chunks with agent request.
    """
    url = f"http://localhost:{PORT}/stream_with_agent_request"
    async with aiohttp.ClientSession() as session:
        async with session.post(
            url,
            json={
                "input": [
                    {
                        "role": "user",
                        "type": "message",
                        "content": [{"type": "text", "text": "hello"}],
                    },
                    {
                        "type": "message",
                        "role": "assistant",
                        "content": [
                            {
                                "object": "content",
                                "type": "text",
                                "text": "Hello! How can I assist you today?",
                            },
                        ],
                    },
                    {
                        "role": "user",
                        "type": "message",
                        "content": [
                            {
                                "type": "text",
                                "text": "What is the capital of France?",
                            },
                        ],
                    },
                ],
                "session_id": "1764056632961",
            },
        ) as resp:
            assert resp.status == 200
            assert resp.content_type == "text/event-stream"
            text_chunks = await _collect_sse_payloads(resp)
            assert len(text_chunks) == 10


@pytest.mark.asyncio
async def test_stream_with_agent_request_direct_return_endpoint(start_app):
    """
    Test /stream_with_agent_request_direct_return endpoint
    """
    url = f"http://localhost:{PORT}/stream_with_agent_request_direct_return"
    async with aiohttp.ClientSession() as session:
        async with session.post(
            url,
            json={
                "input": [
                    {
                        "role": "user",
                        "type": "message",
                        "content": [{"type": "text", "text": "hello"}],
                    },
                    {
                        "type": "message",
                        "role": "assistant",
                        "content": [
                            {
                                "object": "content",
                                "type": "text",
                                "text": "Hello! How can I assist you today?",
                            },
                        ],
                    },
                    {
                        "role": "user",
                        "type": "message",
                        "content": [
                            {
                                "type": "text",
                                "text": "What is the capital of France?",
                            },
                        ],
                    },
                ],
                "session_id": "1764056632961",
            },
        ) as resp:
            assert resp.status == 200
            data = await resp.json()
            assert data == {"hello": "world"}
