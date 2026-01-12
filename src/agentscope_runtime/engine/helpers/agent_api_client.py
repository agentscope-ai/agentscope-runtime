# -*- coding: utf-8 -*-
"""
Agent API Protocol Client Library.
"""

import json
import logging
from abc import ABC, abstractmethod
from typing import AsyncIterator, Dict, Iterator, Optional

import httpx

from agentscope_runtime.engine.schemas.agent_schemas import (
    AgentRequest,
    AgentResponse,
    Content,
    DataContent,
    Event,
    ImageContent,
    Message,
    TextContent,
)

logger = logging.getLogger(__name__)


class AgentAPIClientBase(ABC):
    """
    Abstract base class for Agent API Protocol clients.

    All Agent API clients must implement this interface, which defines
    the core method for streaming requests and responses according to
    the Agent API Protocol.
    """

    @abstractmethod
    def stream(self, request: AgentRequest) -> Iterator[Event]:
        """
        Send a request and stream the response events (synchronous).

        Args:
            request: AgentRequest object

        Yields:
            Event objects (Message, Content, AgentResponse, etc.)

        Raises:
            Exception: If the request fails
        """
        raise NotImplementedError

    @abstractmethod
    async def astream(self, request: AgentRequest) -> AsyncIterator[Event]:
        """
        Send a request and stream the response events (asynchronous).

        Args:
            request: AgentRequest object

        Yields:
            Event objects (Message, Content, AgentResponse, etc.)

        Raises:
            Exception: If the request fails
        """
        raise NotImplementedError
        # Make this an async generator for proper type checking
        yield  # pylint: disable=unreachable


# ============================================================================
# HTTP Implementation
# ============================================================================


def parse_sse_line_bytes(line: bytes) -> tuple[Optional[str], Optional[str]]:
    """
    Parse a single SSE (Server-Sent Events) line from bytes.

    Args:
        line: SSE line as bytes

    Returns:
        Tuple of (field, value) where field can be 'data', 'event',
        'id', or 'retry'
    """
    line_str = line.decode("utf-8").strip()
    return parse_sse_line(line_str)


def parse_sse_line(line: str) -> tuple[Optional[str], Optional[str]]:
    """
    Parse a single SSE (Server-Sent Events) line.

    Args:
        line: SSE line string (already decoded from bytes)

    Returns:
        Tuple of (field, value) where field can be 'data', 'event',
        'id', or 'retry'
    """
    line_str = line.strip()
    if line_str.startswith("data: "):
        return "data", line_str[6:]
    elif line_str.startswith("event:"):
        return "event", line_str[7:].strip()
    elif line_str.startswith("id: "):
        return "id", line_str[4:].strip()
    elif line_str.startswith("retry:"):
        return "retry", line_str[7:].strip()
    return None, None


def parse_event_from_json(data: Dict) -> Optional[Event]:
    """
    Parse an Event object from JSON data according to Agent API Protocol.

    Args:
        data: Parsed JSON response data

    Returns:
        Event object (Message, Content, or AgentResponse) if valid,
        None otherwise
    """
    try:
        obj_type = data.get("object")

        if obj_type == "response":
            return AgentResponse(**data)
        if obj_type == "message":
            return Message(**data)
        if obj_type == "content":
            content_type = data.get("type", "")
            content_class_map = {
                "text": TextContent,
                "image": ImageContent,
                "data": DataContent,
            }
            content_class = content_class_map.get(content_type, Content)
            return content_class(**data)
        # Unknown object type, return as generic event if it has
        # required fields
        if "object" in data:
            return Event(**data)
        return None
    except Exception as e:
        logger.warning(
            "Failed to parse event from JSON: %s, error: %s",
            data,
            e,
        )
        return None


