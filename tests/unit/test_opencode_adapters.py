# -*- coding: utf-8 -*-
import copy
import json
import mimetypes

import pytest

from agentscope_runtime.adapters.opencode.message import (
    message_to_opencode_parts,
)
from agentscope_runtime.adapters.opencode.stream import (
    adapt_opencode_message_stream,
)
from agentscope_runtime.engine.schemas.agent_schemas import (
    AudioContent,
    ContentType,
    DataContent,
    FileContent,
    ImageContent,
    Message,
    MessageType,
    RefusalContent,
    Role,
    RunStatus,
    TextContent,
)


def test_message_to_opencode_parts_prefers_user_message() -> None:
    user_message = Message(
        type=MessageType.MESSAGE,
        role=Role.USER,
        content=[
            TextContent(text="Hello"),
            DataContent(data={"key": "value"}),
            RefusalContent(refusal="nope"),
        ],
    )
    assistant_message = Message(
        type=MessageType.MESSAGE,
        role=Role.ASSISTANT,
        content=[TextContent(text="Ignore me")],
    )

    parts = message_to_opencode_parts([user_message, assistant_message])

    assert len(parts) == 3
    assert parts[0] == {"type": "text", "text": "Hello"}
    assert json.loads(parts[1]["text"]) == {"key": "value"}
    assert json.loads(parts[2]["text"]) == "nope"


def test_message_to_opencode_parts_handles_media_and_files() -> None:
    message = Message(
        type=MessageType.MESSAGE,
        role=Role.USER,
        content=[
            ImageContent(image_url="http://example.com/image.png"),
            AudioContent(data="http://example.com/audio.wav"),
            FileContent(
                file_url="http://example.com/report.txt",
                filename="report.txt",
            ),
        ],
    )

    parts = message_to_opencode_parts(message)

    assert len(parts) == 3
    assert all(part["type"] == "file" for part in parts)

    expected_image_mime = (
        mimetypes.guess_type("http://example.com/image.png")[0]
        or "application/octet-stream"
    )
    expected_audio_mime = (
        mimetypes.guess_type("http://example.com/audio.wav")[0]
        or "application/octet-stream"
    )
    expected_file_mime = (
        mimetypes.guess_type("http://example.com/report.txt")[0]
        or "application/octet-stream"
    )

    assert parts[0]["url"] == "http://example.com/image.png"
    assert parts[0]["mime"] == expected_image_mime

    assert parts[1]["url"] == "http://example.com/audio.wav"
    assert parts[1]["mime"] == expected_audio_mime

    assert parts[2]["url"] == "http://example.com/report.txt"
    assert parts[2]["mime"] == expected_file_mime
    assert parts[2]["filename"] == "report.txt"


@pytest.mark.asyncio
async def test_adapt_opencode_message_stream_text_and_usage() -> None:
    events = [
        {
            "payload": {
                "type": "message.updated",
                "properties": {
                    "info": {
                        "id": "msg_1",
                        "role": "assistant",
                        "agent": "agent-a",
                        "tokens": {"input": 1, "output": 2},
                    },
                },
            },
        },
        {
            "directory": "/",
            "payload": {
                "type": "message.part.updated",
                "properties": {
                    "part": {
                        "id": "part_1",
                        "messageID": "msg_1",
                        "sessionID": "ses_1",
                        "type": "text",
                        "text": "Hello",
                    },
                    "delta": "Hello",
                },
            },
        },
        {
            "directory": "/",
            "payload": {
                "type": "message.part.updated",
                "properties": {
                    "part": {
                        "id": "part_1",
                        "messageID": "msg_1",
                        "sessionID": "ses_1",
                        "type": "text",
                        "text": "Hello world",
                        "time": {"end": "t1"},
                    },
                    "delta": " world",
                },
            },
        },
    ]

    items = await _collect_stream_events(events)
    messages = [item for item in items if item.object == "message"]
    contents = [item for item in items if item.object == "content"]

    completed_messages = [
        message
        for message in messages
        if message.status == RunStatus.Completed
    ]
    assert len(completed_messages) == 1
    final_message = completed_messages[0]

    assert final_message.metadata is not None
    assert final_message.metadata["agent_name"] == "agent-a"
    assert final_message.usage is not None
    assert final_message.usage["input_tokens"] == 1
    assert final_message.usage["output_tokens"] == 2

    assert final_message.content is not None
    assert final_message.content[0].text == "Hello world"

    delta_text = "".join(
        content.text
        for content in contents
        if content.type == ContentType.TEXT and content.delta
    )
    assert delta_text == "Hello world"


@pytest.mark.asyncio
async def test_global_idle_event_does_not_terminate_stream() -> None:
    events = [
        {
            "payload": {
                "type": "session.idle",
                "properties": {"sessionID": "ses_child"},
            },
        },
        {
            "payload": {
                "type": "message.part.updated",
                "properties": {
                    "part": {
                        "id": "part_idle_1",
                        "messageID": "msg_idle_1",
                        "sessionID": "ses_main",
                        "type": "text",
                        "text": "Hello",
                    },
                    "delta": "Hello",
                },
            },
        },
        {
            "payload": {
                "type": "message.part.updated",
                "properties": {
                    "part": {
                        "id": "part_idle_1",
                        "messageID": "msg_idle_1",
                        "sessionID": "ses_main",
                        "type": "text",
                        "text": "Hello world",
                        "time": {"end": "t1"},
                    },
                    "delta": " world",
                },
            },
        },
    ]

    items = await _collect_stream_events(events)
    messages = [item for item in items if item.object == "message"]
    completed_messages = [
        message
        for message in messages
        if message.status == RunStatus.Completed
    ]

    assert len(completed_messages) == 1
    assert completed_messages[0].content is not None
    assert completed_messages[0].content[0].text == "Hello world"


async def _collect_stream_events(events):
    results = []
    async for item in adapt_opencode_message_stream(_event_stream(events)):
        results.append(copy.deepcopy(item))
    return results


async def _event_stream(events):
    for event in events:
        yield event
