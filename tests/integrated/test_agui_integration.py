# -*- coding: utf-8 -*-
# pylint: disable=redefined-outer-name, protected-access
import json
import multiprocessing
import os
import socket
import time

import aiohttp
import pytest

from agentscope.agent import ReActAgent
from agentscope.message import TextBlock
from agentscope.model import DashScopeChatModel
from agentscope.formatter import DashScopeChatFormatter
from agentscope.tool import ToolResponse, Toolkit, execute_python_code
from agentscope.pipeline import stream_printing_messages

from agentscope_runtime.engine import AgentApp
from agentscope_runtime.engine.schemas.agent_schemas import AgentRequest
from agentscope_runtime.adapters.agentscope.memory import (
    AgentScopeSessionHistoryMemory,
)
from agentscope_runtime.engine.services.agent_state import (
    InMemoryStateService,
)
from agentscope_runtime.engine.services.session_history import (
    InMemorySessionHistoryService,
)

PORT = 8091


def run_app():
    """Start AgentApp with AG-UI endpoint and real LLM."""

    async def get_weather(location: str) -> ToolResponse:
        """Get the weather for a location.

        Args:
            location (str): The location to get the weather for.

        """
        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text=f"The weather in {location} is sunny with a "
                    "temperature of 25°C.",
                ),
            ],
        )

    agent_app = AgentApp(
        app_name="Friday",
        app_description="A helpful assistant for AG-UI testing",
    )

    @agent_app.init
    async def init_func(self):
        self.state_service = InMemoryStateService()
        self.session_service = InMemorySessionHistoryService()

        await self.state_service.start()
        await self.session_service.start()

    @agent_app.shutdown
    async def shutdown_func(self):
        await self.state_service.stop()
        await self.session_service.stop()

    @agent_app.query(framework="agentscope")
    async def query_func(
        self,
        msgs,
        request: AgentRequest = None,
        **kwargs,  # pylint: disable=unused-argument
    ):
        session_id = request.session_id
        user_id = request.user_id

        state = await self.state_service.export_state(
            session_id=session_id,
            user_id=user_id,
        )

        toolkit = Toolkit()
        toolkit.register_tool_function(execute_python_code)
        toolkit.register_tool_function(get_weather)

        agent = ReActAgent(
            name="Friday",
            model=DashScopeChatModel(
                "qwen-max",
                api_key=os.getenv("DASHSCOPE_API_KEY"),
                enable_thinking=False,
                stream=True,
            ),
            sys_prompt="You're a helpful assistant.",
            toolkit=toolkit,
            memory=AgentScopeSessionHistoryMemory(
                service=self.session_service,
                session_id=session_id,
                user_id=user_id,
            ),
            formatter=DashScopeChatFormatter(),
        )
        agent.set_console_output_enabled(enabled=False)

        if state:
            agent.load_state_dict(state)

        async for msg, last in stream_printing_messages(
            agents=[agent],
            coroutine_task=agent(msgs),
        ):
            yield msg, last

        state = agent.state_dict()

        await self.state_service.save_state(
            user_id=user_id,
            session_id=session_id,
            state=state,
        )

    agent_app.run(host="127.0.0.1", port=PORT)


@pytest.fixture(scope="module")
def start_app():
    """Launch AgentApp in a separate process before the async tests."""
    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        pytest.skip("DASHSCOPE_API_KEY not set, skipping integration tests")

    proc = multiprocessing.Process(target=run_app)
    proc.start()

    # Wait for server to start
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


