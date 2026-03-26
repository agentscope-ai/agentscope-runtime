# -*- coding: utf-8 -*-
# pylint:disable=redefined-outer-name, unused-argument
"""
Integration tests for stream_query background task functionality.
"""
import asyncio
import multiprocessing
import time

import aiohttp
import pytest

from agentscope_runtime.engine import AgentApp
from agentscope_runtime.engine.schemas.agent_schemas import (
    AgentRequest,
    RunStatus,
)

PORT = 8095


def run_app():
    """Start AgentApp with stream task enabled."""
    app = AgentApp(
        app_name="TestAgent",
        app_description="Test agent for background tasks",
        enable_stream_task=True,
        stream_task_queue="test_queue",
        stream_task_timeout=30,
    )

    @app.query(framework="agentscope")
    async def query_func(self, msgs, request: AgentRequest, **kwargs):
        """
        Mock query handler that yields (msg, last) tuples.
        Simulates agentscope's stream_printing_messages format.
        """
        from agentscope.message import Msg

        for i in range(3):
            await asyncio.sleep(0.1)
            msg = Msg(
                name="assistant",
                content=f"Thinking step {i}",
                role="assistant",
            )
            yield msg, False

        final_msg = Msg(
            name="assistant",
            content="Final answer",
            role="assistant",
        )
        yield final_msg, True

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
async def test_root_endpoint_shows_task_endpoints(start_app):
    """
    Test that root endpoint shows task-related endpoints
    when enable_stream_task is True.
    """
    url = f"http://localhost:{PORT}/"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            assert resp.status == 200
            data = await resp.json()
            assert "endpoints" in data
            assert "task" in data["endpoints"]
            assert data["endpoints"]["task"] == "/process/task"
            assert "task_status" in data["endpoints"]


@pytest.mark.asyncio
async def test_submit_stream_query_task(start_app):
    """Test submitting a stream query as background task."""
    url = f"http://localhost:{PORT}/process/task"
    async with aiohttp.ClientSession() as session:
        async with session.post(
            url,
            json={
                "input": [
                    {
                        "role": "user",
                        "type": "message",
                        "content": [{"type": "text", "text": "Hello"}],
                    },
                ],
                "session_id": "test-session",
            },
        ) as resp:
            assert resp.status == 200
            data = await resp.json()

            assert "task_id" in data
            assert data["status"] == "submitted"
            assert data["queue"] == "test_queue"
            assert "message" in data

            task_id = data["task_id"]

    return task_id


@pytest.mark.asyncio
async def test_get_task_status_pending(start_app):
    """Test getting task status while task is running."""
    submit_url = f"http://localhost:{PORT}/process/task"
    async with aiohttp.ClientSession() as session:
        async with session.post(
            submit_url,
            json={
                "input": [
                    {
                        "role": "user",
                        "type": "message",
                        "content": [{"type": "text", "text": "Hello"}],
                    },
                ],
                "session_id": "test-session",
            },
        ) as resp:
            data = await resp.json()
            task_id = data["task_id"]

        await asyncio.sleep(0.05)

        status_url = f"http://localhost:{PORT}/process/task/{task_id}"
        async with session.get(status_url) as resp:
            assert resp.status == 200
            status_data = await resp.json()

            assert "status" in status_data
            assert status_data["status"] in ["pending", "finished"]


@pytest.mark.asyncio
async def test_get_task_status_finished(start_app):
    """Test getting task status after task completes."""
    submit_url = f"http://localhost:{PORT}/process/task"
    async with aiohttp.ClientSession() as session:
        async with session.post(
            submit_url,
            json={
                "input": [
                    {
                        "role": "user",
                        "type": "message",
                        "content": [{"type": "text", "text": "Test"}],
                    },
                ],
                "session_id": "test-session-2",
            },
        ) as resp:
            data = await resp.json()
            task_id = data["task_id"]

        await asyncio.sleep(1.0)

        status_url = f"http://localhost:{PORT}/process/task/{task_id}"
        async with session.get(status_url) as resp:
            assert resp.status == 200
            status_data = await resp.json()

            assert status_data["status"] == "finished"
            assert "result" in status_data
            assert status_data["result"] is not None

            result = status_data["result"]
            assert result["object"] == "response"
            assert result["status"] == RunStatus.Completed


@pytest.mark.asyncio
async def test_task_only_stores_final_response(start_app):
    """
    Test that task only stores the final response,
    not intermediate events.
    """
    submit_url = f"http://localhost:{PORT}/process/task"
    async with aiohttp.ClientSession() as session:
        async with session.post(
            submit_url,
            json={
                "input": [
                    {
                        "role": "user",
                        "type": "message",
                        "content": [{"type": "text", "text": "Final test"}],
                    },
                ],
                "session_id": "test-session-final",
            },
        ) as resp:
            data = await resp.json()
            task_id = data["task_id"]

        await asyncio.sleep(1.0)

        status_url = f"http://localhost:{PORT}/process/task/{task_id}"
        async with session.get(status_url) as resp:
            status_data = await resp.json()

            assert status_data["status"] == "finished"
            result = status_data["result"]

            assert isinstance(result, dict)
            assert result["object"] == "response"
            assert result["status"] == RunStatus.Completed


@pytest.mark.asyncio
async def test_get_nonexistent_task(start_app):
    """Test getting status of a non-existent task."""
    url = f"http://localhost:{PORT}/process/task/nonexistent-task-id"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            assert resp.status == 200
            data = await resp.json()
            assert "error" in data
            assert "not found" in data["error"].lower()
