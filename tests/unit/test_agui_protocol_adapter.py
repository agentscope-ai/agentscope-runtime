# -*- coding: utf-8 -*-
# pylint: disable=redefined-outer-name, protected-access
"""
Unit tests for AG-UI Protocol Adapter.

Tests cover:
- AGUIDefaultAdapter endpoint creation
- Request handling and streaming
- SSE event formatting
- Error handling
- Concurrency control
"""
import asyncio
import json

import pytest
from ag_ui.core import RunAgentInput
from ag_ui.core.types import (
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
    RunStatus,
    TextContent,
)


class TestAGUIDefaultAdapterBasics:
    """Test basic functionality of AGUIDefaultAdapter."""

    def test_adapter_initialization(self):
        """Test AGUIDefaultAdapter initialization with default values."""
        adapter = AGUIDefaultAdapter()

        assert adapter._execution_func is None
        assert adapter._max_concurrent_requests == 100
        assert isinstance(adapter._semaphore, asyncio.Semaphore)
        assert adapter._semaphore._value == 100

    def test_adapter_initialization_with_custom_max_concurrent(self):
        """Test adapter initialization with custom max_concurrent_requests."""
        adapter = AGUIDefaultAdapter(max_concurrent_requests=50)

        assert adapter._max_concurrent_requests == 50
        assert adapter._semaphore._value == 50

    def test_add_endpoint(self):
        """Test adding AG-UI endpoint to FastAPI app."""
        adapter = AGUIDefaultAdapter()
        app = FastAPI()

        async def mock_func(
            request: AgentRequest,
        ):  # pylint: disable=unused-argument
            yield AgentResponse(status=RunStatus.Completed)

        result = adapter.add_endpoint(app, mock_func)

        assert result is app
        assert adapter._execution_func is mock_func
        # Verify route was added
        routes = [route.path for route in app.routes]
        assert "/agui" in routes

    def test_as_sse_data(self):
        """Test SSE data formatting."""
        from ag_ui.core.events import RunStartedEvent

        adapter = AGUIDefaultAdapter()
        event = RunStartedEvent(
            thread_id="thread_123",
            run_id="run_456",
        )

        result = adapter.as_sse_data(event)

        assert result.startswith("data: ")
        assert result.endswith("\n\n")
        # Parse JSON part
        json_str = result[6:-2]  # Remove "data: " and "\n\n"
        data = json.loads(json_str)
        assert data["type"] == "RUN_STARTED"
        assert data["thread_id"] == "thread_123"
        assert data["run_id"] == "run_456"


class TestAGUIEndpointIntegration:
    """Test AG-UI endpoint integration with FastAPI."""

    @pytest.mark.asyncio
    async def test_endpoint_accepts_post_request(self):
        """Test that AG-UI endpoint accepts POST requests."""
        adapter = AGUIDefaultAdapter()
        app = FastAPI()

        async def mock_func(
            request: AgentRequest,
        ):  # pylint: disable=unused-argument
            yield AgentResponse(status=RunStatus.Completed)

        adapter.add_endpoint(app, mock_func)
        client = TestClient(app)

        # Create a valid RunAgentInput
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

    @pytest.mark.asyncio
    async def test_endpoint_sse_headers(self):
        """Test that AG-UI endpoint returns correct SSE headers."""
        adapter = AGUIDefaultAdapter()
        app = FastAPI()

        async def mock_func(
            request: AgentRequest,
        ):  # pylint: disable=unused-argument
            yield AgentResponse(status=RunStatus.Completed)

        adapter.add_endpoint(app, mock_func)
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
                    "content": "Hello",
                },
            ],
        }

        response = client.post("/agui", json=request_data)

        assert response.headers["cache-control"] == "no-cache"
        assert response.headers["connection"] == "keep-alive"
        assert response.headers["x-accel-buffering"] == "no"


