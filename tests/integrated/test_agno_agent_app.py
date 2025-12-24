# -*- coding: utf-8 -*-
# pylint:disable=redefined-outer-name, unused-argument
import os
import multiprocessing
import time
import json

import aiohttp
import pytest

from agno.agent import Agent
from agno.models.dashscope import DashScope
from agno.db.in_memory import InMemoryDb

from agentscope_runtime.engine import AgentApp
from agentscope_runtime.engine.schemas.agent_schemas import AgentRequest

PORT = 8090


def run_app():
    """Start AgentApp with streaming output enabled."""
    agent_app = AgentApp(
        app_name="Friday",
        app_description="A helpful assistant",
    )

    @agent_app.init
    async def init_func(self):
        # About Agno DB:
        # See https://docs.agno.com/reference/storage for details.
        self.db = InMemoryDb()

    @agent_app.query(framework="agno")
    async def query_func(
        self,
        msgs,
        request: AgentRequest = None,
        **kwargs,
    ):
        session_id = request.session_id

        # Modify agent according to the config
        agent = Agent(
            name="Friday",
            instructions="You're a helpful assistant named Friday",
            model=DashScope(
                id="qwen-plus",
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                api_key=os.getenv("DASHSCOPE_API_KEY"),
            ),
            db=self.db,
            session_id=session_id,
            add_history_to_context=True,
        )

        async for event in agent.arun(
            msgs,
            # session_state=ag_context.memory,
            stream=True,
            stream_events=True,
        ):
            yield event

    agent_app.run(host="127.0.0.1", port=PORT)


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
async def test_openai_compatible_mode(start_app):
    """
    Async test for OpenAI compatible mode endpoint.
    Verifies that the assistant identifies itself as 'Friday'.
    """
    from openai import OpenAI

    client = OpenAI(base_url="http://127.0.0.1:8090/compatible-mode/v1")
    resp = client.responses.create(
        model="any_name",
        input="Who are you?",
    )
    data = resp.response
    assert "Friday" in data["output"][0]["content"][0]["text"]


@pytest.mark.asyncio
async def test_multi_turn_stream_async(start_app):
    """
    Async test for multi‑turn conversation with streaming output.
    Ensures that the agent remembers the user's name from a previous turn.
    """
    session_id = "123456"

    url = f"http://localhost:{PORT}/process"

    async with aiohttp.ClientSession() as session:
        payload1 = {
            "input": [
                {
                    "role": "user",
                    "content": [{"type": "text", "text": "My name is Alice."}],
                },
            ],
            "session_id": session_id,
        }
        async with session.post(url, json=payload1) as resp:
            assert resp.status == 200
            assert resp.headers.get("Content-Type", "").startswith(
                "text/event-stream",
            )
            async for chunk, _ in resp.content.iter_chunks():
                if not chunk:
                    continue
                line = chunk.decode("utf-8").strip()
                if (
                    line.startswith("data:")
                    and line[len("data:") :].strip() == "[DONE]"
                ):
                    break

    payload2 = {
        "input": [
            {
                "role": "user",
                "content": [{"type": "text", "text": "What is my name?"}],
            },
        ],
        "session_id": session_id,
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload2) as resp:
            assert resp.status == 200
            assert resp.headers.get("Content-Type", "").startswith(
                "text/event-stream",
            )

            found_name = False

            async for chunk, _ in resp.content.iter_chunks():
                if not chunk:
                    continue
                line = chunk.decode("utf-8").strip()
                if line.startswith("data:"):
                    data_str = line[len("data:") :].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        event = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue

                    if "output" in event:
                        try:
                            text_content = event["output"][0]["content"][0][
                                "text"
                            ].lower()
                            if "alice" in text_content:
                                found_name = True
                        except Exception:
                            pass

            assert found_name, "Did not find 'Alice' in the second turn output"
