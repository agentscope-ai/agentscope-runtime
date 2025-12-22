# -*- coding: utf-8 -*-
# pylint: disable=redefined-outer-name, protected-access
"""
Integration tests for AG-UI Protocol support.

Tests cover:
- End-to-end AG-UI request/response flow
- Integration with AgentApp
- Real streaming scenarios
- Complete message conversion workflows
"""
import json

import pytest
from ag_ui.core.types import (
    SystemMessage,
    UserMessage,
)
from fastapi import FastAPI
from fastapi.testclient import TestClient

from agentscope_runtime.engine.deployers.adapter.agui import (
    AGUIDefaultAdapter,
)
from agentscope_runtime.engine.schemas.agent_schemas import (
    AgentRequest,
    AgentResponse,
    DataContent,
    FunctionCall as AgentFunctionCall,
    Message,
    MessageType,
    Role,
    RunStatus,
    TextContent,
)


class TestAGUIEndToEndFlow:
    """Test end-to-end AG-UI request and response flow."""

    @pytest.mark.asyncio
    async def test_simple_text_exchange(self):
        """Test simple text exchange through AG-UI protocol."""
        adapter = AGUIDefaultAdapter()
        app = FastAPI()

        # Mock agent execution function
        async def mock_agent_execution(
            request: AgentRequest,
        ):  # pylint: disable=unused-argument
            # Yield created status
            yield AgentResponse(status=RunStatus.Created)

            # Yield text response
            msg = Message(
                id="msg_resp_1",
                type=MessageType.MESSAGE,
                role=Role.ASSISTANT,
                content=[TextContent(text="Hello! ", delta=True)],
            )
            yield msg

            msg2 = Message(
                id="msg_resp_1",
                type=MessageType.MESSAGE,
                role=Role.ASSISTANT,
                content=[TextContent(text="How can I help?", delta=True)],
            )
            yield msg2

            # Mark message as completed
            msg_completed = Message(
                id="msg_resp_1",
                type=MessageType.MESSAGE,
                role=Role.ASSISTANT,
                content=[
                    TextContent(text="Hello! How can I help?", delta=False),
                ],
                status=RunStatus.Completed,
            )
            yield msg_completed

            # Yield completion status
            yield AgentResponse(status=RunStatus.Completed)

        adapter.add_endpoint(app, mock_agent_execution)
        client = TestClient(app)

        # Send AG-UI request
        request_data = {
            "threadId": "test_thread",
            "runId": "test_run",
            "state": None,
            "tools": [],
            "context": [],
            "forwardedProps": None,
            "messages": [
                {
                    "id": "msg_1",
                    "role": "user",
                    "content": "Hello",
                },
            ],
        }

        response = client.post("/agui", json=request_data)

        assert response.status_code == 200
        assert (
            response.headers["content-type"]
            == "text/event-stream; charset=utf-8"
        )

        # Parse SSE events
        events = []
        for line in response.text.strip().split("\n\n"):
            if line.startswith("data: "):
                event_data = json.loads(line[6:])
                events.append(event_data)

        # Verify event sequence
        assert len(events) >= 3

        # Should have run.started
        assert any(e["type"] == "RUN_STARTED" for e in events)

        # Should have text message events
        text_events = [
            e
            for e in events
            if e["type"]
            in [
                "TEXT_MESSAGE_START",
                "TEXT_MESSAGE_CONTENT",
                "TEXT_MESSAGE_END",
            ]
        ]
        assert len(text_events) > 0

        # Should have run.finished
        assert any(e["type"] == "RUN_FINISHED" for e in events)

    @pytest.mark.asyncio
    async def test_multimodal_user_input(self):
        """Test handling multimodal user input (text + image)."""
        adapter = AGUIDefaultAdapter()
        app = FastAPI()

        received_request = None

        async def mock_agent_execution(request: AgentRequest):
            nonlocal received_request
            received_request = request

            yield AgentResponse(status=RunStatus.Created)
            yield AgentResponse(status=RunStatus.Completed)

        adapter.add_endpoint(app, mock_agent_execution)
        client = TestClient(app)

        # Send multimodal request
        request_data = {
            "threadId": "test_thread",
            "runId": "test_run",
            "state": None,
            "tools": [],
            "context": [],
            "forwardedProps": None,
            "messages": [
                {
                    "id": "msg_1",
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "What is in this image?"},
                        {
                            "type": "binary",
                            "mime_type": "image/jpeg",
                            "url": "http://example.com/test.jpg",
                        },
                    ],
                },
            ],
        }

        response = client.post("/agui", json=request_data)
        assert response.status_code == 200

        # Verify the agent received properly converted request
        assert received_request is not None
        assert len(received_request.input) == 1
        assert len(received_request.input[0].content) == 2
        assert (
            received_request.input[0].content[0].text
            == "What is in this image?"
        )
        # Second content should be image
        from agentscope_runtime.engine.schemas.agent_schemas import (
            ImageContent,
        )

        assert isinstance(received_request.input[0].content[1], ImageContent)

    @pytest.mark.asyncio
    async def test_tool_call_workflow(self):
        """Test complete tool call workflow through AG-UI."""
        adapter = AGUIDefaultAdapter()
        app = FastAPI()

        async def mock_agent_execution(
            request: AgentRequest,
        ):  # pylint: disable=unused-argument
            yield AgentResponse(status=RunStatus.Created)

            # Agent makes tool call
            tool_call_msg = Message(
                id="msg_tool_call",
                type=MessageType.FUNCTION_CALL,
                role=Role.ASSISTANT,
                content=[
                    DataContent(
                        data=AgentFunctionCall(
                            call_id="call_123",
                            name="get_weather",
                            arguments='{"city": "Tokyo"}',
                        ).model_dump(),
                    ),
                ],
            )
            yield tool_call_msg

            yield AgentResponse(status=RunStatus.Completed)

        adapter.add_endpoint(app, mock_agent_execution)
        client = TestClient(app)

        request_data = {
            "threadId": "test_thread",
            "runId": "test_run",
            "state": None,
            "tools": [],
            "context": [],
            "forwardedProps": None,
            "messages": [
                {
                    "id": "msg_1",
                    "role": "user",
                    "content": "What's the weather in Tokyo?",
                },
            ],
        }

        response = client.post("/agui", json=request_data)
        assert response.status_code == 200

        # Parse events
        events = []
        for line in response.text.strip().split("\n\n"):
            if line.startswith("data: "):
                event_data = json.loads(line[6:])
                events.append(event_data)

        # Should have tool call events
        tool_events = [
            e
            for e in events
            if e["type"]
            in ["TOOL_CALL_START", "TOOL_CALL_ARGS", "TOOL_CALL_END"]
        ]
        assert len(tool_events) >= 2

    @pytest.mark.asyncio
    async def test_conversation_with_history(self):
        """Test conversation with message history."""
        adapter = AGUIDefaultAdapter()
        app = FastAPI()

        received_request = None

        async def mock_agent_execution(
            request: AgentRequest,
        ):  # pylint: disable=unused-argument
            nonlocal received_request
            received_request = request

            yield AgentResponse(status=RunStatus.Created)
            yield AgentResponse(status=RunStatus.Completed)

        adapter.add_endpoint(app, mock_agent_execution)
        client = TestClient(app)

        # Send request with conversation history
        request_data = {
            "threadId": "test_thread",
            "runId": "test_run",
            "state": None,
            "tools": [],
            "context": [],
            "forwardedProps": None,
            "messages": [
                {
                    "id": "msg_1",
                    "role": "system",
                    "content": "You are a helpful assistant.",
                },
                {"id": "msg_2", "role": "user", "content": "What's 2+2?"},
                {
                    "id": "msg_3",
                    "role": "assistant",
                    "content": "2+2 equals 4.",
                },
                {"id": "msg_4", "role": "user", "content": "What about 3+3?"},
            ],
        }

        response = client.post("/agui", json=request_data)
        assert response.status_code == 200

        # Verify all messages were converted
        assert received_request is not None
        assert len(received_request.input) == 4
        assert received_request.input[0].role == Role.SYSTEM
        assert received_request.input[1].role == Role.USER
        assert received_request.input[2].role == Role.ASSISTANT
        assert received_request.input[3].role == Role.USER