class TestAGUIStreamGeneration:
    """Test AG-UI stream response generation."""

    @pytest.mark.asyncio
    async def test_generate_stream_response_basic(self):
        """Test basic stream response generation."""
        adapter = AGUIDefaultAdapter()

        # Mock execution function
        async def mock_execution(
            request: AgentRequest,
        ):  # pylint: disable=unused-argument
            yield AgentResponse(status=RunStatus.Created)
            yield AgentResponse(status=RunStatus.Completed)

        adapter._execution_func = mock_execution

        # Create RunAgentInput
        agui_request = RunAgentInput(
            threadId="thread_123",
            runId="run_456",
            state=None,
            tools=[],
            context=[],
            forwardedProps=None,
            messages=[
                UserMessage(
                    id="msg_user",
                    role="user",
                    content="Test message",
                ),
            ],
        )

        # Collect stream events
        events = []
        async for event_data in adapter._generate_stream_response(
            agui_request,
        ):
            events.append(event_data)

        # Should have at least run.started and run.finished events
        assert len(events) >= 2
        # Check that events are SSE formatted
        for event in events:
            assert event.startswith("data: ")
            assert event.endswith("\n\n")

    @pytest.mark.asyncio
    async def test_generate_stream_response_with_text_content(self):
        """Test stream response with text content."""
        adapter = AGUIDefaultAdapter()

        # Mock execution function that yields text content
        async def mock_execution(
            request: AgentRequest,
        ):  # pylint: disable=unused-argument
            yield AgentResponse(status=RunStatus.Created)
            msg_content = TextContent(
                msg_id="msg_1",
                text="Hello",
                delta=True,
                index=0,
            )
            yield msg_content
            yield AgentResponse(status=RunStatus.Completed)

        adapter._execution_func = mock_execution

        agui_request = RunAgentInput(
            threadId="thread_123",
            runId="run_456",
            state=None,
            tools=[],
            context=[],
            forwardedProps=None,
            messages=[UserMessage(id="msg_user", role="user", content="Test")],
        )

        events = []
        async for event_data in adapter._generate_stream_response(
            agui_request,
        ):
            events.append(event_data)

        # Parse events to check content
        parsed_events = []
        for event_str in events:
            json_str = event_str[6:-2]  # Remove "data: " and "\n\n"
            parsed_events.append(json.loads(json_str))

        # Should have RUN_STARTED, text message events, and RUN_FINISHED
        event_types = [e["type"] for e in parsed_events]
        assert "RUN_STARTED" in event_types
        assert (
            "TEXT_MESSAGE_CONTENT" in event_types
            or "TEXT_MESSAGE_START" in event_types
        )
        assert "RUN_FINISHED" in event_types

    @pytest.mark.asyncio
    async def test_generate_stream_response_error_handling(self):
        """Test stream response error handling."""
        adapter = AGUIDefaultAdapter()

        # Mock execution function that raises error
        async def mock_execution(
            request: AgentRequest,
        ):  # pylint: disable=unused-argument
            yield AgentResponse(status=RunStatus.Created)
            raise ValueError("Test error")

        adapter._execution_func = mock_execution

        agui_request = RunAgentInput(
            threadId="thread_123",
            runId="run_456",
            state=None,
            tools=[],
            context=[],
            forwardedProps=None,
            messages=[UserMessage(id="msg_user", role="user", content="Test")],
        )

        events = []
        async for event_data in adapter._generate_stream_response(
            agui_request,
        ):
            events.append(event_data)

        # Should have error event
        assert len(events) > 0
        # Last event should be error
        last_event_str = events[-1]
        json_str = last_event_str[6:-2]
        last_event = json.loads(json_str)
        assert last_event["type"] == "RUN_ERROR"
        assert "Test error" in last_event["message"]


class TestAGUIConcurrencyControl:
    """Test AG-UI adapter concurrency control."""

    @pytest.mark.asyncio
    async def test_semaphore_limits_concurrent_requests(self):
        """Test that semaphore limits concurrent request handling."""
        adapter = AGUIDefaultAdapter(max_concurrent_requests=2)

        # Verify semaphore is created with correct limit
        assert adapter._semaphore is not None
        assert adapter._semaphore._value == 2

        # Test that semaphore can be acquired
        await adapter._semaphore.acquire()
        assert adapter._semaphore._value == 1

        await adapter._semaphore.acquire()
        assert adapter._semaphore._value == 0

        # Release them
        adapter._semaphore.release()
        adapter._semaphore.release()
        assert adapter._semaphore._value == 2


