# -*- coding: utf-8 -*-
# pylint: disable=redefined-outer-name, protected-access
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
from agentscope_runtime.engine.helpers.agent_api_builder import ResponseBuilder
from agentscope_runtime.engine.schemas.agent_schemas import (
    AgentRequest,
    AgentResponse,
    RunStatus,
)


class TestAGUIEventStreaming:
    """Test end-to-end AG-UI request and response flow."""

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

    @pytest.mark.asyncio
    async def test_agui_events(self):
        """Test streaming text with multiple deltas."""
        adapter = AGUIDefaultAdapter()
        app = FastAPI()

        async def mock_agent_execution(
            request: AgentRequest,
        ):  # pylint: disable=unused-argument
            response_builder = ResponseBuilder(
                session_id=request.session_id,
            )

            for event in response_builder.generate_streaming_response(
                text_tokens=[
                    "Hello",
                    " there",
                    "!",
                    " How",
                    " are",
                    " you",
                    "?",
                ],
                role="assistant",
            ):
                yield event

        adapter.add_endpoint(app, mock_agent_execution)
        client = TestClient(app)

        request_data = {
            "threadId": "test_thread",
            "runId": "test_run",
            "messages": [{"id": "msg_1", "role": "user", "content": "Hi"}],
        }

        response = client.post("/ag-ui", json=request_data)
        assert response.status_code == 200

        # Parse events
        events = []
        for line in response.text.strip().split("\n\n"):
            if line.startswith("data: "):
                event_data = json.loads(line[6:])
                events.append(event_data)

        # Verify we received events
        assert len(events) > 0, "Should receive at least one event"

        # Extract event types
        event_types = [event["type"] for event in events]

        # Verify expected event types in sequence
        assert (
            "TEXT_MESSAGE_START" in event_types
            or "TEXT_MESSAGE_CONTENT" in event_types
        ), "Should have text message events"

        run_started_count = sum(
            1 for e in events if e["type"] == "RUN_STARTED"
        )
        assert (
            run_started_count == 1
        ), "Should have exactly one RUN_STARTED event"

        run_finished_count = sum(
            1 for e in events if e["type"] == "RUN_FINISHED"
        )
        assert (
            run_finished_count == 1
        ), "Should have exactly one RUN_FINISHED event"

        # Verify event sequence order
        run_started_idx = event_types.index("RUN_STARTED")
        run_finished_idx = event_types.index("RUN_FINISHED")
        assert (
            run_started_idx < run_finished_idx
        ), "RUN_STARTED should come before RUN_FINISHED"

        # Verify thread_id and run_id are present in RUN_STARTED event
        run_started_event = events[run_started_idx]
        assert (
            run_started_event["threadId"] == "test_thread"
        ), "RUN_STARTED should have correct threadId"
        assert (
            run_started_event["runId"] == "test_run"
        ), "RUN_STARTED should have correct runId"

        # Verify RUN_FINISHED event
        run_finished_event = events[run_finished_idx]
        assert (
            run_finished_event["threadId"] == "test_thread"
        ), "RUN_FINISHED should have correct threadId"
        assert (
            run_finished_event["runId"] == "test_run"
        ), "RUN_FINISHED should have correct runId"

        # Collect text deltas from TEXT_MESSAGE_CONTENT events
        text_deltas = []
        for event in events:
            if event["type"] == "TEXT_MESSAGE_CONTENT" and "delta" in event:
                text_deltas.append(event["delta"])

        # Verify we got text deltas
        assert len(text_deltas) > 0, "Should receive text content deltas"

        # Verify the complete text matches our input tokens
        complete_text = "".join(text_deltas)
        expected_text = "Hello there! How are you?"
        assert (
            complete_text == expected_text
        ), f"Complete text should be '{expected_text}', got '{complete_text}'"

        # Verify message_id consistency in text events
        message_ids = set()
        for event in events:
            if event["type"] in ["TEXT_MESSAGE_START", "TEXT_MESSAGE_CONTENT"]:
                if "messageId" in event:
                    message_ids.add(event["messageId"])

        assert (
            len(message_ids) == 1
        ), "All text message events should have the same messageId"