class HTTPAgentAPIClient(AgentAPIClientBase):
    """
    HTTP/SSE implementation of Agent API Protocol client.

    This client uses HTTP POST with Server-Sent Events (SSE) for streaming
    responses from Agent API Protocol endpoints.

    Attributes:
        endpoint: API endpoint URL
        token: Optional authorization token
        timeout: Request timeout in seconds
        headers: Additional custom headers
    """

    def __init__(
        self,
        endpoint: str,
        token: Optional[str] = None,
        timeout: float = 300.0,
        headers: Optional[Dict[str, str]] = None,
    ):
        """
        Initialize HTTP Agent API client.

        Args:
            endpoint: API endpoint URL
                (e.g., "https://api.example.com/process")
            token: Optional authorization token (Bearer token)
            timeout: Request timeout in seconds (default: 300)
            headers: Optional additional custom headers
        """
        self.endpoint = endpoint
        self.token = token
        self.timeout = timeout
        self.headers = headers or {}

    def _prepare_headers(self) -> Dict[str, str]:
        """Prepare HTTP headers for the request."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
            "Cache-Control": "no-cache",
        }

        # Add custom headers
        headers.update(self.headers)

        # Add authorization if token is provided
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        return headers

    def stream(self, request: AgentRequest) -> Iterator[Event]:
        """
        Send a request and stream the response events (synchronous).

        Args:
            request: AgentRequest object

        Yields:
            Event objects (Message, Content, AgentResponse, etc.)

        Raises:
            requests.exceptions.RequestException: If the HTTP request fails
        """
        import requests

        headers = self._prepare_headers()
        payload = request.model_dump(exclude_none=True)

        try:
            response = requests.post(
                self.endpoint,
                json=payload,
                headers=headers,
                stream=True,
                timeout=self.timeout,
            )
            response.raise_for_status()

            # Parse SSE stream
            for line in response.iter_lines():
                if not line:
                    continue
                field, value = parse_sse_line_bytes(line)
                if field != "data" or not value:
                    continue
                try:
                    data = json.loads(value)
                    event = parse_event_from_json(data)
                    if event:
                        yield event
                except json.JSONDecodeError:
                    logger.debug("Failed to parse JSON: %s", value)

        except requests.exceptions.RequestException as e:
            logger.error("HTTP request failed: %s", e)
            raise

    async def astream(self, request: AgentRequest) -> AsyncIterator[Event]:
        """
        Send a request and stream the response events (asynchronous).

        Args:
            request: AgentRequest object

        Yields:
            Event objects (Message, Content, AgentResponse, etc.)

        Raises:
            httpx.HTTPError: If the HTTP request fails
        """
        headers = self._prepare_headers()
        payload = request.model_dump(exclude_none=True)

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream(
                    "POST",
                    self.endpoint,
                    json=payload,
                    headers=headers,
                ) as response:
                    # chunks = ""

                    # async for c in response.aiter_bytes():
                    #     if c:
                    #         chunks += c.decode("utf-8")
                    # print(chunks)

                    response.raise_for_status()

                    # Parse SSE stream
                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        field, value = parse_sse_line(line)
                        if field != "data" or not value:
                            continue
                        try:
                            data = json.loads(value)
                            event = parse_event_from_json(data)
                            if event:
                                yield event
                        except json.JSONDecodeError:
                            logger.debug(
                                "Failed to parse JSON: %s",
                                value,
                            )

        except httpx.HTTPError as e:
            logger.error("HTTP request failed: %s", e)
            raise


# ============================================================================
# Convenience Utilities
# ============================================================================


def extract_text_from_event(event: Event) -> Optional[str]:
    """
    Extract text content from an Event.

    Args:
        event: Event object

    Returns:
        Text string if the event contains text content, None otherwise
    """
    if isinstance(event, TextContent):
        return event.text
    elif isinstance(event, Message):
        # Extract text from completed messages
        if event.status == "completed" and event.content:
            texts = []
            for content_item in event.content:
                if isinstance(content_item, TextContent) and content_item.text:
                    texts.append(content_item.text)
            return "".join(texts) if texts else None
    return None


def create_simple_text_request(
    query: str,
    session_id: Optional[str] = None,
    **kwargs,
) -> AgentRequest:
    """
    Create a simple AgentRequest with a text query.

    Args:
        query: User query text
        session_id: Optional session ID for conversation continuity
        **kwargs: Additional parameters for AgentRequest

    Returns:
        AgentRequest object
    """
    message = Message(
        role="user",
        type="message",
        content=[TextContent(type="text", text=query)],
    )

    request_params = {
        "input": [message],
        "stream": True,
    }

    if session_id:
        request_params["session_id"] = session_id

    # Merge with any additional parameters
    request_params.update(kwargs)

    return AgentRequest(**request_params)
