# -*- coding: utf-8 -*-
import pytest

from agentscope_runtime.engine.schemas.agent_schemas import (
    AgentRequest,
    MessageType,
    RunStatus,
)
from agentscope_runtime.engine.helpers.runner import SimpleRunner


@pytest.mark.asyncio
async def test_runner():
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
            ],
            "stream": True,
            "session_id": "Test Session",
        },
    )

    print("\n")
    final_text = ""
    async with SimpleRunner() as runner:
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
    assert final_text == "Hi! My name is Friday."
