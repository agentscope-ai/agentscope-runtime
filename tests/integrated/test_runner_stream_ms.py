# -*- coding: utf-8 -*-
# pylint:disable=unused-argument
import os

import pytest

from agent_framework.openai import OpenAIChatClient
from agentscope_runtime.engine.schemas.agent_schemas import (
    AgentRequest,
    MessageType,
    RunStatus,
)
from agentscope_runtime.engine.runner import Runner
from agentscope_runtime.engine.services.sandbox import SandboxService


class MyRunner(Runner):
    def __init__(self) -> None:
        super().__init__()
        self.framework_type = "ms_agent_framework"

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
        id_key = f"{user_id}_{session_id}"

        thread = self.thread_storage.get(id_key)

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
        agent = OpenAIChatClient(
            model_id="qwen-turbo",
            api_key=os.environ["DASHSCOPE_API_KEY"],
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        ).create_agent(
            instructions="You're a helpful assistant named Friday",
            name="Friday",
            tools=browser_tools,
        )

        if thread:
            thread = await agent.deserialize_thread(thread)
        else:
            thread = agent.get_new_thread()

        async for event in agent.run_stream(
            msgs,
            thread=thread,
        ):
            yield event

        serialized_thread = await thread.serialize()
        self.thread_storage[id_key] = serialized_thread

    async def init_handler(self, *args, **kwargs):
        """
        Init handler.
        """
        self.thread_storage = {}  # Only for testing
        self.sandbox_service = SandboxService()
        await self.sandbox_service.start()

    async def shutdown_handler(self, *args, **kwargs):
        """
        Shutdown handler.
        """
        await self.sandbox_service.stop()


@pytest.mark.asyncio(loop_scope="session")
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
            print("message", message.model_dump_json())
            if message.object == "message":
                if MessageType.MESSAGE == message.type:
                    if RunStatus.Completed == message.status:
                        res = message.content
                        print("res", res)
                        if res and len(res) > 0:
                            final_text = res[0].text
                            print("final_text", final_text)
                if MessageType.FUNCTION_CALL == message.type:
                    if RunStatus.Completed == message.status:
                        res = message.content
                        print("res", res)

        print("\n")
    assert "杭州" in final_text or "hangzhou" in final_text.lower()


@pytest.mark.asyncio(loop_scope="session")
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
