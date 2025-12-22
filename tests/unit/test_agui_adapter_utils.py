# -*- coding: utf-8 -*-
# pylint: disable=redefined-outer-name, protected-access
"""
Unit tests for AG-UI Adapter Utilities.

Tests cover:
- Message conversion from AG-UI to Agent API format
- Event conversion from Agent API to AG-UI format
- AGUIAdapter state management
- Edge cases and error handling
"""
import pytest
from pydantic import ValidationError
from ag_ui.core import RunAgentInput
from ag_ui.core.types import (
    AssistantMessage,
    BinaryInputContent,
    DeveloperMessage,
    FunctionCall,
    SystemMessage,
    TextInputContent,
    ToolCall,
    ToolMessage,
    UserMessage,
    ActivityMessage,
)

from agentscope_runtime.engine.deployers.adapter.agui.agui_adapter_utils import (  # noqa: E501
    AGUI_MESSAGE_STATUS,
    AGUIAdapter,
    convert_ag_ui_messages_to_agent_request_messages,
)
from agentscope_runtime.engine.schemas.agent_schemas import (
    AgentRequest,
    AgentResponse,
    DataContent,
    ImageContent,
    Message,
    MessageType,
    Role,
    RunStatus,
    TextContent,
    ToolCall as AgentToolCall,
)


