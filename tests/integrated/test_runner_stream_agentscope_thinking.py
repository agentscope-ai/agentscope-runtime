# -*- coding: utf-8 -*-
# pylint: disable=unused-argument
import os

import pytest

from agentscope.agent import ReActAgent
from agentscope.model import DashScopeChatModel
from agentscope.formatter import DashScopeChatFormatter
from agentscope.tool import Toolkit
from agentscope.pipeline import stream_printing_messages
from agentscope.memory import InMemoryMemory
from agentscope.session import RedisSession

from agentscope_runtime.engine.schemas.agent_schemas import (
    AgentRequest,
    MessageType,
    RunStatus,
)
from agentscope_runtime.engine.runner import Runner
from agentscope_runtime.adapters.agentscope.tool import sandbox_tool_adapter
from agentscope_runtime.engine.services.sandbox import SandboxService


class MyRunner(Runner):
    def __init__(self) -> None:
        super().__init__()
        self.framework_type = "agentscope"

    async def query_handler(
        self,
        msgs,
        request: AgentRequest = None,
        **kwargs,
    ):
        """
        Handle agent query.
        """
        session_id = request.session_id
        user_id = request.user_id

        # Get sandbox
        sandboxes = self.sandbox_service.connect(
            session_id=session_id,
            user_id=user_id,
            sandbox_types=["browser"],
        )

        sandbox = sandboxes[0]
        browser_tools = [
            sandbox.browser_navigate,
            sandbox.browser_take_screenshot,
            sandbox.browser_snapshot,
            sandbox.browser_click,
            sandbox.browser_type,
        ]

        toolkit = Toolkit()
        for tool in browser_tools:
            toolkit.register_tool_function(sandbox_tool_adapter(tool))

        # Modify agent according to the config
        agent = ReActAgent(
            name="Friday",
            model=DashScopeChatModel(
                "qwen-turbo",
                api_key=os.getenv("DASHSCOPE_API_KEY"),
                enable_thinking=True,
                stream=True,
            ),
            sys_prompt="You're a helpful assistant named Friday.",
            toolkit=toolkit,
            memory=InMemoryMemory(),
            formatter=DashScopeChatFormatter(),
        )
        agent.set_console_output_enabled(enabled=False)

        await self.session.load_session_state(
            session_id=session_id,
            user_id=user_id,
            agent=agent,
        )

        async for msg, last in stream_printing_messages(
            agents=[agent],
            coroutine_task=agent(msgs),
        ):
            yield msg, last

        await self.session.save_session_state(
            session_id=session_id,
            user_id=user_id,
            agent=agent,
        )

    async def init_handler(self, *args, **kwargs):
        """
        Init handler.
        """
        import fakeredis

        fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
        # NOTE: This FakeRedis instance is for development/testing only.
        # In production, replace it with your own Redis client/connection
        # (e.g., aioredis.Redis)
        self.session = RedisSession(connection_pool=fake_redis.connection_pool)

        self.sandbox_service = SandboxService(drain_on_stop=True)
        await self.sandbox_service.start()

    async def shutdown_handler(self, *args, **kwargs):
        """
        Shutdown handler.
        """
        await self.sandbox_service.stop()


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
            "session_id": "Test Session",
        },
    )

    print("\n")
    final_text = ""
    async with MyRunner() as runner:
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
    assert "杭州" in final_text or "hangzhou" in final_text.lower()


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
    async with MyRunner() as runner:
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
