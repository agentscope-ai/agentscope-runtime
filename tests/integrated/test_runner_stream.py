# -*- coding: utf-8 -*-
import os

import pytest
from agentscope.agent import ReActAgent
from agentscope.model import DashScopeChatModel

from agentscope_runtime.engine.agents.agentscope_agent import AgentScopeAgent
from agentscope_runtime.engine.runner import Runner
from agentscope_runtime.engine.schemas.agent_schemas import (
    AgentRequest,
    MessageType,
    RunStatus,
)
from agentscope_runtime.engine.services.context_manager import ContextManager
from agentscope_runtime.engine.services.session_history_service import (
    InMemorySessionHistoryService,
)


@pytest.mark.asyncio
async def test_runner():
    from dotenv import load_dotenv

    load_dotenv("../../.env")

    agent = AgentScopeAgent(
        name="Friday",
        model=DashScopeChatModel(
            "qwen-turbo",
            api_key=os.getenv("DASHSCOPE_API_KEY"),
        ),
        agent_config={
            "sys_prompt": "You're a helpful assistant named Friday.",
        },
        agent_builder=ReActAgent,
    )

    session_history_service = InMemorySessionHistoryService()
    USER_ID = "user_1"
    SESSION_ID = "session_001"  # Using a fixed ID for simplicity
    await session_history_service.create_session(
        user_id=USER_ID,
        session_id=SESSION_ID,
    )

    context_manager = ContextManager(
        session_history_service=session_history_service,
    )
    async with context_manager:
        runner = Runner(
            agent=agent,
            context_manager=context_manager,
            environment_manager=None,
        )

        request = AgentRequest.model_validate(
            {
                "input": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "杭州的天气怎么样？",
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
                                    "arguments": '{"location": "杭州"}',
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
                "session_id": SESSION_ID,
                "tools": [
                    {
                        "type": "function",
                        "function": {
                            "name": "get_current_weather",
                            "description": "Get the current weather in a "
                            "given "
                            "location",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "location": {
                                        "type": "string",
                                        "description": "The city and state, "
                                        "e.g. San Francisco, CA",
                                    },
                                },
                            },
                        },
                    },
                ],
            },
        )

        print("\n")
        async for message in runner.stream_query(
            user_id=USER_ID,
            request=request,
        ):
            print(message.model_dump_json())
            if message.object == "message":
                if MessageType.MESSAGE == message.type:
                    if RunStatus.Completed == message.status:
                        res = message.content
                        print(res)
                if MessageType.FUNCTION_CALL == message.type:
                    if RunStatus.Completed == message.status:
                        res = message.content
                        print(res)

        print("\n")
