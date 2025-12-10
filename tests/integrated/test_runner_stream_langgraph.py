# -*- coding: utf-8 -*-
# pylint: disable=all

import os
import pytest

from langchain.agents import AgentState
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.constants import START
from langgraph.graph import StateGraph

from agentscope_runtime.engine.schemas.agent_schemas import (
    AgentRequest,
    MessageType,
    RunStatus,
)
from agentscope_runtime.engine.runner import Runner


class MyLangGraphRunner(Runner):
    def __init__(self) -> None:
        super().__init__()
        self.framework_type = "langgraph"

    async def init_handler(self, *args, **kwargs):
        """
        Init handler.
        """
        self.short_term_mem = InMemorySaver()

    async def shutdown_handler(self, *args, **kwargs):
        """
        Shutdown handler.
        """
        pass

    async def query_handler(
        self,
        msgs,
        request: AgentRequest = None,
        **kwargs,
    ):
        """
        Handle LangGraph agent query.
        """
        session_id = request.session_id
        user_id = request.user_id
        print(f"Received query from user {user_id} with session {session_id}")
        llm = ChatOpenAI(
            model="qwen-plus",
            api_key=os.environ.get("DASHSCOPE_API_KEY"),
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )

        def call_model(state: AgentState):
            """Call the LLM to generate a joke about a topic"""
            model_response = llm.invoke(state["messages"])
            return {"messages": model_response}

        workflow = StateGraph(AgentState)
        workflow.add_node("call_model", call_model)
        workflow.add_edge(START, "call_model")
        graph = workflow.compile(name="langgraph_agent")

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


@pytest.mark.asyncio
async def test_runner_sample1():
    from dotenv import load_dotenv

    load_dotenv("../../.env")

    request = AgentRequest.model_validate(
        {
            "input": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "What's the weather like in Hangzhou?",
                        },
                    ],
                },
                {
                    "type": "function_call",
                    "content": [
                        {
                            "type": "data",
                            "data": {
                                "call_id": "call_eb113ba709d54ab6a4dcbf",
                                "name": "get_current_weather",
                                "arguments": '{"location": "Hangzhou"}',
                            },
                        },
                    ],
                },
                {
                    "type": "function_call_output",
                    "content": [
                        {
                            "type": "data",
                            "data": {
                                "call_id": "call_eb113ba709d54ab6a4dcbf",
                                "output": '{"temperature": 25, "unit": '
                                '"Celsius"}',
                            },
                        },
                    ],
                },
            ],
            "stream": True,
            "session_id": "Test Session",
        },
    )

    print("\n")
    final_text = ""
    async with MyLangGraphRunner() as runner:
        async for message in runner.stream_query(
            request=request,
        ):
            print(message.model_dump_json())
            if message.object == "message":
                if MessageType.MESSAGE == message.type:
                    if RunStatus.Completed == message.status:
                        res = message.content
                        print(res)
                        if res and len(res) > 0:
                            final_text = res[0].text
                            print(final_text)
                if MessageType.FUNCTION_CALL == message.type:
                    if RunStatus.Completed == message.status:
                        res = message.content
                        print(res)

        print("\n")
    assert "Hangzhou" in final_text


@pytest.mark.asyncio
async def test_runner_sample2():
    from dotenv import load_dotenv

    load_dotenv("../../.env")

    request = AgentRequest.model_validate(
        {
            "input": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "What is in https://example.com?",
                        },
                    ],
                },
            ],
            "stream": True,
            "session_id": "Test Session",
        },
    )

    print("\n")
    final_text = ""
    async with MyLangGraphRunner() as runner:
        async for message in runner.stream_query(
            request=request,
        ):
            print(message.model_dump_json())
            if message.object == "message":
                if MessageType.MESSAGE == message.type:
                    if RunStatus.Completed == message.status:
                        res = message.content
                        print(res)
                        if res and len(res) > 0:
                            final_text = res[0].text
                            print(final_text)
                if MessageType.FUNCTION_CALL == message.type:
                    if RunStatus.Completed == message.status:
                        res = message.content
                        print(res)

        print("\n")

    assert "example.com" in final_text
