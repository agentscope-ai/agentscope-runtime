# -*- coding: utf-8 -*-
"""Deployment modes and configuration for unified FastAPI architecture."""

from enum import Enum
from typing import Optional
from pydantic import BaseModel


class DeploymentMode(str, Enum):
    """FastAPI application deployment modes."""

    DAEMON_THREAD = "daemon_thread"  # LocalDeployManager daemon thread mode
    DETACHED_PROCESS = (
        "detached_process"  # LocalDeployManager detached process mode
    )
    STANDALONE = "standalone"  # Package project template mode


class StreamConfig(BaseModel):
    """Stream response configuration."""

    enabled: bool = True
    buffer_size: Optional[int] = None  # None = no buffering
    chunk_delay: Optional[float] = None  # Delay between chunks in seconds
    error_recovery: bool = True  # Enable error recovery


class DeploymentConfig(BaseModel):
    """Deployment configuration for different modes."""

    mode: DeploymentMode
    host: str = "127.0.0.1"
    port: int = 8000
    timeout: int = 120
    stream_config: Optional[StreamConfig] = None

    def __post_init__(self):
        """Set default stream config based on mode."""
        if self.stream_config is None:
            if self.mode == DeploymentMode.DAEMON_THREAD:
                self.stream_config = StreamConfig(
                    enabled=True,
                    buffer_size=None,
                )
            elif self.mode == DeploymentMode.DETACHED_PROCESS:
                self.stream_config = StreamConfig(
                    enabled=True,
                    buffer_size=None,
                    error_recovery=True,
                )
            elif self.mode == DeploymentMode.STANDALONE:
                self.stream_config = StreamConfig(
                    enabled=True,
                    buffer_size=None,
                )


def validate_deployment_mode(mode_str: str) -> DeploymentMode:
    """Validate and convert string to DeploymentMode enum.

    Args:
        mode_str: String representation of deployment mode

    Returns:
        DeploymentMode: Validated deployment mode enum

    Raises:
        ValueError: If mode_str is not a valid deployment mode
    """
    try:
        return DeploymentMode(mode_str)
    except ValueError as e:
        valid_modes = [mode.value for mode in DeploymentMode]
        raise ValueError(
            f"Invalid deployment mode: {mode_str}. "
            f"Valid modes are: {', '.join(valid_modes)}",
        ) from e