class TestAGUIErrorScenarios:
    """Test error scenarios in AG-UI protocol."""

    @pytest.mark.asyncio
    async def test_agent_execution_error(self):
        """Test handling of agent execution error."""
        adapter = AGUIDefaultAdapter()
        app = FastAPI()

        async def mock_agent_execution(
            request: AgentRequest,
        ):  # pylint: disable=unused-argument
            yield AgentResponse(status=RunStatus.Created)
            raise RuntimeError("Agent execution failed")

        adapter.add_endpoint(app, mock_agent_execution)
        client = TestClient(app)

        request_data = {
            "threadId": "test_thread",
            "runId": "test_run",
            "state": None,
            "tools": [],
            "context": [],
            "forwardedProps": None,
            "messages": [{"id": "msg_1", "role": "user", "content": "Test"}],
        }

        response = client.post("/agui", json=request_data)
        assert response.status_code == 200

        # Parse events
        events = []
        for line in response.text.strip().split("\n\n"):
            if line.startswith("data: "):
                event_data = json.loads(line[6:])
                events.append(event_data)

        # Should have error event
        error_events = [e for e in events if e["type"] == "RUN_ERROR"]
        assert len(error_events) == 1
        assert "Agent execution failed" in error_events[0]["message"]

    @pytest.mark.asyncio
    async def test_agent_failure_response(self):
        """Test handling of agent failure response."""
        adapter = AGUIDefaultAdapter()
        app = FastAPI()

        async def mock_agent_execution(
            request: AgentRequest,
        ):  # pylint: disable=unused-argument
            yield AgentResponse(status=RunStatus.Created)

            from agentscope_runtime.engine.schemas.agent_schemas import (
                Error,
            )

            yield AgentResponse(
                status=RunStatus.Failed,
                error=Error(
                    code="internal_error",
                    message="Internal processing error",
                ),
            )

        adapter.add_endpoint(app, mock_agent_execution)
        client = TestClient(app)

        request_data = {
            "threadId": "test_thread",
            "runId": "test_run",
            "state": None,
            "tools": [],
            "context": [],
            "forwardedProps": None,
            "messages": [{"id": "msg_1", "role": "user", "content": "Test"}],
        }

        response = client.post("/agui", json=request_data)
        assert response.status_code == 200

        # Parse events
        events = []
        for line in response.text.strip().split("\n\n"):
            if line.startswith("data: "):
                event_data = json.loads(line[6:])
                events.append(event_data)

        # Should have error event
        error_events = [e for e in events if e["type"] == "RUN_ERROR"]
        assert len(error_events) == 1