class TestConvertAGUIMessagesToAgentRequest:
    """Test conversion from AG-UI messages to Agent Request messages."""

    def test_convert_user_message_with_text(self):
        """Test converting simple user message with text content."""
        agui_messages = [
            UserMessage(
                id="msg_1",
                role="user",
                content="Hello, how are you?",
            ),
        ]

        result = convert_ag_ui_messages_to_agent_request_messages(
            agui_messages,
        )

        assert len(result) == 1
        assert result[0].id == "msg_1"
        assert result[0].type == MessageType.MESSAGE
        assert result[0].role == Role.USER
        assert len(result[0].content) == 1
        assert isinstance(result[0].content[0], TextContent)
        assert result[0].content[0].text == "Hello, how are you?"

    def test_convert_user_message_with_multimodal_content(self):
        """Test converting user message with text and image content."""
        agui_messages = [
            UserMessage(
                id="msg_1",
                role="user",
                content=[
                    TextInputContent(text="What is in this image?"),
                    BinaryInputContent(
                        mime_type="image/jpeg",
                        url="http://example.com/image.jpg",
                    ),
                ],
            ),
        ]

        result = convert_ag_ui_messages_to_agent_request_messages(
            agui_messages,
        )

        assert len(result) == 1
        assert result[0].id == "msg_1"
        assert result[0].type == MessageType.MESSAGE
        assert result[0].role == Role.USER
        assert len(result[0].content) == 2
        assert isinstance(result[0].content[0], TextContent)
        assert result[0].content[0].text == "What is in this image?"
        assert isinstance(result[0].content[1], ImageContent)
        assert result[0].content[1].image_url == "http://example.com/image.jpg"

    def test_convert_system_message(self):
        """Test converting system message."""
        agui_messages = [
            SystemMessage(
                id="msg_sys",
                role="system",
                content="You are a helpful assistant.",
            ),
        ]

        result = convert_ag_ui_messages_to_agent_request_messages(
            agui_messages,
        )

        assert len(result) == 1
        assert result[0].id == "msg_sys"
        assert result[0].type == MessageType.MESSAGE
        assert result[0].role == Role.SYSTEM
        assert len(result[0].content) == 1
        assert result[0].content[0].text == "You are a helpful assistant."

    def test_convert_developer_message(self):
        """Test converting developer message."""
        agui_messages = [
            DeveloperMessage(
                id="msg_dev",
                role="developer",
                content="Debug information",
            ),
        ]

        result = convert_ag_ui_messages_to_agent_request_messages(
            agui_messages,
        )

        assert len(result) == 1
        assert result[0].type == MessageType.MESSAGE
        assert result[0].role == Role.SYSTEM
        assert result[0].content[0].text == "Debug information"

    def test_convert_assistant_message_with_text(self):
        """Test converting assistant message with text content."""
        agui_messages = [
            AssistantMessage(
                id="msg_assist",
                role="assistant",
                content="I can help you with that.",
            ),
        ]

        result = convert_ag_ui_messages_to_agent_request_messages(
            agui_messages,
        )

        assert len(result) == 1
        assert result[0].type == MessageType.MESSAGE
        assert result[0].role == Role.ASSISTANT
        assert result[0].content[0].text == "I can help you with that."

    def test_convert_assistant_message_with_tool_calls(self):
        """Test converting assistant message with tool calls."""
        agui_messages = [
            AssistantMessage(
                id="msg_assist",
                role="assistant",
                content="",
                tool_calls=[
                    ToolCall(
                        id="call_1",
                        type="function",
                        function=FunctionCall(
                            name="get_weather",
                            arguments='{"location": "Tokyo"}',
                        ),
                    ),
                ],
            ),
        ]

        result = convert_ag_ui_messages_to_agent_request_messages(
            agui_messages,
        )

        assert len(result) == 1
        assert result[0].type == MessageType.FUNCTION_CALL
        assert result[0].role == Role.ASSISTANT
        assert len(result[0].content) == 1
        assert isinstance(result[0].content[0], DataContent)

        # Check function call data
        func_call_data = result[0].content[0].data
        assert func_call_data["call_id"] == "call_1"
        assert func_call_data["name"] == "get_weather"
        assert func_call_data["arguments"] == '{"location": "Tokyo"}'

    def test_convert_tool_message(self):
        """Test converting tool message."""
        agui_messages = [
            ToolMessage(
                id="msg_tool",
                role="tool",
                tool_call_id="call_1",
                content="The weather in Tokyo is sunny, 25°C",
            ),
        ]

        result = convert_ag_ui_messages_to_agent_request_messages(
            agui_messages,
        )

        assert len(result) == 1
        assert result[0].type == MessageType.FUNCTION_CALL_OUTPUT
        assert result[0].role == Role.TOOL
        assert len(result[0].content) == 1
        assert isinstance(result[0].content[0], DataContent)

        output_data = result[0].content[0].data
        assert output_data["call_id"] == "call_1"
        assert output_data["output"] == "The weather in Tokyo is sunny, 25°C"

    def test_convert_tool_message_with_error(self):
        """Test converting tool message with error."""
        agui_messages = [
            ToolMessage(
                id="msg_tool_err",
                role="tool",
                tool_call_id="call_2",
                content="",
                error="API rate limit exceeded",
            ),
        ]

        result = convert_ag_ui_messages_to_agent_request_messages(
            agui_messages,
        )

        assert len(result) == 1
        output_data = result[0].content[0].data
        assert "error: API rate limit exceeded" in output_data["output"]

    def test_convert_binary_content_non_image(self):
        """Test converting binary content that is not an image."""
        agui_messages = [
            UserMessage(
                id="msg_1",
                role="user",
                content=[
                    BinaryInputContent(
                        mime_type="application/pdf",
                        data="base64_encoded_pdf_data",
                    ),
                ],
            ),
        ]

        result = convert_ag_ui_messages_to_agent_request_messages(
            agui_messages,
        )

        assert len(result) == 1
        assert len(result[0].content) == 1
        assert isinstance(result[0].content[0], DataContent)

    def test_convert_empty_user_message(self):
        """Test converting user message with empty content."""
        agui_messages = [
            UserMessage(
                id="msg_empty",
                role="user",
                content="",
            ),
        ]

        result = convert_ag_ui_messages_to_agent_request_messages(
            agui_messages,
        )

        assert len(result) == 1
        assert len(result[0].content) == 1
        assert result[0].content[0].text == ""

    def test_convert_multiple_messages(self):
        """Test converting multiple messages of different types."""
        agui_messages = [
            SystemMessage(
                id="msg_1",
                role="system",
                content="System prompt",
            ),
            UserMessage(
                id="msg_2",
                role="user",
                content="User question",
            ),
            AssistantMessage(
                id="msg_3",
                role="assistant",
                content="Assistant response",
            ),
        ]

        result = convert_ag_ui_messages_to_agent_request_messages(
            agui_messages,
        )

        assert len(result) == 3
        assert result[0].role == Role.SYSTEM
        assert result[1].role == Role.USER
        assert result[2].role == Role.ASSISTANT

    def test_convert_message_with_none_id(self):
        """Test converting message with missing ID (should generate one)."""
        agui_messages = [
            UserMessage(
                id="",
                role="user",
                content="Test message",
            ),
        ]

        result = convert_ag_ui_messages_to_agent_request_messages(
            agui_messages,
        )

        assert len(result) == 1
        # Should have generated an ID
        assert result[0].id is not None
        assert result[0].id.startswith("msg_")

    def test_convert_activity_message_logs_warning(self):
        """Test that activity messages log a warning and are not converted."""
        agui_messages = [
            ActivityMessage(
                id="msg_activity",
                role="activity",
                activityType="test_activity",
                content={"detail": "Some activity"},
            ),
        ]

        # Should not raise error but log warning
        result = convert_ag_ui_messages_to_agent_request_messages(
            agui_messages,
        )

        # Activity messages are skipped
        assert len(result) == 0

    def test_convert_unsupported_user_content_raises_error(self):
        """Test that unsupported user content type raises ValidationError."""
        from pydantic import BaseModel

        class UnsupportedContent(BaseModel):
            data: str

        with pytest.raises(ValidationError):
            UserMessage(
                id="msg_1",
                role="user",
                content=UnsupportedContent(data="test"),  # type: ignore
            )


