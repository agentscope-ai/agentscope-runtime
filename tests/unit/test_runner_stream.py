# -*- coding: utf-8 -*-
import copy
import pytest
from dotenv import load_dotenv

from agentscope_runtime.engine.schemas.agent_schemas import (
    AgentRequest,
    MessageType,
    RunStatus,
)
from agentscope_runtime.engine.helpers.runner import SimpleRunner, ErrorRunner


def make_request(text: str, session_id: str) -> AgentRequest:
    """Build a reusable AgentRequest object."""
    return AgentRequest.model_validate(
        {
            "input": [
                {
                    "role": "user",
                    "content": [{"type": "text", "text": text}],
                },
            ],
            "stream": True,
            "session_id": session_id,
        },
    )


async def run_and_collect(runner_cls, request: AgentRequest):
    """Run a runner class and collect all streamed messages."""
    results = []
    async with runner_cls() as runner:
        async for message in runner.stream_query(request=request):
            print(message.model_dump_json())
            results.append(copy.deepcopy(message))
    return results


@pytest.mark.asyncio
async def test_simple_runner():
    """Test SimpleRunner for a normal completion response."""
    load_dotenv("../../.env")

    request = make_request("What's the weather in Hangzhou?", "Test Session")
    messages = await run_and_collect(SimpleRunner, request)

    final_text = ""
    for message in messages:
        if (
            message.object == "message"
            and message.type == MessageType.MESSAGE
            and message.status == RunStatus.Completed
        ):
            res = message.content
            if res and len(res) > 0:
                final_text = res[0].text

    assert final_text == "Hi! My name is Friday."


@pytest.mark.asyncio
async def test_error_runner():
    """Test ErrorRunner to ensure error messages are returned."""
    load_dotenv("../../.env")

    request = make_request(
        "This should trigger an error",
        "Test Error Session",
    )
    messages = await run_and_collect(ErrorRunner, request)
    assert len(messages) >= 2

    assert (
        messages[-1].object == "response"
        and messages[-1].status == RunStatus.Failed
    ), "ErrorRunner should return error response in the end"