class TestAGUIIntegration:
    """Integration tests for AG-UI protocol."""

    @pytest.mark.asyncio
    async def test_simple_text_exchange(
        self,
        start_app,
    ):  # pylint: disable=unused-argument
        """Test simple text exchange through AG-UI protocol with real LLM."""
        url = f"http://localhost:{PORT}/agui"
        custom_thread_id = "test_thread_1"
        custom_run_id = "test_run_1"
        request_data = {
            "threadId": custom_thread_id,
            "runId": custom_run_id,
            "messages": [
                {
                    "id": "msg_1",
                    "role": "user",
                    "content": "What is 2+2? Answer in one sentence.",
                },
            ],
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=request_data) as resp:
                assert resp.status == 200
                assert (
                    resp.headers["content-type"]
                    == "text/event-stream; charset=utf-8"
                )

                # Parse SSE events
                events = []
                async for line in resp.content:
                    line_str = line.decode("utf-8").strip()
                    if line_str.startswith("data: "):
                        data_str = line_str[6:]
                        if data_str == "[DONE]":
                            break
                        try:
                            event_data = json.loads(data_str)
                            events.append(event_data)
                        except json.JSONDecodeError:
                            continue

                # Verify event sequence
                assert len(events) >= 3, "Should have at least 3 events"

                # Should have run.started
                run_started = [e for e in events if e["type"] == "RUN_STARTED"]
                assert len(run_started) > 0, "Should have RUN_STARTED event"

                # Should have text message events
                text_events = [
                    e
                    for e in events
                    if e["type"]
                    in [
                        "TEXT_MESSAGE_START",
                        "TEXT_MESSAGE_CONTENT",
                        "TEXT_MESSAGE_END",
                    ]
                ]
                assert len(text_events) > 0, "Should have text message events"

                # Should have run.finished
                run_finished = [
                    e for e in events if e["type"] == "RUN_FINISHED"
                ]
                assert len(run_finished) > 0, "Should have RUN_FINISHED event"

                run_started = [e for e in events if e["type"] == "RUN_STARTED"]
                assert len(run_started) > 0
                assert run_started[0]["thread_id"] == custom_thread_id
                assert run_started[0]["run_id"] == custom_run_id

    @pytest.mark.asyncio
    async def test_conversation_with_history(
        self,
        start_app,
    ):  # pylint: disable=unused-argument
        """Test conversation with message history through AG-UI."""
        url = f"http://localhost:{PORT}/agui"

        # First turn: tell agent the user's name
        request_data_1 = {
            "threadId": "test_thread_history",
            "runId": "test_run_h1",
            "messages": [
                {
                    "id": "msg_1",
                    "role": "system",
                    "content": "You are a helpful assistant.",
                },
                {
                    "id": "msg_2",
                    "role": "user",
                    "content": "My name is Bob. Please remember it.",
                },
            ],
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=request_data_1) as resp:
                assert resp.status == 200
                # Consume the response
                async for _ in resp.content:
                    pass

        # Second turn: ask agent to recall the name
        request_data_2 = {
            "threadId": "test_thread_history",
            "runId": "test_run_h2",
            "state": None,
            "tools": [],
            "context": [],
            "forwardedProps": None,
            "messages": [
                {
                    "id": "msg_1",
                    "role": "system",
                    "content": "You are a helpful assistant.",
                },
                {
                    "id": "msg_2",
                    "role": "user",
                    "content": "My name is Bob. Please remember it.",
                },
                {
                    "id": "msg_3",
                    "role": "assistant",
                    "content": "Nice to meet you, Bob! I'll remember your"
                    " name.",
                },
                {
                    "id": "msg_4",
                    "role": "user",
                    "content": "What is my name?",
                },
            ],
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=request_data_2) as resp:
                assert resp.status == 200

                events = []
                async for line in resp.content:
                    line_str = line.decode("utf-8").strip()
                    if line_str.startswith("data: "):
                        data_str = line_str[6:]
                        if data_str == "[DONE]":
                            break
                        try:
                            event_data = json.loads(data_str)
                            events.append(event_data)
                        except json.JSONDecodeError:
                            continue

                # Verify response mentions Bob
                content_events = [
                    e for e in events if e["type"] == "TEXT_MESSAGE_CONTENT"
                ]
                response_text = ""
                for evt in content_events:
                    if "delta" in evt:
                        response_text += evt["delta"]

                assert (
                    "Bob" in response_text or "bob" in response_text.lower()
                ), "Agent should remember and mention Bob"

    async def test_tool_call(
        self,
        start_app,
    ):  # pylint: disable=unused-argument
        """Test tool call through AG-UI."""
        url = f"http://localhost:{PORT}/agui"
        custom_thread_id = "test_thread_1"
        custom_run_id = "test_run_1"
        request_data = {
            "threadId": custom_thread_id,
            "runId": custom_run_id,
            "messages": [
                {
                    "id": "msg_1",
                    "role": "user",
                    "content": "北京的天气如何?",
                },
            ],
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=request_data) as resp:
                assert resp.status == 200
                assert (
                    resp.headers["content-type"]
                    == "text/event-stream; charset=utf-8"
                )

                # Parse SSE events
                events = []
                async for line in resp.content:
                    line_str = line.decode("utf-8").strip()
                    if line_str.startswith("data: "):
                        data_str = line_str[6:]
                        if data_str == "[DONE]":
                            break
                        try:
                            event_data = json.loads(data_str)
                            events.append(event_data)
                        except json.JSONDecodeError:
                            continue
        assert len(events) >= 3, "Should have at least 3 events"

        tool_call_start_events = [
            e for e in events if e["type"] == "TOOL_CALL_START"
        ]
        assert (
            len(tool_call_start_events) > 0
        ), "Should have TOOL_CALL_START event"

        tool_call_args_events = [
            e for e in events if e["type"] == "TOOL_CALL_ARGS"
        ]
        assert (
            len(tool_call_args_events) > 0
        ), "Should have TOOL_CALL_ARGS event"

        tool_call_end_events = [
            e for e in events if e["type"] == "TOOL_CALL_END"
        ]
        assert len(tool_call_end_events) > 0, "Should have TOOL_CALL_END event"

        tool_call_result_event = [
            e for e in events if e["type"] == "TOOL_CALL_RESULT"
        ]
        assert (
            len(tool_call_result_event) == 1
        ), "Should have exactly one TOOL_CALL_RESULT event"