class TestAGUIStreamingBehavior:
    """Test streaming behavior of AG-UI protocol."""

    @pytest.mark.asyncio
    async def test_streaming_text_deltas(self):
        """Test streaming text with multiple deltas."""
        adapter = AGUIDefaultAdapter()
        app = FastAPI()

        async def mock_agent_execution(
            request: AgentRequest,
        ):  # pylint: disable=unused-argument
            yield AgentResponse(status=RunStatus.Created)

            # Yield multiple text deltas
            words = ["Hello", " there", "!", " How", " are", " you", "?"]
            for word in words:
                msg = Message(
                    id="msg_1",
                    type=MessageType.MESSAGE,
                    role=Role.ASSISTANT,
                    content=[TextContent(text=word, delta=True, index=0)],
                )
                yield msg

            # Complete message
            final_msg = Message(
                id="msg_1",
                type=MessageType.MESSAGE,
                role=Role.ASSISTANT,
                content=[
                    TextContent(
                        text="Hello there! How are you?",
                        delta=False,
                        index=0,
                    ),
                ],
                status=RunStatus.Completed,
            )
            yield final_msg

            yield AgentResponse(status=RunStatus.Completed)

        adapter.add_endpoint(app, mock_agent_execution)
        client = TestClient(app)

        request_data = {
            "threadId": "test_thread",
            "runId": "test_run",
            "state": None,
            "tools": [],
            "context": [],
            "forwardedProps": None,
            "messages": [{"id": "msg_1", "role": "user", "content": "Hi"}],
        }

        response = client.post("/agui", json=request_data)
        assert response.status_code == 200

        # Parse events
        events = []
        for line in response.text.strip().split("\n\n"):
            if line.startswith("data: "):
                event_data = json.loads(line[6:])
                events.append(event_data)

        # Count text content events
        content_events = [
            e for e in events if e["type"] == "TEXT_MESSAGE_CONTENT"
        ]
        # Should have multiple content events (one for each delta)
        assert len(content_events) >= 5

        # Verify deltas are present
        deltas = [e["delta"] for e in content_events if "delta" in e]
        assert len(deltas) >= 5

    @pytest.mark.asyncio
    async def test_concurrent_messages(self):
        """Test handling multiple concurrent messages."""
        adapter = AGUIDefaultAdapter()
        app = FastAPI()

        async def mock_agent_execution(
            request: AgentRequest,
        ):  # pylint: disable=unused-argument
            yield AgentResponse(status=RunStatus.Created)

            # Yield two messages with different indices
            msg1 = Message(
                id="msg_1",
                type=MessageType.MESSAGE,
                role=Role.ASSISTANT,
                content=[TextContent(text="First part", delta=True, index=0)],
            )
            yield msg1

            msg2 = Message(
                id="msg_1",
                type=MessageType.MESSAGE,
                role=Role.ASSISTANT,
                content=[
                    TextContent(text="Second part", delta=True, index=1),
                ],
            )
            yield msg2

            # Complete both
            final_msg = Message(
                id="msg_1",
                type=MessageType.MESSAGE,
                role=Role.ASSISTANT,
                content=[
                    TextContent(text="First part", delta=False, index=0),
                    TextContent(text="Second part", delta=False, index=1),
                ],
                status=RunStatus.Completed,
            )
            yield final_msg

            yield AgentResponse(status=RunStatus.Completed)

        adapter.add_endpoint(app, mock_agent_execution)
        client = TestClient(app)

        request_data = {
            "threadId": "test_thread",
            "runId": "test_run",
            "state": None,
            "tools": [],
            "context": [],
            "forwardedProps": None,
            "messages": [{"id": "msg_1", "role": "user", "content": "Test"}],
        }

        response = client.post("/agui", json=request_data)
        assert response.status_code == 200

        # Parse events
        events = []
        for line in response.text.strip().split("\n\n"):
            if line.startswith("data: "):
                event_data = json.loads(line[6:])
                events.append(event_data)

        # Should have start events for different message IDs
        start_events = [e for e in events if e["type"] == "TEXT_MESSAGE_START"]
        # Should have 2 different message_ids (msg_1_0 and msg_1_1)
        message_ids = [e["message_id"] for e in start_events]
        assert len(set(message_ids)) >= 2