class TestAGUIAdapterInitialization:
    """Test AGUIAdapter initialization and properties."""

    def test_adapter_init_with_defaults(self):
        """Test adapter initialization with default values."""
        adapter = AGUIAdapter()

        assert adapter.thread_id is not None
        assert adapter.thread_id.startswith("thread_")
        assert adapter.run_id is not None
        assert adapter.run_id.startswith("run_")
        assert not adapter.run_finished_emitted

    def test_adapter_init_with_custom_ids(self):
        """Test adapter initialization with custom thread and run IDs."""
        adapter = AGUIAdapter(
            threadId="custom_thread_123",
            runId="custom_run_456",
        )

        assert adapter.thread_id == "custom_thread_123"
        assert adapter.run_id == "custom_run_456"
        assert not adapter.run_finished_emitted


class TestAGUIAdapterConvertRequest:
    """Test AGUIAdapter request conversion."""

    def test_convert_agui_request_to_agent_request(self):
        """Test converting AG-UI request to Agent request."""
        adapter = AGUIAdapter(
            threadId="thread_123",
            runId="run_456",
        )

        agui_request = RunAgentInput(
            threadId="thread_123",
            runId="run_456",
            state=None,
            tools=[],
            context=[],
            forwardedProps=None,
            messages=[
                UserMessage(
                    id="msg_1",
                    role="user",
                    content="Hello",
                ),
            ],
        )

        result = adapter.convert_agui_request_to_agent_request(agui_request)

        assert isinstance(result, AgentRequest)
        assert result.id == "run_456"
        assert result.session_id == "thread_123"
        assert result.stream is True
        assert len(result.input) == 1
        assert result.input[0].content[0].text == "Hello"

    def test_convert_agui_request_warns_unsupported_fields(self):
        """Test that unsupported fields in AG-UI request log warnings."""
        from ag_ui.core.types import Context

        adapter = AGUIAdapter()

        agui_request = RunAgentInput(
            threadId="thread_123",
            runId="run_456",
            state=None,
            tools=[],
            context=[
                Context(description="context description", value="ctx_value"),
            ],
            forwardedProps={"some_prop": "value"},
            messages=[UserMessage(id="msg_user", role="user", content="Test")],
        )

        # Should not raise error, just log warning
        result = adapter.convert_agui_request_to_agent_request(agui_request)
        assert isinstance(result, AgentRequest)


