# -*- coding: utf-8 -*-
"""
Business System Exception Definitions
Provides a three-level exception structure:
Base Class -> HTTP Status Exceptions -> Business Exceptions
"""

from typing import Any, Dict, Optional


class AppBaseException(Exception):
    """
    Business exception base class

    Attributes:
        status: HTTP status code, aligned with standard HTTP status codes
        code: Business error code, used for business logic distinction
        message: Error message
        details: Additional error details
    """

    def __init__(
        self,
        status: int,
        code: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize the exception

        Args:
            status: HTTP status code
            code: Business error code
            message: Error message
            details: Additional details
        """
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.details = details or {}

    def __str__(self) -> str:
        """String representation"""
        return f"[{self.status}] {self.code}: {self.message}"

    def __repr__(self) -> str:
        """Detailed representation"""
        return (
            f"{self.__class__.__name__}(status={self.status}, code="
            f"'{self.code}', message='{self.message}')"
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to a dictionary"""
        return {
            "status": self.status,
            "code": self.code,
            "message": self.message,
            "details": self.details,
        }


# ==================== HTTP Status Exceptions ====================


class BadRequestException(AppBaseException):
    """400 Bad Request - Client request error"""

    def __init__(
        self,
        code: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(400, code, message, details)


class UnauthorizedException(AppBaseException):
    """401 Unauthorized"""

    def __init__(
        self,
        code: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(401, code, message, details)


class ForbiddenException(AppBaseException):
    """403 Forbidden - Access denied"""

    def __init__(
        self,
        code: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(403, code, message, details)


class NotFoundException(AppBaseException):
    """404 Not Found - Resource does not exist"""

    def __init__(
        self,
        code: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(404, code, message, details)


class MethodNotAllowedException(AppBaseException):
    """405 Method Not Allowed"""

    def __init__(
        self,
        code: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(405, code, message, details)


class ConflictException(AppBaseException):
    """409 Conflict"""

    def __init__(
        self,
        code: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(409, code, message, details)


class UnprocessableEntityException(AppBaseException):
    """422 Unprocessable Entity"""

    def __init__(
        self,
        code: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(422, code, message, details)


class TooManyRequestsException(AppBaseException):
    """429 Too Many Requests"""

    def __init__(
        self,
        code: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(429, code, message, details)


class InternalServerErrorException(AppBaseException):
    """500 Internal Server Error"""

    def __init__(
        self,
        code: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(500, code, message, details)


class BadGatewayException(AppBaseException):
    """502 Bad Gateway"""

    def __init__(
        self,
        code: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(502, code, message, details)


class ServiceUnavailableException(AppBaseException):
    """503 Service Unavailable"""

    def __init__(
        self,
        code: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(503, code, message, details)


class GatewayTimeoutException(AppBaseException):
    """504 Gateway Timeout"""

    def __init__(
        self,
        code: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(504, code, message, details)


# ==================== Business Exceptions ====================


# Authentication-related exceptions
class AuthenticationException(UnauthorizedException):
    """Authentication failed"""

    def __init__(
        self,
        message: str = "Authentication failed",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__("AUTH_FAILED", message, details)


class TokenExpiredException(UnauthorizedException):
    """Token expired"""

    def __init__(
        self,
        message: str = "Token has expired",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__("TOKEN_EXPIRED", message, details)


class InvalidTokenException(UnauthorizedException):
    """Invalid token"""

    def __init__(
        self,
        message: str = "Invalid token",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__("INVALID_TOKEN", message, details)


# Permission-related exceptions
class PermissionDeniedException(ForbiddenException):
    """Permission denied"""

    def __init__(
        self,
        message: str = "Permission denied",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__("PERMISSION_DENIED", message, details)


class AccessDeniedException(ForbiddenException):
    """Access denied"""

    def __init__(
        self,
        message: str = "Access denied",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__("ACCESS_DENIED", message, details)


# Resource-related exceptions
class ResourceNotFoundException(NotFoundException):
    """Resource not found"""

    def __init__(
        self,
        resource_type: str,
        resource_id: str,
        details: Optional[Dict[str, Any]] = None,
    ):
        message = f"{resource_type} not found: {resource_id}"
        super().__init__("RESOURCE_NOT_FOUND", message, details)


class UserNotFoundException(NotFoundException):
    """User not found"""

    def __init__(self, user_id: str, details: Optional[Dict[str, Any]] = None):
        message = f"User not found: {user_id}"
        super().__init__("USER_NOT_FOUND", message, details)


class TaskNotFoundException(NotFoundException):
    """Task not found"""

    def __init__(self, task_id: str, details: Optional[Dict[str, Any]] = None):
        message = f"Task not found: {task_id}"
        super().__init__("TASK_NOT_FOUND", message, details)


# Parameter-related exceptions
class InvalidParameterException(BadRequestException):
    """Invalid parameter"""

    def __init__(
        self,
        parameter: str,
        message: str = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        if message is None:
            message = f"Invalid parameter: {parameter}"
        super().__init__("INVALID_PARAMETER", message, details)


class MissingParameterException(BadRequestException):
    """Missing parameter"""

    def __init__(
        self,
        parameter: str,
        details: Optional[Dict[str, Any]] = None,
    ):
        message = f"Missing required parameter: {parameter}"
        super().__init__("MISSING_PARAMETER", message, details)


class ParameterValidationException(BadRequestException):
    """Parameter validation error"""

    def __init__(
        self,
        parameter: str,
        validation_error: str,
        details: Optional[Dict[str, Any]] = None,
    ):
        message = (
            f"Parameter validation failed: {parameter} - {validation_error}"
        )
        super().__init__("PARAMETER_VALIDATION", message, details)


# Rate limit-related exceptions
class RateLimitExceededException(TooManyRequestsException):
    """Rate limit exceeded"""

    def __init__(
        self,
        operation: str,
        retry_after: int = 60,
        details: Optional[Dict[str, Any]] = None,
    ):
        message = (
            f"Operation {operation} is too frequent, please retry "
            f"after {retry_after} seconds"
        )
        super().__init__("RATE_LIMIT_EXCEEDED", message, details)


# Business logic exceptions
class BusinessLogicException(UnprocessableEntityException):
    """Business logic exception"""


class WorkflowException(BusinessLogicException):
    """Workflow error"""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__("WORKFLOW_ERROR", message, details)


class AgentException(BusinessLogicException):
    """Agent error"""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__("AGENT_ERROR", message, details)


class ResponseException(BusinessLogicException):
    """Response error"""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__("RESPONSE_ERROR", message, details)


# System-related exceptions
class SystemException(InternalServerErrorException):
    """System exception"""


class DatabaseException(SystemException):
    """Database error"""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__("DATABASE_ERROR", message, details)


class RedisException(SystemException):
    """Redis error"""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__("REDIS_ERROR", message, details)


class ExternalServiceException(SystemException):
    """External service error"""

    def __init__(
        self,
        service_name: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ):
        full_message = f"External service {service_name} error: {message}"
        super().__init__("EXTERNAL_SERVICE_ERROR", full_message, details)


# Configuration-related exceptions
class ConfigurationException(InternalServerErrorException):
    """Configuration error"""

    def __init__(
        self,
        config_key: str,
        message: str = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        if message is None:
            message = f"Configuration error: {config_key}"
        super().__init__("CONFIGURATION_ERROR", message, details)


# Network-related exceptions
class NetworkException(ServiceUnavailableException):
    """Network error"""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__("NETWORK_ERROR", message, details)


class TimeoutException(GatewayTimeoutException):
    """Timeout error"""

    def __init__(
        self,
        operation: str,
        timeout: int,
        details: Optional[Dict[str, Any]] = None,
    ):
        message = (
            f"Operation {operation} timed out, timeout limit:"
            f" {timeout} seconds"
        )
        super().__init__("TIMEOUT", message, details)