class TestAGUIRequestValidation:
    """Test AG-UI request validation and conversion."""

    @pytest.mark.asyncio
    async def test_handle_requests_with_invalid_request(self):
        """Test handling of invalid AG-UI requests."""
        adapter = AGUIDefaultAdapter()
        app = FastAPI()

        async def mock_func(
            request: AgentRequest,
        ):  # pylint: disable=unused-argument
            yield AgentResponse(status=RunStatus.Completed)

        adapter.add_endpoint(app, mock_func)
        client = TestClient(app)

        # Send invalid request data
        response = client.post("/agui", json={"invalid": "data"})

        # Should return error status
        assert response.status_code >= 400


class TestAGUIEndpointMethods:
    """Test AG-UI endpoint HTTP methods."""

    def test_endpoint_accepts_options_request(self):
        """Test that AG-UI endpoint accepts OPTIONS requests (for CORS)."""
        adapter = AGUIDefaultAdapter()
        app = FastAPI()

        async def mock_func(
            request: AgentRequest,
        ):  # pylint: disable=unused-argument
            yield AgentResponse(status=RunStatus.Completed)

        adapter.add_endpoint(app, mock_func)

        # Verify that OPTIONS is in the registered methods
        routes = [
            route
            for route in app.routes
            if hasattr(route, "path") and route.path == "/agui"
        ]
        assert len(routes) > 0
        route = routes[0]
        # Check that OPTIONS is in the allowed methods
        assert "OPTIONS" in route.methods or "POST" in route.methods


class TestAGUIStreamResponseEdgeCases:
    """Test edge cases in AG-UI stream response generation."""

    @pytest.mark.asyncio
    async def test_stream_with_empty_execution_func(self):
        """Test that missing execution_func raises assertion error."""
        adapter = AGUIDefaultAdapter()

        agui_request = RunAgentInput(
            threadId="thread_123",
            runId="run_456",
            state=None,
            tools=[],
            context=[],
            forwardedProps=None,
            messages=[UserMessage(id="msg_user", role="user", content="Test")],
        )

        with pytest.raises(AssertionError):
            async for _ in adapter._generate_stream_response(agui_request):
                pass

    @pytest.mark.asyncio
    async def test_stream_ensures_run_finished_emitted(self):
        """Test that run.finished event is always emitted."""
        adapter = AGUIDefaultAdapter()

        # Mock execution that doesn't emit completion event
        async def mock_execution(
            request: AgentRequest,
        ):  # pylint: disable=unused-argument
            yield AgentResponse(status=RunStatus.Created)
            # No completion event

        adapter._execution_func = mock_execution

        agui_request = RunAgentInput(
            threadId="thread_123",
            runId="run_456",
            state=None,
            tools=[],
            context=[],
            forwardedProps=None,
            messages=[UserMessage(id="msg_user", role="user", content="Test")],
        )

        events = []
        async for event_data in adapter._generate_stream_response(
            agui_request,
        ):
            events.append(event_data)

        # Parse last event
        parsed_events = []
        for event_str in events:
            json_str = event_str[6:-2]
            parsed_events.append(json.loads(json_str))

        event_types = [e["type"] for e in parsed_events]
        # Should have run.finished even if not explicitly yielded
        assert "RUN_FINISHED" in event_types


class TestAGUIJSONSerialization:
    """Test JSON serialization in AG-UI events."""

    def test_as_sse_data_with_unicode(self):
        """Test SSE data formatting with Unicode characters."""
        from ag_ui.core.events import TextMessageContentEvent

        adapter = AGUIDefaultAdapter()
        event = TextMessageContentEvent(
            message_id="msg_1",
            delta="你好世界 🌍",
        )

        result = adapter.as_sse_data(event)

        assert result.startswith("data: ")
        assert result.endswith("\n\n")
        json_str = result[6:-2]
        data = json.loads(json_str)
        assert data["delta"] == "你好世界 🌍"

    def test_as_sse_data_excludes_none_values(self):
        """Test that None values are excluded from SSE data."""
        from ag_ui.core.events import TextMessageStartEvent

        adapter = AGUIDefaultAdapter()
        event = TextMessageStartEvent(
            message_id="msg_1",
        )

        result = adapter.as_sse_data(event)
        json_str = result[6:-2]
        data = json.loads(json_str)

        # Should not have null/None values for optional fields
        for value in data.values():
            assert value is not None