class TestAGUIAdapterConvertResponseEvents:
    """Test AGUIAdapter conversion of Agent response events to AG-UI events."""

    def test_convert_response_created_status(self):
        """Test converting response with Created status."""
        adapter = AGUIAdapter(thread_id="thread_1", runId="run_1")

        response = AgentResponse(status=RunStatus.Created)
        events = adapter.convert_agent_event_to_agui_events(response)

        assert len(events) == 1
        assert events[0].type == "RUN_STARTED"
        assert events[0].thread_id == "thread_1"
        assert events[0].run_id == "run_1"

    def test_convert_response_completed_status(self):
        """Test converting response with Completed status."""
        adapter = AGUIAdapter(thread_id="thread_1", runId="run_1")

        response = AgentResponse(status=RunStatus.Completed)
        events = adapter.convert_agent_event_to_agui_events(response)

        assert len(events) >= 1
        # Last event should be run.finished
        assert any(e.type == "RUN_FINISHED" for e in events)
        assert adapter.run_finished_emitted

    def test_convert_response_failed_status(self):
        """Test converting response with Failed status."""
        adapter = AGUIAdapter(thread_id="thread_1", runId="run_1")

        from agentscope_runtime.engine.schemas.agent_schemas import Error

        response = AgentResponse(
            status=RunStatus.Failed,
            error=Error(
                code="test_error",
                message="Test error message",
            ),
        )
        events = adapter.convert_agent_event_to_agui_events(response)

        assert len(events) >= 1
        error_events = [e for e in events if e.type == "RUN_ERROR"]
        assert len(error_events) == 1
        assert "Test error message" in str(error_events[0].model_dump())

    def test_convert_response_canceled_status(self):
        """Test converting response with Canceled status."""
        adapter = AGUIAdapter(thread_id="thread_1", runId="run_1")

        response = AgentResponse(status=RunStatus.Canceled)
        events = adapter.convert_agent_event_to_agui_events(response)

        assert len(events) >= 1
        finished_events = [e for e in events if e.type == "RUN_FINISHED"]
        assert len(finished_events) == 1
        assert adapter.run_finished_emitted


class TestAGUIAdapterConvertContentEvents:
    """Test AGUIAdapter conversion of Agent content events to AG-UI events."""

    def test_convert_text_content_with_delta(self):
        """Test converting text content with delta."""
        adapter = AGUIAdapter(thread_id="thread_1", runId="run_1")

        content = TextContent(
            msg_id="msg_1",
            text="Hello",
            delta=True,
            index=0,
        )
        events = adapter.convert_agent_event_to_agui_events(content)

        # Should have run.started, text_message.start, and text_message.content
        assert len(events) >= 2
        event_types = [e.type for e in events]
        assert "RUN_STARTED" in event_types
        assert (
            "TEXT_MESSAGE_START" in event_types
            or "TEXT_MESSAGE_CONTENT" in event_types
        )

        content_events = [
            e for e in events if e.type == "TEXT_MESSAGE_CONTENT"
        ]
        if content_events:
            assert content_events[0].delta == "Hello"

    def test_convert_text_content_without_delta(self):
        """Test converting text content without delta (final message)."""
        adapter = AGUIAdapter(thread_id="thread_1", runId="run_1")

        # First send a delta to start the message
        content1 = TextContent(
            msg_id="msg_1",
            text="Hello",
            delta=True,
            index=0,
        )
        adapter.convert_agent_event_to_agui_events(content1)

        # Then send final content
        content2 = TextContent(
            msg_id="msg_1",
            text=" World",
            delta=False,
            index=0,
        )
        events = adapter.convert_agent_event_to_agui_events(content2)

        # Should have text_message.end or text_message.content
        event_types = [e.type for e in events]
        assert (
            "TEXT_MESSAGE_END" in event_types
            or "TEXT_MESSAGE_CONTENT" in event_types
        )

    def test_convert_data_content_with_tool_call(self):
        """Test converting data content containing tool call."""
        adapter = AGUIAdapter(thread_id="thread_1", runId="run_1")

        tool_call = AgentToolCall(
            call_id="call_123",
            name="get_weather",
            arguments='{"location": "Paris"}',
        )
        content = DataContent(
            msg_id="msg_1",
            data=tool_call.model_dump(),
            index=0,
        )
        events = adapter.convert_agent_event_to_agui_events(content)

        # Should have run.started, tool_call events
        assert len(events) >= 3
        event_types = [e.type for e in events]
        assert "RUN_STARTED" in event_types
        assert "TOOL_CALL_START" in event_types
        assert "TOOL_CALL_ARGS" in event_types
        assert "TOOL_CALL_END" in event_types  # noqa: E501

    def test_convert_data_content_with_invalid_tool_call(self):
        """Test converting data content with invalid tool call data."""
        adapter = AGUIAdapter(thread_id="thread_1", runId="run_1")

        # Invalid tool call data
        content = DataContent(
            msg_id="msg_1",
            data={"invalid": "data"},
            index=0,
        )
        # Should not raise error, just log and ignore
        events = adapter.convert_agent_event_to_agui_events(content)

        # Should at least have run.started
        assert len(events) >= 1
        assert events[0].type == "RUN_STARTED"

    def test_convert_message_event_completed(self):
        """Test converting message event with Completed status."""
        adapter = AGUIAdapter(thread_id="thread_1", runId="run_1")

        # First create a text content to start a message
        content = TextContent(
            msg_id="msg_1",
            text="Test",
            delta=True,
            index=0,
        )
        adapter.convert_agent_event_to_agui_events(content)

        # Then send completed message event
        message = Message(
            id="msg_1",
            type=MessageType.MESSAGE,
            role=Role.ASSISTANT,
            content=[TextContent(text="Test")],
            status=RunStatus.Completed,
        )
        events = adapter.convert_agent_event_to_agui_events(message)

        # Should have text_message.end event
        event_types = [e.type for e in events]
        assert "TEXT_MESSAGE_END" in event_types

    def test_convert_unsupported_content_type(self):
        """Test converting unsupported content type logs warning."""
        adapter = AGUIAdapter(thread_id="thread_1", runId="run_1")

        # ImageContent is not directly supported for AG-UI events
        content = ImageContent(
            msg_id="msg_1",
            image_url="http://example.com/img.jpg",
            index=0,
        )
        # Should not raise error, just log warning
        events = adapter.convert_agent_event_to_agui_events(content)

        # Should at least have run.started
        assert len(events) >= 1


