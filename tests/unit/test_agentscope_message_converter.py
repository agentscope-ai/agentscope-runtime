# -*- coding: utf-8 -*-
import json
import pytest

from agentscope.message import (
    Msg,
    TextBlock,
    ImageBlock,
    AudioBlock,
    URLSource,
    Base64Source,
    ToolUseBlock,
    ToolResultBlock,
    ThinkingBlock,
)

from agentscope_runtime.adapters.agentscope.message import (
    agentscope_msg_to_message,
    message_to_agentscope_msg,
)
from agentscope_runtime.engine.schemas.agent_schemas import AgentRequest


def normalize(obj):
    """
    Recursively converts an object into a standard comparable structure.
    """
    if hasattr(obj, "model_dump"):  # Handles Pydantic v2 objects
        return obj.model_dump()
    elif isinstance(obj, (list, tuple)):
        return [normalize(i) for i in obj]
    elif isinstance(obj, dict):
        return {k: normalize(v) for k, v in obj.items()}
    else:
        return obj


def _check_round_trip(msgs):
    """
    Performs a round-trip conversion check:
    Agentscope `Msg` -> Runtime Message -> Agentscope `Msg`.
    """
    runtime_messages = agentscope_msg_to_message(msgs)
    assert isinstance(runtime_messages, list)
    assert len(runtime_messages) >= 1

    converted_msgs = message_to_agentscope_msg(runtime_messages)

    if isinstance(msgs, Msg):
        original_msgs = [msgs]
    elif isinstance(msgs, list):
        original_msgs = msgs
    else:
        raise TypeError(f"Unsupported msgs type: {type(msgs)}")

    assert isinstance(converted_msgs, list)
    assert len(converted_msgs) == len(original_msgs)

    for orig, conv in zip(original_msgs, converted_msgs):
        assert conv.name == orig.name
        assert conv.role == orig.role
        assert conv.invocation_id == orig.invocation_id
        assert conv.metadata == orig.metadata

        orig_blocks = normalize(orig.content)
        conv_blocks = normalize(conv.content)
        assert json.dumps(orig_blocks, sort_keys=True) == json.dumps(
            conv_blocks,
            sort_keys=True,
        )


@pytest.mark.parametrize(
    "msgs",
    [
        Msg(
            name="assistant",
            role="assistant",
            metadata={"testdata": "test"},
            content=[
                TextBlock(type="text", text="hello world"),
                ImageBlock(
                    type="image",
                    source=URLSource(
                        type="url",
                        url="http://example.com/image.jpg",
                    ),
                ),
                ImageBlock(
                    type="image",
                    source=Base64Source(
                        type="base64",
                        media_type="image/gif",
                        data=(
                            "UklGRgAAAABXQVZFZm10IBAAAAABAAEA"
                            "ESsAACJWAAACABAAZGF0YQAAAAA="
                        ),
                    ),
                ),
                AudioBlock(
                    type="audio",
                    source=URLSource(
                        type="url",
                        url="http://example.com/audio.wav",
                    ),
                ),
                AudioBlock(
                    type="audio",
                    source=Base64Source(
                        type="base64",
                        media_type="audio/wav",
                        data=(
                            "UklGRgAAAABXQVZFZm10IBAAAAABAAEA"
                            "ESsAACJWAAACABAAZGF0YQAAAAA="
                        ),
                    ),
                ),
                ThinkingBlock(type="thinking", thinking="Reasoning..."),
                ToolUseBlock(
                    type="tool_use",
                    id="tool1",
                    name="search_tool",
                    input={"query": "test"},
                ),
                ToolResultBlock(
                    type="tool_result",
                    id="tool1",
                    name="assistant",
                    output=[TextBlock(type="text", text="Tool results.")],
                ),
            ],
        ),
        [
            Msg(
                name="assistant",
                role="assistant",
                content=[
                    TextBlock(type="text", text="message one text"),
                    ThinkingBlock(type="thinking", thinking="Reasoning one"),
                ],
            ),
            Msg(
                name="assistant",
                role="assistant",
                content=[
                    ImageBlock(
                        type="image",
                        source=URLSource(
                            type="url",
                            url="http://example.com/img2.jpg",
                        ),
                    ),
                    ToolUseBlock(
                        type="tool_use",
                        id="tool2",
                        name="search_tool_2",
                        input={"query": "second message"},
                    ),
                ],
            ),
        ],
    ],
)
def test_round_trip_messages(msgs):
    _check_round_trip(msgs)


def _check_round_trip_runtime_messages(runtime_messages):
    """
    Performs a round-trip conversion check:
    Runtime Message -> Agentscope `Msg` -> Runtime Message.
    """

    def strip_irrelevant_fields(obj):
        """
        Recursively remove fields we want to ignore in the comparison.
        """
        ignore_keys = {
            "id",
            "metadata",
            "role",
            "type",  # function_call ↔ plugin_call
            "status",  # created ↔ completed
            "index",  # 0 ↔ null
            "msg_id",  # uuid ↔ null
            "sequence_number",  # number ↔ null
        }
        if isinstance(obj, dict):
            return {
                k: strip_irrelevant_fields(v)
                for k, v in obj.items()
                if k not in ignore_keys
            }
        elif isinstance(obj, list):
            return [strip_irrelevant_fields(i) for i in obj]
        else:
            return obj

    msgs = message_to_agentscope_msg(runtime_messages)
    assert isinstance(msgs, list)
    assert len(msgs) >= 1

    converted_runtime_messages = agentscope_msg_to_message(msgs)
    assert isinstance(converted_runtime_messages, list)
    assert len(converted_runtime_messages) == len(runtime_messages)

    orig_norm = strip_irrelevant_fields(normalize(runtime_messages))
    conv_norm = strip_irrelevant_fields(normalize(converted_runtime_messages))

    assert json.dumps(orig_norm, sort_keys=True) == json.dumps(
        conv_norm,
        sort_keys=True,
    )


@pytest.mark.parametrize(
    "request_data",
    [
        {
            "input": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "What's the weather in Hangzhou?",
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
                                "arguments": json.dumps(
                                    {"location": "Hangzhou"},
                                ),
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
                                "output": json.dumps(
                                    {"temperature": 25, "unit": "Celsius"},
                                ),
                            },
                        },
                    ],
                },
            ],
            "stream": True,
            "session_id": "123",
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "get_current_weather",
                        "description": "Get the current weather in a given "
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
    ],
)
def test_round_trip_agent_request(request_data):
    request = AgentRequest.model_validate(request_data)
    _check_round_trip_runtime_messages(request.input)
