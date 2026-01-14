# -*- coding: utf-8 -*-
"""
Custom exceptions for ModelStudio Memory components.
"""
from typing import Optional


class MemoryAPIError(Exception):
    """
    Base exception for Memory API errors.

    Attributes:
        message: Error message
        status_code: HTTP status code
        error_code: API error code (e.g., 'InvalidApiKey', 'InvalidParameter')
        request_id: Request ID for tracking
    """

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        error_code: Optional[str] = None,
        request_id: Optional[str] = None,
    ):
        self.status_code = status_code
        self.error_code = error_code
        self.request_id = request_id
        super().__init__(message)

    def __str__(self) -> str:
        """Format error message with all available information."""
        parts = [super().__str__()]

        if self.error_code:
            parts.append(f"Error Code: {self.error_code}")

        if self.status_code:
            parts.append(f"Status Code: {self.status_code}")

        if self.request_id:
            parts.append(f"Request ID: {self.request_id}")

        return " | ".join(parts)


class MemoryAuthenticationError(MemoryAPIError):
    """Raised when authentication fails (401, 403)."""


class MemoryNotFoundError(MemoryAPIError):
    """Raised when a memory node is not found (404)."""


class MemoryValidationError(MemoryAPIError):
    """Raised when input validation fails (400)."""


class MemoryNetworkError(MemoryAPIError):
    """Raised when network communication fails."""