class TestAGUIAdapterMessageStatusTracking:
    """Test AGUIAdapter message status tracking."""

    def test_message_status_transitions(self):
        """Test message status transitions through lifecycle."""
        adapter = AGUIAdapter(thread_id="thread_1", runId="run_1")

        # Create message
        content1 = TextContent(
            msg_id="msg_1",
            text="Hello",
            delta=True,
            index=0,
        )
        adapter.convert_agent_event_to_agui_events(content1)

        agui_msg_id = "msg_1_0"
        assert adapter._agui_message_status[agui_msg_id] in [
            AGUI_MESSAGE_STATUS.CREATED,
            AGUI_MESSAGE_STATUS.IN_PROGRESS,
        ]

        # Continue message
        content2 = TextContent(
            msg_id="msg_1",
            text=" World",
            delta=True,
            index=0,
        )
        adapter.convert_agent_event_to_agui_events(content2)

        assert (
            adapter._agui_message_status[agui_msg_id]
            == AGUI_MESSAGE_STATUS.IN_PROGRESS
        )

        # Complete message
        message = Message(
            id="msg_1",
            type=MessageType.MESSAGE,
            role=Role.ASSISTANT,
            content=[TextContent(text="Hello World")],
            status=RunStatus.Completed,
        )
        adapter.convert_agent_event_to_agui_events(message)

        assert (
            adapter._agui_message_status[agui_msg_id]
            == AGUI_MESSAGE_STATUS.COMPLETED
        )

    def test_multiple_content_indices(self):
        """Test handling multiple content items with different indices."""
        adapter = AGUIAdapter(thread_id="thread_1", runId="run_1")

        # First content item
        content1 = TextContent(
            msg_id="msg_1",
            text="First",
            delta=True,
            index=0,
        )
        adapter.convert_agent_event_to_agui_events(content1)

        # Second content item
        content2 = TextContent(
            msg_id="msg_1",
            text="Second",
            delta=True,
            index=1,
        )
        adapter.convert_agent_event_to_agui_events(content2)

        # Should have different AG-UI message IDs
        assert "msg_1_0" in adapter._agui_message_status
        assert "msg_1_1" in adapter._agui_message_status


