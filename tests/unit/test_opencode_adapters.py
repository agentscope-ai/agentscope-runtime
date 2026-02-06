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
from agentscope_runtime.engine.schemas.exception import (
    AgentRuntimeErrorException,
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


@pytest.mark.asyncio
async def test_adapt_opencode_tool_part_emits_call_and_output() -> None:
    events = [
        {
            "payload": {
                "type": "message.updated",
                "properties": {
                    "info": {
                        "id": "msg_tool",
                        "role": "assistant",
                        "agent": "AgentTool",
                    },
                },
            },
        },
        {
            "payload": {
                "type": "message.part.updated",
                "properties": {
                    "part": {
                        "id": "part_tool",
                        "messageID": "msg_tool",
                        "sessionID": "ses_tool",
                        "type": "tool",
                        "callID": "call_1",
                        "tool": "search",
                        "state": {
                            "status": "running",
                            "input": {"query": "hi"},
                        },
                    },
                },
            },
        },
        {
            "payload": {
                "type": "message.part.updated",
                "properties": {
                    "part": {
                        "id": "part_tool",
                        "messageID": "msg_tool",
                        "sessionID": "ses_tool",
                        "type": "tool",
                        "callID": "call_1",
                        "tool": "search",
                        "state": {
                            "status": "completed",
                            "input": {"query": "hi"},
                            "output": {"result": "ok"},
                        },
                    },
                },
            },
        },
    ]

    items = await _collect_stream_events(events)
    completed_messages = [
        item
        for item in items
        if item.object == "message" and item.status == RunStatus.Completed
    ]

    plugin_call = next(
        message
        for message in completed_messages
        if message.type == MessageType.PLUGIN_CALL
    )
    plugin_output = next(
        message
        for message in completed_messages
        if message.type == MessageType.PLUGIN_CALL_OUTPUT
    )

    assert plugin_call.content is not None
    call_data = plugin_call.content[0].data
    assert call_data["call_id"] == "call_1"
    assert call_data["name"] == "search"
    assert json.loads(call_data["arguments"]) == {"query": "hi"}

    assert plugin_output.role == Role.TOOL
    assert plugin_output.content is not None
    output_data = plugin_output.content[0].data
    assert output_data["call_id"] == "call_1"
    assert output_data["name"] == "search"
    assert json.loads(output_data["output"]) == {"output": {"result": "ok"}}


@pytest.mark.asyncio
async def test_adapt_opencode_step_finish_usage_applied() -> None:
    events = [
        {
            "payload": {
                "type": "message.part.updated",
                "properties": {
                    "part": {
                        "id": "part_step",
                        "messageID": "msg_step",
                        "sessionID": "ses_step",
                        "type": "step-finish",
                        "cost": 0.25,
                        "tokens": {
                            "input": 3,
                            "output": 4,
                            "reasoning": 1,
                            "cache": {"read": 2, "write": 0},
                        },
                    },
                },
            },
        },
        {
            "payload": {
                "type": "message.part.updated",
                "properties": {
                    "part": {
                        "id": "part_step_text",
                        "messageID": "msg_step",
                        "sessionID": "ses_step",
                        "type": "text",
                        "text": "done",
                        "time": {"end": "t1"},
                    },
                    "delta": "done",
                },
            },
        },
    ]

    items = await _collect_stream_events(events)
    completed_messages = [
        item
        for item in items
        if item.object == "message" and item.status == RunStatus.Completed
    ]
    assert len(completed_messages) == 1
    message = completed_messages[0]

    assert message.usage is not None
    assert message.usage["input_tokens"] == 3
    assert message.usage["output_tokens"] == 4
    assert message.usage["reasoning_tokens"] == 1
    assert message.usage["cache_read_tokens"] == 2
    assert message.usage["cache_write_tokens"] == 0
    assert message.usage["cost"] == 0.25

    assert message.content is not None
    assert message.content[0].text == "done"


@pytest.mark.asyncio
async def test_adapt_opencode_message_removed_events() -> None:
    events = [
        {
            "payload": {
                "type": "message.part.removed",
                "properties": {
                    "sessionID": "ses_rm",
                    "messageID": "msg_rm",
                    "partID": "part_rm",
                },
            },
        },
        {
            "payload": {
                "type": "message.removed",
                "properties": {
                    "sessionID": "ses_rm",
                    "messageID": "msg_rm",
                },
            },
        },
    ]

    items = await _collect_stream_events(events)
    completed_messages = [
        item
        for item in items
        if item.object == "message" and item.status == RunStatus.Completed
    ]
    opencode_types = []
    for message in completed_messages:
        assert message.content is not None
        part = message.content[0].data["opencode_part"]
        opencode_types.append(part["type"])

    assert "part-removed" in opencode_types
    assert "message-removed" in opencode_types


@pytest.mark.asyncio
async def test_adapt_opencode_session_error_raises() -> None:
    events = [
        {
            "payload": {
                "type": "session.error",
                "properties": {
                    "error": {"name": "OpencodeError", "message": "boom"},
                },
            },
        },
    ]

    with pytest.raises(AgentRuntimeErrorException) as exc_info:
        async for _ in adapt_opencode_message_stream(_event_stream(events)):
            pass

    assert exc_info.value.code == "OPENCODE_SESSION_ERROR"
    assert "OpencodeError" in exc_info.value.message


@pytest.mark.asyncio
async def test_adapt_opencode_ignored_text_part_skipped() -> None:
    events = [
        {
            "payload": {
                "type": "message.part.updated",
                "properties": {
                    "part": {
                        "id": "part_ignore",
                        "messageID": "msg_ignore",
                        "sessionID": "ses_ignore",
                        "type": "text",
                        "text": "ignore",
                        "ignored": True,
                    },
                },
            },
        },
    ]

    items = await _collect_stream_events(events)
    assert items == []


@pytest.mark.asyncio
async def test_adapt_opencode_text_delta_without_delta_field() -> None:
    events = [
        {
            "payload": {
                "type": "message.part.updated",
                "properties": {
                    "part": {
                        "id": "part_delta",
                        "messageID": "msg_delta",
                        "sessionID": "ses_delta",
                        "type": "text",
                        "text": "Hello",
                    },
                },
            },
        },
        {
            "payload": {
                "type": "message.part.updated",
                "properties": {
                    "part": {
                        "id": "part_delta",
                        "messageID": "msg_delta",
                        "sessionID": "ses_delta",
                        "type": "text",
                        "text": "Hello world",
                        "time": {"end": "t1"},
                    },
                },
            },
        },
    ]

    items = await _collect_stream_events(events)
    contents = [
        item
        for item in items
        if item.object == "content"
        and item.type == ContentType.TEXT
        and item.delta
    ]
    delta_text = "".join(content.text for content in contents)
    assert delta_text == "Hello world"


@pytest.mark.asyncio
async def test_adapt_opencode_file_part_emits_file_content() -> None:
    events = [
        {
            "payload": {
                "type": "message.part.updated",
                "properties": {
                    "part": {
                        "id": "part_file",
                        "messageID": "msg_file",
                        "sessionID": "ses_file",
                        "type": "file",
                        "url": "http://example.com/file.txt",
                        "filename": "file.txt",
                    },
                },
            },
        },
    ]

    items = await _collect_stream_events(events)
    completed_messages = [
        item
        for item in items
        if item.object == "message" and item.status == RunStatus.Completed
    ]
    assert len(completed_messages) == 1
    message = completed_messages[0]
    assert message.content is not None
    file_content = message.content[0]
    assert file_content.type == ContentType.FILE
    assert file_content.file_url == "http://example.com/file.txt"
    assert file_content.filename == "file.txt"


@pytest.mark.asyncio
async def test_adapt_opencode_unknown_event_emits_data_message() -> None:
    events = [
        {
            "payload": {
                "type": "tui.toast.show",
                "properties": {"title": "hello"},
            },
        },
    ]

    items = await _collect_stream_events(events)
    completed_messages = [
        item
        for item in items
        if item.object == "message" and item.status == RunStatus.Completed
    ]
    assert len(completed_messages) == 1
    message = completed_messages[0]
    assert message.content is not None
    part = message.content[0].data["opencode_part"]
    assert part["type"] == "event"
    assert part["event"] == "tui.toast.show"
    assert part["properties"]["title"] == "hello"


async def _collect_stream_events(events):
    results = []
    async for item in adapt_opencode_message_stream(_event_stream(events)):
        results.append(copy.deepcopy(item))
    return results


async def _event_stream(events):
    for event in events:
        yield event
