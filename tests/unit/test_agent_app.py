# -*- coding: utf-8 -*-
# pylint:disable=redefined-outer-name, unused-argument
import os
import multiprocessing
import time
import json

import aiohttp
import pytest

from agentscope.agent import ReActAgent
from agentscope.model import DashScopeChatModel

from agentscope_runtime.engine import AgentApp
from agentscope_runtime.engine.agents.agentscope_agent import AgentScopeAgent


PORT = 8090


def run_app():
    """Start AgentApp with streaming output enabled."""
    agent = AgentScopeAgent(
        name="Friday",
        model=DashScopeChatModel(
            "qwen-max",
            api_key=os.getenv("DASHSCOPE_API_KEY"),
        ),
        agent_config={
            "sys_prompt": "You're a helpful assistant named Friday.",
        },
        agent_builder=ReActAgent,
    )
    app = AgentApp(agent=agent)

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
async def test_process_endpoint_stream_async(start_app):
    """
    Async test for streaming /process endpoint (SSE, multiple JSON events).
    """
    url = f"http://localhost:{PORT}/process"
    payload = {
        "input": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "What is the capital of France?"},
                ],
            },
        ],
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload) as resp:
            assert resp.status == 200
            assert resp.headers.get("Content-Type", "").startswith(
                "text/event-stream",
            )

            found_paris = False

            async for chunk, _ in resp.content.iter_chunks():
                if not chunk:
                    continue

                line = chunk.decode("utf-8").strip()
                # SSE lines start with "data:"
                if line.startswith("data:"):
                    data_str = line[len("data:") :].strip()
                    if data_str == "[DONE]":
                        break

                    try:
                        event = json.loads(data_str)
                    except json.JSONDecodeError:
                        # Ignore non‑JSON keepalive messages or partial lines
                        continue

                    # Debug: print(event)  # Uncomment if needed

                    # Check if this event has "output" from the assistant
                    if "output" in event:
                        try:
                            text_content = event["output"][0]["content"][0][
                                "text"
                            ].lower()
                            if "paris" in text_content:
                                found_paris = True
                        except Exception:
                            # Structure may differ; ignore
                            pass

            # Final assertion — we must have seen "paris" in at least one event
            assert (
                found_paris
            ), "Did not find 'paris' in any streamed output event"


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
            text_chunks = []
            async for chunk, _ in resp.content.iter_chunks():
                if chunk:
                    text_chunks.append(chunk.decode("utf-8").strip())

    assert text_chunks == [f"async chunk {i}" for i in range(5)]


@pytest.mark.asyncio
async def test_stream_sync_endpoint(start_app):
    """
    Test /stream_sync streaming chunks (sync-style handler).
    """
    url = f"http://localhost:{PORT}/stream_sync"
    async with aiohttp.ClientSession() as session:
        async with session.post(url) as resp:
            assert resp.status == 200
            text_chunks = []
            async for chunk, _ in resp.content.iter_chunks():
                if chunk:
                    text_chunks.append(chunk.decode("utf-8").strip())

    assert text_chunks == [f"sync chunk {i}" for i in range(5)]
