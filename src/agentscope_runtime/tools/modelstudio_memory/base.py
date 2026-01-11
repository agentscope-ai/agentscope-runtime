# -*- coding: utf-8 -*-
"""
Base class for ModelStudio Memory components.
"""
import logging
from types import TracebackType
from typing import Any, Dict, Optional, Type

import aiohttp

from .config import (
    MemoryServiceConfig,
)
from .exceptions import (
    MemoryAPIError,
    MemoryAuthenticationError,
    MemoryNetworkError,
    MemoryNotFoundError,
    MemoryValidationError,
)

logger = logging.getLogger(__name__)


class ModelStudioMemoryBase:
    """
    Base class for ModelStudio Memory API components.

    This class provides common functionality for all memory components,
    including:
    - Configuration management
    - HTTP request handling with error handling
    - Common headers generation
    - Session management

    Attributes:
        config: Configuration for the memory service
    """

    def __init__(self, config: Optional[MemoryServiceConfig] = None):
        """
        Initialize the base memory component.

        Args:
            config: Optional configuration. If not provided, will be loaded
                   from environment variables.

        Raises:
            ValueError: If required configuration is missing
        """
        self.config = config or MemoryServiceConfig.from_env()
        self._session: Optional[aiohttp.ClientSession] = None

    def _get_headers(self) -> Dict[str, str]:
        """
        Get common HTTP headers for API requests.

        Returns:
            Dictionary of HTTP headers
        """
        return {
            "Content-Type": "application/json",
            "User-Agent": "agentscope-runtime",
            "Authorization": f"Bearer {self.config.api_key}",
        }

    async def _get_session(self) -> aiohttp.ClientSession:
        """
        Get or create an aiohttp session.

        Returns:
            An aiohttp ClientSession
        """
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def _request(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Common HTTP request handler with comprehensive error handling.

        Args:
            method: HTTP method (GET, POST, DELETE, etc.)
            url: Request URL
            **kwargs: Additional arguments for the request

        Returns:
            Response JSON as dictionary

        Raises:
            MemoryAuthenticationError: If authentication fails (401)
            MemoryNotFoundError: If resource not found (404)
            MemoryAPIError: For other API errors
            MemoryNetworkError: For network-related errors
        """
        try:
            session = await self._get_session()
            logger.debug(f"Making {method} request to {url}")

            async with session.request(
                method,
                url,
                headers=self._get_headers(),
                **kwargs,
            ) as response:
                # Handle successful response
                if response.status == 200:
                    result = await response.json()
                    logger.debug(
                        f"Request successful: {method} {url}",
                    )
                    return result

                # Handle error responses (4XX, 5XX)
                # Try to parse JSON error response first
                error_data = None
                try:
                    error_data = await response.json()
                except Exception:
                    # If JSON parsing fails, fall back to text
                    error_text = await response.text()
                    error_data = {"message": error_text}

                # Extract error information
                error_code = error_data.get("code", "Unknown")
                error_message = error_data.get("message", "Unknown error")
                request_id = error_data.get("request_id", "")

                # Format error log
                error_log = (
                    f"API Error - Status: {response.status}, "
                    f"Code: {error_code}, Message: {error_message}, "
                    f"Request ID: {request_id}"
                )
                logger.error(error_log)

                # Raise appropriate exception based on status code
                if response.status in [401, 403]:
                    raise MemoryAuthenticationError(
                        error_message,
                        status_code=response.status,
                        error_code=error_code,
                        request_id=request_id,
                    )
                if response.status == 404:
                    raise MemoryNotFoundError(
                        error_message,
                        status_code=response.status,
                        error_code=error_code,
                        request_id=request_id,
                    )
                if response.status == 400:
                    raise MemoryValidationError(
                        error_message,
                        status_code=response.status,
                        error_code=error_code,
                        request_id=request_id,
                    )
                if 400 <= response.status < 500:
                    # Other 4XX errors
                    raise MemoryValidationError(
                        error_message,
                        status_code=response.status,
                        error_code=error_code,
                        request_id=request_id,
                    )
                raise MemoryAPIError(
                    error_message,
                    status_code=response.status,
                    error_code=error_code,
                    request_id=request_id,
                )

        except aiohttp.ClientError as e:
            logger.exception(f"Network error: {str(e)}")
            raise MemoryNetworkError(
                f"Network error during {method} request to {url}: {str(e)}",
            ) from e
        except (
            MemoryAuthenticationError,
            MemoryNotFoundError,
            MemoryValidationError,
            MemoryAPIError,
        ):
            # Re-raise our custom exceptions (already have proper error info)
            raise
        except Exception as e:
            logger.exception(f"Unexpected error: {str(e)}")
            raise MemoryAPIError(
                f"Unexpected error during {method} request to {url}: {str(e)}",
            ) from e

    async def close(self) -> None:
        """
        Close the HTTP session.

        Should be called when the component is no longer needed to clean up
        resources.
        """
        if self._session and not self._session.closed:
            await self._session.close()
            logger.debug("Session closed")

    async def __aenter__(self) -> "ModelStudioMemoryBase":
        """Support async context manager."""
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        """Support async context manager."""
        await self.close()
