# -*- coding: utf-8 -*-
import asyncio
import json
import logging
import traceback
from typing import Any, AsyncGenerator, Callable, List, Optional
from uuid import uuid4

from ag_ui.core.types import Context, Message, Tool
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from agentscope_runtime.engine.schemas.agent_schemas import AgentRequest, Event

from .agui_adapter_utils import (
    AGUIAdapter,
    AGUIEvent,
    AGUIEventType,
    RunErrorEvent,
)
from ..protocol_adapter import ProtocolAdapter

logger = logging.getLogger(__name__)

SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


class FlexibleRunAgentInput(BaseModel):
    """
    Flexible input for running an agent with optional fields.

    This is a custom model that relaxes the required constraints from
    the original ag_ui.RunAgentInput, making state, tools, context,
    and forwarded_props optional for better API flexibility.

    Supports both snake_case (thread_id) and camelCase (threadId) field names.
    """

    thread_id: str = Field(..., alias="threadId")
    run_id: str = Field(..., alias="runId")
    parent_run_id: Optional[str] = Field(None, alias="parentRunId")
    state: Any = None
    messages: List[Message] = Field(default_factory=list)
    tools: List[Tool] = Field(default_factory=list)
    context: List[Context] = Field(default_factory=list)
    forwarded_props: Any = Field(None, alias="forwardedProps")

    model_config = {
        "extra": "allow",
        "populate_by_name": True,
        "json_schema_extra": {
            "example": {
                "threadId": "thread_123",
                "runId": "run_456",
                "messages": [
                    {
                        "id": "msg_1",
                        "role": "system",
                        "content": "You are a helpful assistant.",
                    },
                    {
                        "id": "msg_2",
                        "role": "user",
                        "content": "Hello",
                    },
                ],
                "tools": [],
                "context": [],
                "forwardedProps": None,
            },
        },
    }


class AGUIAdaptorConfig(BaseModel):
    """
    Configuration for AGUI adaptor.

    Attributes:
        route_path: The path of the AGUI endpoint.
    """

    route_path: str = Field(default="/ag-ui")


class AGUIDefaultAdapter(ProtocolAdapter):
    def __init__(
        self,
        config: Optional[AGUIAdaptorConfig] = None,
        **kwargs,
    ) -> None:
        self.config = config or AGUIAdaptorConfig()
        super().__init__(**kwargs)
        self._execution_func: Optional[
            Callable[[AgentRequest], AsyncGenerator[Event, None]]
        ] = None
        self._max_concurrent_requests = kwargs.get(
            "max_concurrent_requests",
            100,
        )
        self._semaphore = asyncio.Semaphore(self._max_concurrent_requests)

    async def _handle_requests(
        self,
        agent_run_input: FlexibleRunAgentInput,
    ) -> StreamingResponse:
        """
        Handle AG-UI streaming request.
        """
        await self._semaphore.acquire()
        request_id = f"agui_{uuid4()}"
        logger.info(
            "[AGUI] start request_id=%s, request=%s",
            request_id,
            agent_run_input.model_dump_json(by_alias=True, ensure_ascii=False),
        )
        try:
            return StreamingResponse(
                self._stream_with_semaphore(
                    agent_run_input,
                    request_id,
                ),
                media_type="text/event-stream",
                headers=SSE_HEADERS,
            )
        except HTTPException:
            self._semaphore.release()
            logger.info("[AGUI] end request_id=%s", request_id)
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error in _handle_requests: {e}\n"
                f"{traceback.format_exc()}",
            )
            self._semaphore.release()
            logger.info("[AGUI] end request_id=%s", request_id)
            raise HTTPException(
                status_code=500,
                detail="Internal server error",
            ) from e

    def as_sse_data(self, event: AGUIEvent) -> str:
        data = event.model_dump(
            mode="json",
            exclude_none=True,
            by_alias=True,
        )
        return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

    async def _generate_stream_response(
        self,
        request: FlexibleRunAgentInput,
    ):
        assert self._execution_func is not None
        adapter = AGUIAdapter(
            thread_id=request.thread_id,
            run_id=request.run_id,
        )
        try:
            agent_request = adapter.convert_agui_request_to_agent_request(
                request,
            )
            async for event in self._execution_func(agent_request):
                agui_events = adapter.convert_agent_event_to_agui_events(event)
                for agui_event in agui_events:
                    yield self.as_sse_data(agui_event)

            if not adapter.run_finished_emitted:
                # pylint: disable=protected-access
                adapter._run_finished_emitted = True
                yield self.as_sse_data(
                    adapter.build_run_event(
                        event_type=AGUIEventType.RUN_FINISHED,
                    ),
                )
        except Exception as e:
            logger.error(
                f"AG-UI stream failed: {e}\n{traceback.format_exc()}",
            )

            error_event = RunErrorEvent(
                message=f"Unexpected stream error: {e}",
                code="unexpected_stream_error",
            ).model_dump(
                mode="json",
                exclude_none=True,
            )
            yield f"data: {json.dumps(error_event, ensure_ascii=False)}\n\n"
            return

    async def _stream_with_semaphore(
        self,
        request: FlexibleRunAgentInput,
        request_id: str,
    ):
        try:
            async for chunk in self._generate_stream_response(request):
                yield chunk
        finally:
            self._semaphore.release()
            logger.info("[AGUI] end request_id=%s", request_id)

    def add_endpoint(self, app: FastAPI, func, **kwargs) -> Any:
        """
        Add AG-UI endpoint to FastAPI app.
        """
        self._execution_func = func
        app.add_api_route(
            self.config.route_path,
            self._handle_requests,
            methods=["POST"],
            tags=[
                "ag-ui",
            ],
        )
        return app
