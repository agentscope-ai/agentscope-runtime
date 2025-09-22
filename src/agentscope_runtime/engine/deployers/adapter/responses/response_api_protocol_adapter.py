# -*- coding: utf-8 -*-
import asyncio
import json
import logging
import traceback
from typing import Callable, Dict, Any, Optional, AsyncGenerator
from uuid import uuid4

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse

# OpenAI Response API official type definition
from openai.types.responses import ResponseCreateParams

from .response_api_adapter_utils import ResponsesAdapter
from .response_api_agent_adapter import ResponseAPIExecutor
from ..protocol_adapter import ProtocolAdapter
from ....schemas.agent_schemas import AgentRequest, BaseResponse

logger = logging.getLogger(__name__)

RESPONSES_ENDPOINT_PATH = "/compatible-mode/v1/responses"
SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",  # disable Nginx buffering
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization",
}


class ResponseAPIDefaultAdapter(ProtocolAdapter):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._executor: Optional[ResponseAPIExecutor] = None
        self._timeout = kwargs.get("timeout", 300)  # seconds
        self._max_concurrent_requests = kwargs.get(
            "max_concurrent_requests",
            100,
        )
        self._semaphore = asyncio.Semaphore(self._max_concurrent_requests)

    async def _handle_requests(self, request: Request) -> StreamingResponse:
        """
        Handle OpenAI Response API request.

        Args:
            request: FastAPI Request object

        Returns:
            StreamingResponse: SSE streaming response
        """
        # Concurrency guard per request
        await self._semaphore.acquire()
        request_id = f"resp_{uuid4()}"
        logger.info("[ResponseAPI] start request_id=%s", request_id)
        try:
            # Parse request body
            request_data = await request.json()

            stream = request_data.get("stream", False)

            # Stream or non-stream
            if stream:
                # Return SSE streaming response with timeout control
                return StreamingResponse(
                    self._generate_stream_response_with_timeout(
                        request=request_data,
                        request_id=request_id,
                    ),
                    media_type="text/event-stream",
                    headers=SSE_HEADERS,
                )

            # Non-stream JSON response
            response_obj = await self._collect_non_stream_response(
                request=request_data,
                request_id=request_id,
            )
            return JSONResponse(content=response_obj)

        except HTTPException:
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error in _handle_requests: {e}\n"
                f"{traceback.format_exc()}",
            )
            raise HTTPException(
                status_code=500,
                detail="Internal server error",
            ) from e
        finally:
            self._semaphore.release()
            logger.info("[ResponseAPI] end request_id=%s", request_id)

    def _convert_response_request_to_agent_request(
        self,
        response_request: ResponseCreateParams,
    ) -> AgentRequest:
        """
        Convert an OpenAI Response API request to Agent API request.

        Args:
            response_request: OpenAI Response API request

        Returns:
            AgentRequest: Agent API request
        """
        # Convert with ResponsesAdapter
        adapter = ResponsesAdapter()
        agent_request = adapter.convert_responses_request_to_agent_request(
            response_request.model_dump(),
        )

        return agent_request

    async def _collect_non_stream_response(
        self,
        request: Dict,
        request_id: str,
    ) -> Dict[str, Any]:
        """
        Run the agent and build a non-streaming OpenAI Responses API object.

        This collects events until completion and returns a single JSON object
        representing the final response.
        """
        last_agent_response: Optional[BaseResponse] = None
        try:
            async for event in self._executor.execute(request):
                last_agent_response = event
        except Exception:
            # Map to Responses error shape
            return {
                "id": request_id,
                "object": "response",
                "status": "failed",
                "error": {
                    "code": "non_stream_error",
                    "message": "Failed to build non-stream response",
                },
            }

        if not last_agent_response:
            # No response produced
            return {
                "id": request_id,
                "object": "response",
                "status": "failed",
                "error": {
                    "code": "empty_response",
                    "message": "No response produced by agent",
                },
            }

        # Convert to dict for JSONResponse
        return last_agent_response.model_dump(exclude_none=True)

    async def _generate_stream_response_with_timeout(
        self,
        request: Dict,
        request_id: str,
    ) -> AsyncGenerator[str, None]:
        """
        Generate SSE streaming response with timeout.

        Args:
            agent_request: Agent API request

        Yields:
            str: SSE data chunks
        """
        try:
            # Add timeout with asyncio.wait_for
            async for chunk in self._generate_stream_response(
                request=request,
                request_id=request_id,
            ):
                yield chunk
        except asyncio.TimeoutError:
            logger.error(f"Request timeout after {self._timeout} seconds")
            # Send timeout error event
            timeout_event = {
                "id": request_id,
                "object": "response",
                "status": "failed",
                "error": {
                    "code": "timeout",
                    "message": f"Request timed out after "
                    f"{self._timeout} seconds",
                },
            }
            yield (
                f"event: response.failed\n"
                f"data: {json.dumps(timeout_event)}\n\n"
            )
        except Exception as e:
            logger.error(
                f"Error in timeout-controlled stream: {e}\n"
                f"{traceback.format_exc()}",
            )
            # Send error event
            error_event = {
                "id": request_id,
                "object": "response",
                "status": "failed",
                "error": {
                    "code": "stream_error",
                    "message": str(e),
                },
            }
            yield (
                f"event: response.failed\n"
                f"data: {json.dumps(error_event)}\n\n"
            )

    async def _generate_stream_response(
        self,
        request: Dict,
        request_id: str,
    ) -> AsyncGenerator[str, None]:
        """
        Generate SSE streaming response.

        Args:
            request: Responses API request

        Yields:
            str: SSE data chunks
        """
        try:
            # Handle streaming events
            async for event in self._executor.execute(request):
                try:
                    if event:
                        # Serialize event
                        event_data = event.model_dump(exclude_none=True)
                        data = json.dumps(event_data, ensure_ascii=False)

                        # Set SSE event type based on event type
                        event_type = event_data.get("type", "message")
                        yield f"event: {event_type}\ndata: {data}\n\n"

                except Exception as e:
                    logger.error(
                        f"Error processing event: {e}\n"
                        f"{traceback.format_exc()}",
                    )
                    # Send error event
                    error_event = {
                        "id": request_id,
                        "object": "response",
                        "status": "failed",
                        "error": {
                            "code": "processing_error",
                            "message": str(e),
                        },
                    }
                    yield (
                        f"event: response.failed\n"
                        f"data: {json.dumps(error_event)}\n\n"
                    )
                    break
        except Exception as e:
            logger.error(
                f"Error in stream generation: {e}\n{traceback.format_exc()}",
            )
            # Send error event
            error_event = {
                "id": request_id,
                "object": "response",
                "status": "failed",
                "error": {
                    "code": "stream_error",
                    "message": str(e),
                },
            }
            yield (
                f"event: response.failed\n"
                f"data: {json.dumps(error_event)}\n\n"
            )

    def add_endpoint(self, app: FastAPI, func: Callable, **kwargs) -> None:
        """
        Add endpoint to FastAPI app.

        Args:
            app: FastAPI application instance
            func: handler function
            **kwargs: extra options
        """
        # Create executor
        self._executor = ResponseAPIExecutor(func=func)

        # Register route
        app.post(
            RESPONSES_ENDPOINT_PATH,
            openapi_extra={
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {
                                "$ref": "#/components/schemas/ResponseAPI",
                            },
                        },
                    },
                    "required": True,
                    "description": "OpenAI Response API compatible "
                    "request format",
                },
            },
        )(self._handle_requests)
