# -*- coding: utf-8 -*-
"""Input validation utilities for CLI."""

import os

from agentscope_runtime.engine.deployers.state import DeploymentStateManager


class ValidationError(Exception):
    """Raised when validation fails."""


def validate_agent_source(source: str) -> tuple[str, str]:
    """
    Validate and determine the type of agent source.

    Args:
        source: Path to file/directory or deployment ID

    Returns:
        Tuple of (source_type, normalized_path/id)
        source_type can be: 'file', 'directory', 'deployment_id'

    Raises:
        ValidationError: If source is invalid
    """
    if not source:
        raise ValidationError("Agent source cannot be empty")

    # Check if it's a file
    if os.path.isfile(source):
        if not source.endswith(".py"):
            raise ValidationError(
                f"Agent source file must be a Python file: {source}",
            )
        return ("file", os.path.abspath(source))

    # Check if it's a directory
    if os.path.isdir(source):
        return ("directory", os.path.abspath(source))

    # Check if it's a deployment ID by querying state manager
    # This ensures we only accept deployment IDs that actually exist
    # Support both formats: platform_timestamp_id (with underscore) and UUID
    # format
    state_manager = DeploymentStateManager()
    if state_manager.exists(source):
        return ("deployment_id", source)

    raise ValidationError(
        f"Invalid agent source: {source}\n"
        "Must be a Python file (.py), directory, or deployment ID",
    )


def validate_port(port: int) -> int:
    """Validate port number."""
    if not isinstance(port, int):
        try:
            port = int(port)
        except (ValueError, TypeError) as e:
            raise ValidationError(f"Port must be an integer: {port}") from e

    if port < 1 or port > 65535:
        raise ValidationError(f"Port must be between 1 and 65535: {port}")

    return port


def validate_platform(platform: str, supported_platforms: list[str]) -> str:
    """Validate platform name."""
    if platform not in supported_platforms:
        raise ValidationError(
            f"Unsupported platform: {platform}\n"
            f"Supported platforms: {', '.join(supported_platforms)}",
        )
    return platform


def validate_file_exists(file_path: str) -> str:
    """Validate that file exists."""
    if not os.path.isfile(file_path):
        raise ValidationError(f"File not found: {file_path}")
    return os.path.abspath(file_path)


def validate_directory_exists(dir_path: str) -> str:
    """Validate that directory exists."""
    if not os.path.isdir(dir_path):
        raise ValidationError(f"Directory not found: {dir_path}")
    return os.path.abspath(dir_path)


def validate_url(url: str) -> str:
    """Basic URL validation."""
    if not url:
        raise ValidationError("URL cannot be empty")

    if not (url.startswith("http://") or url.startswith("https://")):
        raise ValidationError(
            f"URL must start with http:// or https://: {url}",
        )

    return url


def validate_deployment_id(deploy_id: str) -> str:
    """Validate deployment ID format."""
    if not deploy_id:
        raise ValidationError("Deployment ID cannot be empty")

    if "_" not in deploy_id:
        raise ValidationError(
            f"Invalid deployment ID format: {deploy_id}\n"
            "Expected format: platform_timestamp_id",
        )

    return deploy_id
