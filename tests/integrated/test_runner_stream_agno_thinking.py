# -*- coding: utf-8 -*-
import os

import pytest

from agno.agent import Agent
from agno.models.dashscope import DashScope
from agentscope_runtime.engine.schemas.agent_schemas import (
    AgentRequest,
    MessageType,
    RunStatus,
)
from agentscope_runtime.engine.runner import Runner
from agentscope_runtime.engine.services.agent_state import (
    InMemoryStateService,
)
from agentscope_runtime.engine.services.session_history import (
    InMemorySessionHistoryService,
)
from agentscope_runtime.engine.services.sandbox import SandboxService


class MyRunner(Runner):
    def __init__(self) -> None:
        super().__init__()
        self.framework_type = "agno"

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

        # Modify agent according to the config
        agent = Agent(
            name="Friday",
            instructions="You're a helpful assistant named Friday",
            model=DashScope(
                id="qwen-plus",
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                api_key=os.getenv("DASHSCOPE_API_KEY"),
                enable_thinking=True,
            ),
            tools=browser_tools,
        )

        async for event in agent.arun(
            msgs,
            # session_state=ag_context.memory,
            stream=True,
            stream_events=True,
        ):
            yield event

    async def init_handler(self, *args, **kwargs):
        """
        Init handler.
        """
        self.state_service = InMemoryStateService()
        self.session_service = InMemorySessionHistoryService()
        self.sandbox_service = SandboxService()
        await self.state_service.start()
        await self.session_service.start()
        await self.sandbox_service.start()

    async def shutdown_handler(self, *args, **kwargs):
        """
        Shutdown handler.
        """
        await self.state_service.stop()
        await self.session_service.stop()
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
    assert "杭州" in final_text


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