class TestAGUIThreadAndRunManagement:
    """Test thread_id and run_id management in AG-UI."""

    @pytest.mark.asyncio
    async def test_thread_and_run_id_propagation(self):
        """Test that thread_id and run_id are properly propagated."""
        adapter = AGUIDefaultAdapter()
        app = FastAPI()

        received_request = None

        async def mock_agent_execution(
            request: AgentRequest,
        ):  # pylint: disable=unused-argument
            nonlocal received_request
            received_request = request

            yield AgentResponse(status=RunStatus.Created)
            yield AgentResponse(status=RunStatus.Completed)

        adapter.add_endpoint(app, mock_agent_execution)
        client = TestClient(app)

        request_data = {
            "threadId": "custom_thread_123",
            "runId": "custom_run_456",
            "state": None,
            "tools": [],
            "context": [],
            "forwardedProps": None,
            "messages": [{"id": "msg_1", "role": "user", "content": "Test"}],
        }

        response = client.post("/agui", json=request_data)
        assert response.status_code == 200

        # Verify IDs propagated to agent request
        assert received_request is not None
        assert received_request.session_id == "custom_thread_123"
        assert received_request.id == "custom_run_456"

        # Parse events and verify IDs in events
        events = []
        for line in response.text.strip().split("\n\n"):
            if line.startswith("data: "):
                event_data = json.loads(line[6:])
                events.append(event_data)

        # Check run.started event
        run_started = [e for e in events if e["type"] == "RUN_STARTED"][0]
        assert run_started["thread_id"] == "custom_thread_123"
        assert run_started["run_id"] == "custom_run_456"


