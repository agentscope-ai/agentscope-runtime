# -*- coding: utf-8 -*-
# pylint: disable=redefined-outer-name, protected-access, no-name-in-module
import multiprocessing
import os
import socket
import time
from typing import List, cast
import uuid

from ag_ui.core import Event, EventType, FunctionCall, RunAgentInput
from ag_ui.core.types import (
    AssistantMessage,
    SystemMessage,
    UserMessage,
    ToolMessage,
    ToolCall,
)
import aiohttp
from pydantic import TypeAdapter
import pytest

from agentscope.agent import ReActAgent
from agentscope.message import Msg, TextBlock
from agentscope.model import DashScopeChatModel
from agentscope.formatter import DashScopeChatFormatter
from agentscope.tool import ToolResponse, Toolkit, execute_python_code
from agentscope.pipeline import stream_printing_messages

from langchain_core.messages import BaseMessage
from langchain.agents import AgentState, create_agent
from langchain.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.graph.state import CompiledStateGraph
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore

from agentscope_runtime.engine import AgentApp
from agentscope_runtime.engine.runner import Runner
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

AGENTSCOPE_APP_PORT = 8091
LANGGRAPH_APP_PORT = 8092


def launch_agentscope_app():
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
    async def init_func(runner: Runner):
        runner.state_service = InMemoryStateService()
        runner.session_service = InMemorySessionHistoryService()

        await runner.state_service.start()
        await runner.session_service.start()

    @agent_app.query(framework="agentscope")
    async def query_func(
        runner: Runner,
        msgs: List[Msg],
        request: AgentRequest = None,
        **kwargs,  # pylint: disable=unused-argument
    ):
        session_id = request.session_id
        user_id = request.user_id

        state = await runner.state_service.export_state(
            session_id=session_id,
            user_id=user_id,
        )

        toolkit = Toolkit()
        toolkit.register_tool_function(execute_python_code)
        toolkit.register_tool_function(get_weather)

        agent = ReActAgent(
            name="Friday",
            model=DashScopeChatModel(
                "qwen-plus",
                api_key=os.getenv("DASHSCOPE_API_KEY"),
                enable_thinking=False,
                stream=True,
            ),
            sys_prompt="You're a helpful assistant.",
            toolkit=toolkit,
            memory=AgentScopeSessionHistoryMemory(
                service=runner.session_service,
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

        await runner.state_service.save_state(
            user_id=user_id,
            session_id=session_id,
            state=state,
        )

    agent_app.run(host="127.0.0.1", port=AGENTSCOPE_APP_PORT)


def launch_langgraph_app():
    """Start LangGraphAgent App with AG-UI endpoint and real LLM."""

    @tool
    def get_weather(location: str) -> str:
        """Get the weather for a location and date."""
        return (
            f"The weather in {location} is sunny with a temperature of 25°C."
        )

    # Create the AgentApp instance
    agent_app = AgentApp(
        app_name="LangGraphAgent",
        app_description="A LangGraph-based research assistant",
    )

    class CustomAgentState(AgentState):
        user_id: str
        session_id: dict

    # Initialize services as instance variables
    @agent_app.init
    async def init_func(runner: Runner):
        runner.short_term_mem = InMemorySaver()
        runner.long_term_mem = InMemoryStore()
        # Choose the LLM that will drive the agent
        llm = ChatOpenAI(
            model="qwen-plus",
            api_key=os.getenv("DASHSCOPE_API_KEY"),
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )
        prompt = """You are a proactive research assistant. """
        runner.agent = create_agent(
            llm,
            tools=[get_weather],
            system_prompt=prompt,
            checkpointer=runner.short_term_mem,
            store=runner.long_term_mem,
            state_schema=CustomAgentState,
            name="LangGraphAgent",
        )

    @agent_app.query(framework="langgraph")
    async def query_func(
        runner: Runner,
        msgs: List[BaseMessage],
        request: AgentRequest = None,
        **kwargs,  # pylint: disable=unused-argument
    ):
        # Extract session information
        session_id = request.session_id
        user_id = request.user_id
        print(f"Received query from user {user_id} with session {session_id}")
        namespace_for_long_term_memory = (user_id, "memories")

        agent = cast(CompiledStateGraph, runner.agent)

        async for chunk, meta_data in agent.astream(
            input={
                "messages": msgs,
                "session_id": session_id,
                "user_id": user_id,
            },
            stream_mode="messages",
            config={"configurable": {"thread_id": session_id}},
        ):
            is_last_chunk = getattr(chunk, "chunk_position", "") == "last"
            if meta_data["langgraph_node"] == "tools":
                memory_id = str(uuid.uuid4())
                memory = {"lastest_tool_call": chunk.name}
                runner.long_term_mem.put(
                    namespace_for_long_term_memory,
                    memory_id,
                    memory,
                )
            yield chunk, is_last_chunk

    agent_app.run(host="127.0.0.1", port=LANGGRAPH_APP_PORT)


def _start_app_server(target_func, port):
    """Helper to start an app server and wait for it to be ready."""
    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        pytest.skip("DASHSCOPE_API_KEY not set, skipping integration tests")

    proc = multiprocessing.Process(target=target_func)
    proc.start()

    # Wait for server to start
    for _ in range(50):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.connect(("localhost", port))
            s.close()
            break
        except OSError:
            time.sleep(0.1)
    else:
        proc.terminate()
        pytest.fail("Server did not start within timeout")

    return proc


@pytest.fixture(scope="module", params=["agentscope", "langgraph"])
def app_endpoint(request):
    """Parametrized fixture that launches the appropriate app server."""
    if request.param == "agentscope":
        proc = _start_app_server(launch_agentscope_app, AGENTSCOPE_APP_PORT)
        yield "localhost", AGENTSCOPE_APP_PORT
    elif request.param == "langgraph":
        proc = _start_app_server(launch_langgraph_app, LANGGRAPH_APP_PORT)
        yield "localhost", LANGGRAPH_APP_PORT
    else:
        raise ValueError(f"Unknown app_endpoint param: {request.param}")
    proc.terminate()
    proc.join()


async def invoke_api(
    url: str,
    ag_ui_request: RunAgentInput,
) -> List[Event]:
    event_adapter = TypeAdapter(Event)
    events = []
    async with aiohttp.ClientSession() as session:
        async with session.post(
            url,
            json=ag_ui_request.model_dump(mode="json"),
        ) as resp:
            assert resp.status == 200
            assert (
                resp.headers["content-type"]
                == "text/event-stream; charset=utf-8"
            )
            async for line in resp.content:
                line_str = line.decode("utf-8").strip()
                if line_str.startswith("data: "):
                    data_str = line_str[6:]
                    if data_str == "[DONE]":
                        break

                    events.append(event_adapter.validate_json(data_str))
    return events


class TestAGUIIntegration:
    """Integration tests for AG-UI protocol."""

    @pytest.mark.asyncio
    async def test_simple_text_exchange(
        self,
        app_endpoint: tuple[str, int],
    ):
        """Test simple text exchange through AG-UI protocol with real LLM."""
        host, port = app_endpoint
        url = f"http://{host}:{port}/ag-ui"
        custom_thread_id = "test_thread_1"
        custom_run_id = "test_run_1"
        ag_ui_request = RunAgentInput(
            threadId=custom_thread_id,
            runId=custom_run_id,
            messages=[
                UserMessage(
                    id="msg_1",
                    content="What is 2+2? Answer in one sentence.",
                ),
            ],
            state=None,
            tools=[],
            context=[],
            forwarded_props=None,
        )
        events: List[Event] = []
        event_adapter = TypeAdapter(Event)

        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                json=ag_ui_request.model_dump(mode="json"),
            ) as resp:
                assert resp.status == 200
                assert (
                    resp.headers["content-type"]
                    == "text/event-stream; charset=utf-8"
                )

                # Parse SSE events
                async for line in resp.content:
                    line_str = line.decode("utf-8").strip()
                    if line_str.startswith("data: "):
                        data_str = line_str[6:]
                        if data_str == "[DONE]":
                            break
                        events.append(event_adapter.validate_json(data_str))

        # Verify event sequence
        assert len(events) >= 3, "Should have at least 3 events"

        # Should have run.started
        run_started = [e for e in events if e.type == EventType.RUN_STARTED]
        assert len(run_started) > 0, "Should have RUN_STARTED event"
        assert run_started[0].thread_id == custom_thread_id
        assert run_started[0].run_id == custom_run_id

        # Should have text message events
        text_events = [
            e
            for e in events
            if e.type
            in {
                EventType.TEXT_MESSAGE_START,
                EventType.TEXT_MESSAGE_CONTENT,
                EventType.TEXT_MESSAGE_END,
            }
        ]
        assert len(text_events) > 0, "Should have text message events"

        # Should have run.finished
        run_finished = [e for e in events if e.type == EventType.RUN_FINISHED]
        assert len(run_finished) > 0, "Should have RUN_FINISHED event"

    @pytest.mark.asyncio
    async def test_conversation_with_history(
        self,
        app_endpoint: tuple[str, int],
    ):
        """Test conversation with message history through AG-UI."""
        host, port = app_endpoint
        url = f"http://{host}:{port}/ag-ui"

        # First turn: tell agent the user's name
        thread_id = "test_thread_history"
        ag_ui_request_1 = RunAgentInput(
            threadId=thread_id,
            runId="test_run_h1",
            messages=[
                SystemMessage(
                    id="msg_1",
                    content="You are a helpful assistant.",
                ),
                UserMessage(
                    id="msg_2",
                    content="My name is Bob. Please remember it.",
                ),
            ],
            state=None,
            tools=[],
            context=[],
            forwarded_props=None,
        )
        event_adapter = TypeAdapter(Event)
        events_1: List[Event] = []

        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                json=ag_ui_request_1.model_dump(mode="json"),
            ) as resp:
                assert resp.status == 200
                async for line in resp.content:
                    line_str = line.decode("utf-8").strip()
                    if line_str.startswith("data: "):
                        data_str = line_str[6:]
                        if data_str == "[DONE]":
                            break
                        events_1.append(event_adapter.validate_json(data_str))
        assert any(
            e.type == EventType.RUN_FINISHED for e in events_1
        ), "First turn should finish"

        # Second turn: ask agent to recall the name
        ag_ui_request_2 = RunAgentInput(
            threadId=thread_id,
            runId="test_run_h2",
            state=None,
            tools=[],
            context=[],
            forwarded_props=None,
            messages=[
                SystemMessage(
                    id="msg_1",
                    content="You are a helpful assistant.",
                ),
                UserMessage(
                    id="msg_2",
                    content="My name is Bob. Please remember it.",
                ),
                AssistantMessage(
                    id="msg_3",
                    content="Nice to meet you, Bob! I'll remember your name.",
                ),
                UserMessage(
                    id="msg_4",
                    content="What is my name?",
                ),
            ],
        )

        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                json=ag_ui_request_2.model_dump(mode="json"),
            ) as resp:
                assert resp.status == 200

                events: List[Event] = []
                async for line in resp.content:
                    line_str = line.decode("utf-8").strip()
                    if line_str.startswith("data: "):
                        data_str = line_str[6:]
                        if data_str == "[DONE]":
                            break
                        events.append(event_adapter.validate_json(data_str))

                # Verify response mentions Bob
                content_events = [
                    e
                    for e in events
                    if e.type == EventType.TEXT_MESSAGE_CONTENT
                ]
                response_text = "".join(e.delta for e in content_events)

                assert (
                    "Bob" in response_text or "bob" in response_text.lower()
                ), "Agent should remember and mention Bob"

    @pytest.mark.asyncio
    async def test_tool_call(
        self,
        app_endpoint: tuple[str, int],
    ):
        """Test tool call through AG-UI."""
        host, port = app_endpoint
        url = f"http://{host}:{port}/ag-ui"
        thread_id = str(uuid.uuid4())
        run_id = str(uuid.uuid4())

        ag_ui_request = RunAgentInput(
            threadId=thread_id,
            runId=run_id,
            messages=[
                UserMessage(
                    id=str(uuid.uuid4()),
                    content="北京今天的天气如何?",
                ),
            ],
            state=None,
            tools=[],
            context=[],
            forwarded_props=None,
        )
        events = await invoke_api(url, ag_ui_request)

        run_started_event = [
            e for e in events if e.type == EventType.RUN_STARTED
        ]
        assert (
            len(run_started_event) == 1
        ), "Should have exactly one RUN_STARTED event"
        assert run_started_event[0].thread_id == thread_id
        assert run_started_event[0].run_id == run_id

        run_finished_event = [
            e for e in events if e.type == EventType.RUN_FINISHED
        ]
        assert (
            len(run_finished_event) == 1
        ), "Should have exactly one RUN_FINISHED event"
        assert run_finished_event[0].thread_id == thread_id
        assert run_finished_event[0].run_id == run_id

        tool_call_start_events = [
            e for e in events if e.type == EventType.TOOL_CALL_START
        ]
        assert (
            len(tool_call_start_events) > 0
        ), "Should have TOOL_CALL_START event"

        tool_call_args_events = [
            e for e in events if e.type == EventType.TOOL_CALL_ARGS
        ]
        assert (
            len(tool_call_args_events) > 0
        ), "Should have TOOL_CALL_ARGS event"

        tool_call_end_events = [
            e for e in events if e.type == EventType.TOOL_CALL_END
        ]
        assert len(tool_call_end_events) > 0, "Should have TOOL_CALL_END event"

        tool_call_result_events = [
            e for e in events if e.type == EventType.TOOL_CALL_RESULT
        ]
        assert (
            len(tool_call_result_events) == 1
        ), "Should have exactly one TOOL_CALL_RESULT event"
        tool_call_id = str(uuid.uuid4())

        multi_turn_request = RunAgentInput(
            thread_id=thread_id,
            run_id=str(uuid.uuid4()),
            messages=[
                UserMessage(
                    id=str(uuid.uuid4()),
                    content="北京今天的天气如何?",
                ),
                AssistantMessage(
                    id=str(uuid.uuid4()),
                    content="The weather in Beijing is sunny with a "
                    "temperature of 25°C.",
                    tool_calls=[
                        ToolCall(
                            id=tool_call_id,
                            function=FunctionCall(
                                name="get_weather",
                                arguments='{"location": "Beijing"}',
                            ),
                        ),
                    ],
                ),
                ToolMessage(
                    id=str(uuid.uuid4()),
                    content="The weather in Beijing is sunny with a "
                    "temperature of 25°C.",
                    tool_call_id=tool_call_id,
                ),
                AssistantMessage(
                    id=str(uuid.uuid4()),
                    content="北京的天气是晴朗的，气温为25°C。",
                ),
                UserMessage(
                    id=str(uuid.uuid4()),
                    content="那杭州的呢？",
                ),
            ],
            state=None,
            tools=[],
            context=[],
            forwarded_props=None,
        )
        multi_turn_events = await invoke_api(url, multi_turn_request)

        run_started_event = [
            e for e in multi_turn_events if e.type == EventType.RUN_STARTED
        ]
        assert (
            len(run_started_event) == 1
        ), "Should have exactly one RUN_STARTED event"
        assert run_started_event[0].thread_id == thread_id
        assert run_started_event[0].run_id == multi_turn_request.run_id

        run_finished_event = [
            e for e in multi_turn_events if e.type == EventType.RUN_FINISHED
        ]
        assert (
            len(run_finished_event) == 1
        ), "Should have exactly one RUN_FINISHED event"
        assert run_finished_event[0].thread_id == thread_id
        assert run_finished_event[0].run_id == multi_turn_request.run_id

        tool_call_result_events = [
            e
            for e in multi_turn_events
            if e.type == EventType.TOOL_CALL_RESULT
        ]
        assert (
            len(tool_call_result_events) == 1
        ), "Should have exactly one TOOL_CALL_RESULT event"
