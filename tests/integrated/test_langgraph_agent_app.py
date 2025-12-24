# -*- coding: utf-8 -*-
# pylint: disable=all

import json
import multiprocessing
import os
import time
from typing import TypedDict

import aiohttp
import pytest
from langchain.tools import tool
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from typing_extensions import Annotated

from agentscope_runtime.engine import AgentApp
from agentscope_runtime.engine.schemas.agent_schemas import AgentRequest

PORT = 8091  # Use different port from other tests


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]


def add_time(state: AgentState):
    new_message = HumanMessage(content="Today is August 21, 2025")
    return {"messages": [new_message]}


@tool
def get_weather(location: str, date: str) -> str:
    """Get the weather for a location and date."""
    print(f"Getting weather for {location} on {date}...")
    return f"The weather in {location} is sunny with a temperature of 25°C."


tools = [get_weather]
# Choose the LLM that will drive the agent
llm = ChatOpenAI(
    model="qwen-plus",
    api_key=os.environ.get("DASHSCOPE_API_KEY"),
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
)

prompt = """You are a proactive assistant. """


def build_graph():
    llm = ChatOpenAI(
        model="qwen-plus",
        api_key=os.environ.get("DASHSCOPE_API_KEY"),
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    )

    def call_model(state: AgentState, config: RunnableConfig):
        """Call the LLM to generate a joke about a topic"""
        model_response = llm.invoke(state["messages"], config=config)
        return {"messages": model_response}

    workflow = StateGraph(AgentState)
    workflow.add_node("call_model", call_model)
    workflow.add_edge(START, "call_model")
    graph = workflow.compile()
    return graph


def run_langgraph_app():
    """Start LangGraph AgentApp with streaming output enabled."""
    agent_app = AgentApp(
        app_name="LangGraphAgent",
        app_description="A LangGraph-based assistant",
    )

    @agent_app.init
    async def init_func(self):
        self.short_term_mem = InMemorySaver()

    @agent_app.shutdown
    async def shutdown_func(self):
        pass

    @agent_app.query(framework="langgraph")
    async def query_func(
        self,
        msgs,
        request: AgentRequest = None,
        **kwargs,
    ):
        # Extract session information
        session_id = request.session_id
        user_id = request.user_id
        print("Session ID:", session_id)
        print("User ID:", user_id)

        graph = build_graph()

        async for chunk, meta_data in graph.astream(
            input={"messages": msgs},
            stream_mode="messages",
            config={"configurable": {"thread_id": session_id}},
        ):
            is_last_chunk = (
                True
                if getattr(chunk, "chunk_position", "") == "last"
                else False
            )
            yield chunk, is_last_chunk

    agent_app.run(host="127.0.0.1", port=PORT)


@pytest.fixture(scope="module")
def start_langgraph_app():
    """Launch AgentApp in a separate process before the async tests."""
    proc = multiprocessing.Process(target=run_langgraph_app)
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
        pytest.fail("LangGraph server did not start within timeout")

    yield
    proc.terminate()
    proc.join()


@pytest.mark.asyncio
async def test_langgraph_process_endpoint_stream_async(start_langgraph_app):
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

            found_response = False
            chunks = []

            async for chunk, _ in resp.content.iter_chunks():
                if not chunk:
                    continue
                chunks.append(chunk.decode("utf-8").strip())

            line = chunks[-1]
            # SSE lines start with "data:"
            if line.startswith("data:"):
                data_str = line[len("data:") :].strip()
                event = json.loads(data_str)

                # Check if this event has "output" from the assistant
                if "output" in event:
                    try:
                        text_content = event["output"][-1]["content"][0][
                            "text"
                        ].lower()
                        if "paris" in text_content:
                            found_response = True
                    except Exception:
                        # Structure may differ; ignore
                        pass

            # Final assertion — we must have seen "paris" in at least one event
            assert (
                found_response
            ), "Did not find 'paris' in any streamed output event"


@pytest.mark.asyncio
async def test_langgraph_multi_turn_stream_async(start_langgraph_app):
    """
    Async test for multi-turn conversation with streaming output.
    """
    session_id = "langgraph_test_session"
    url = f"http://localhost:{PORT}/process"

    # First turn
    async with aiohttp.ClientSession() as session:
        payload1 = {
            "input": [
                {
                    "role": "user",
                    "content": [{"type": "text", "text": "Hello LangGraph!"}],
                },
            ],
            "session_id": session_id,
        }
        async with session.post(url, json=payload1) as resp:
            assert resp.status == 200
            assert resp.headers.get("Content-Type", "").startswith(
                "text/event-stream",
            )
            # Simply consume the stream without detailed checking
            chunks = []
            async for chunk, _ in resp.content.iter_chunks():
                if not chunk:
                    continue
                chunks.append(chunk.decode("utf-8").strip())

            found_response = False
            line = chunks[-1]
            # SSE lines start with "data:"
            if line.startswith("data:"):
                data_str = line[len("data:") :].strip()
                event = json.loads(data_str)

    payload2 = {
        "input": [
            {
                "role": "user",
                "content": [{"type": "text", "text": "How are you?"}],
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

            chunks = []
            async for chunk, _ in resp.content.iter_chunks():
                if not chunk:
                    continue
                chunks.append(chunk.decode("utf-8").strip())

            found_response = False
            line = chunks[-1]
            # SSE lines start with "data:"
            if line.startswith("data:"):
                data_str = line[len("data:") :].strip()
                event = json.loads(data_str)

                # Check if this event has "output" from the assistant
                if "output" in event:
                    try:
                        text_content = event["output"][-1]["content"][0][
                            "text"
                        ].lower()
                        if text_content:
                            found_response = True
                    except Exception:
                        # Structure may differ; ignore
                        pass

            assert (
                found_response
            ), "Did not find expected response in the second turn output"


if __name__ == "__main__":
    pytest.main([__file__])