class TestAGUIMessageRoundTrip:
    """Test complete message round-trip through AG-UI protocol."""

    @pytest.mark.asyncio
    async def test_user_to_agent_message_conversion(
        self,
    ):  # pylint: disable=unused-argument
        """Test user message conversion from AG-UI to Agent API format."""
        # fmt: off
        from agentscope_runtime.engine.deployers.adapter.agui.agui_adapter_utils import (  # noqa: E501, pylint: disable=line-too-long
            convert_ag_ui_messages_to_agent_request_messages,
        )
        # fmt: on

        # Create AG-UI messages
        agui_messages = [
            SystemMessage(
                id="msg_sys",
                role="system",
                content="You are helpful.",
            ),
            UserMessage(
                id="msg_user",
                role="user",
                content="Hello",
            ),
        ]

        # Convert to Agent API format
        agent_messages = convert_ag_ui_messages_to_agent_request_messages(
            agui_messages,
        )

        assert len(agent_messages) == 2
        assert agent_messages[0].role == Role.SYSTEM
        assert agent_messages[0].content[0].text == "You are helpful."
        assert agent_messages[1].role == Role.USER
        assert agent_messages[1].content[0].text == "Hello"

    @pytest.mark.asyncio
    async def test_tool_call_round_trip(self):
        """Test tool call round-trip conversion."""
        adapter = AGUIDefaultAdapter()
        app = FastAPI()

        received_messages = None

        async def mock_agent_execution(
            request: AgentRequest,
        ):  # pylint: disable=unused-argument
            nonlocal received_messages
            received_messages = request.input

            yield AgentResponse(status=RunStatus.Created)
            yield AgentResponse(status=RunStatus.Completed)

        adapter.add_endpoint(app, mock_agent_execution)
        client = TestClient(app)

        # Send conversation with tool call and result
        request_data = {
            "threadId": "test_thread",
            "runId": "test_run",
            "state": None,
            "tools": [],
            "context": [],
            "forwardedProps": None,
            "messages": [
                {
                    "id": "msg_1",
                    "role": "user",
                    "content": "What's the weather?",
                },
                {
                    "id": "msg_2",
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "call_123",
                            "type": "function",
                            "function": {
                                "name": "get_weather",
                                "arguments": '{"city": "Tokyo"}',
                            },
                        },
                    ],
                },
                {
                    "id": "msg_3",
                    "role": "tool",
                    "tool_call_id": "call_123",
                    "content": "Sunny, 25°C",
                },
            ],
        }

        response = client.post("/agui", json=request_data)
        assert response.status_code == 200

        # Verify conversions
        assert received_messages is not None
        assert len(received_messages) == 3
        # pylint: disable=unsubscriptable-object
        assert received_messages[0].role == Role.USER
        assert received_messages[1].type == MessageType.FUNCTION_CALL
        assert received_messages[2].type == MessageType.FUNCTION_CALL_OUTPUT


class TestAGUIUnicodeAndSpecialChars:
    """Test handling of Unicode and special characters."""

    @pytest.mark.asyncio
    async def test_unicode_in_messages(
        self,
    ):  # pylint: disable=unused-argument
        """Test handling Unicode characters in messages."""
        adapter = AGUIDefaultAdapter()
        app = FastAPI()

        async def mock_agent_execution(
            request: AgentRequest,
        ):  # pylint: disable=unused-argument
            yield AgentResponse(status=RunStatus.Created)

            msg = Message(
                id="msg_1",
                type=MessageType.MESSAGE,
                role=Role.ASSISTANT,
                content=[TextContent(text="你好世界! 🌍🚀", delta=True)],
            )
            yield msg

            yield AgentResponse(status=RunStatus.Completed)

        adapter.add_endpoint(app, mock_agent_execution)
        client = TestClient(app)

        request_data = {
            "threadId": "test_thread",
            "runId": "test_run",
            "state": None,
            "tools": [],
            "context": [],
            "forwardedProps": None,
            "messages": [
                {"id": "msg_1", "role": "user", "content": "测试 emoji 😊"},
            ],
        }

        response = client.post("/agui", json=request_data)
        assert response.status_code == 200

        # Verify Unicode is preserved
        events = []
        for line in response.text.strip().split("\n\n"):
            if line.startswith("data: "):
                event_data = json.loads(line[6:])
                events.append(event_data)

        content_events = [
            e for e in events if e["type"] == "TEXT_MESSAGE_CONTENT"
        ]
        if content_events:
            assert "你好世界! 🌍🚀" in str(content_events)