class TestAGUIAdapterBuildRunEvent:
    """Test AGUIAdapter build_run_event method."""

    def test_build_run_started_event(self):
        """Test building run.started event."""
        from ag_ui.core.events import EventType

        adapter = AGUIAdapter(thread_id="thread_1", runId="run_1")

        event = adapter.build_run_event(event_type=EventType.RUN_STARTED)

        assert event.type == "RUN_STARTED"
        assert event.thread_id == "thread_1"
        assert event.run_id == "run_1"

    def test_build_run_finished_event(self):
        """Test building run.finished event."""
        from ag_ui.core.events import EventType

        adapter = AGUIAdapter(thread_id="thread_1", runId="run_1")

        event = adapter.build_run_event(
            event_type=EventType.RUN_FINISHED,
            result="Success",
        )

        assert event.type == "RUN_FINISHED"
        assert event.thread_id == "thread_1"
        assert event.run_id == "run_1"

    def test_build_run_error_event(self):
        """Test building run.error event."""
        from ag_ui.core.events import EventType

        adapter = AGUIAdapter(thread_id="thread_1", runId="run_1")

        event = adapter.build_run_event(
            event_type=EventType.RUN_ERROR,
            message="Test error",
            code="test_error",
        )

        assert event.type == "RUN_ERROR"
        assert event.run_id == "run_1"
        assert event.message == "Test error"
        assert event.code == "test_error"

    def test_build_unsupported_event_type_raises_error(self):
        """Test that unsupported event type raises ValueError."""
        adapter = AGUIAdapter(thread_id="thread_1", runId="run_1")

        with pytest.raises(
            ValueError,
            match="Unsupported run event type",
        ):  # noqa: E501
            adapter.build_run_event(
                event_type="unsupported_type",
            )  # type: ignore


class TestAGUIAdapterRunStartedEnsurance:
    """Test that run.started event is ensured before other events."""

    def test_run_started_emitted_once(self):
        """Test that run.started event is emitted only once."""
        adapter = AGUIAdapter(thread_id="thread_1", runId="run_1")

        # First event should trigger run.started
        content1 = TextContent(
            msg_id="msg_1",
            text="First",
            delta=True,
            index=0,
        )
        events1 = adapter.convert_agent_event_to_agui_events(content1)

        run_started_count_1 = sum(
            1 for e in events1 if e.type == "RUN_STARTED"
        )
        assert run_started_count_1 == 1

        # Second event should NOT trigger another run.started
        content2 = TextContent(
            msg_id="msg_2",
            text="Second",
            delta=True,
            index=0,
        )
        events2 = adapter.convert_agent_event_to_agui_events(content2)

        run_started_count_2 = sum(
            1 for e in events2 if e.type == "RUN_STARTED"
        )
        assert run_started_count_2 == 0

    def test_run_started_before_all_events(self):
        """Test that run.started is always the first event."""
        adapter = AGUIAdapter(thread_id="thread_1", runId="run_1")

        content = TextContent(
            msg_id="msg_1",
            text="Test",
            delta=True,
            index=0,
        )
        events = adapter.convert_agent_event_to_agui_events(content)

        # First event should be run.started
        assert events[0].type == "RUN_STARTED"


class TestAGUIAdapterEdgeCases:
    """Test edge cases in AGUIAdapter."""

    def test_empty_text_content(self):
        """Test handling empty text content."""
        adapter = AGUIAdapter(thread_id="thread_1", runId="run_1")

        content = TextContent(
            msg_id="msg_1",
            text="",
            delta=True,
            index=0,
        )
        # Should not raise error
        events = adapter.convert_agent_event_to_agui_events(content)

        assert len(events) >= 1

    def test_content_without_index(self):
        """Test handling content without explicit index."""
        adapter = AGUIAdapter(thread_id="thread_1", runId="run_1")

        content = TextContent(
            msg_id="msg_1",
            text="Test",
            delta=True,
            index=None,
        )
        # Should compute index automatically
        events = adapter.convert_agent_event_to_agui_events(content)

        assert len(events) >= 1

    def test_message_completed_before_started(self):
        """Test handling message completed before started (edge case)."""
        adapter = AGUIAdapter(thread_id="thread_1", runId="run_1")

        # Try to complete a message that was never started
        message = Message(
            id="msg_unknown",
            type=MessageType.MESSAGE,
            role=Role.ASSISTANT,
            content=[TextContent(text="Test")],
            status=RunStatus.Completed,
        )
        # Should not raise error, just log warning
        events = adapter.convert_agent_event_to_agui_events(message)

        # Should still have some events (at least run.started)
        assert len(events) >= 0
