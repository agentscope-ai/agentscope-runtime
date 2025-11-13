# -*- coding: utf-8 -*-
"""
CloudSandbox base class for cloud-based sandbox implementations.

This module provides a base class for cloud sandbox implementations that
don't rely on local container management but instead communicate directly
with cloud APIs.
"""
import logging
from typing import Any, Dict, Optional
from abc import ABC, abstractmethod

from ...enums import SandboxType
from ...box.sandbox import Sandbox

logger = logging.getLogger(__name__)


class CloudSandbox(Sandbox, ABC):
    """
    Base class for cloud-based sandbox implementations.

    This class provides a unified interface for cloud sandbox services that
    don't depend on local container management. Instead, they communicate
    directly with cloud APIs to manage remote environments.

    Key features:
    - No local container dependency
    - Direct cloud API communication
    - Unified interface for cloud sandbox operations
    - Support for different cloud providers
    """

    def __init__(
        self,
        sandbox_id: Optional[str] = None,
        timeout: int = 3000,
        base_url: Optional[str] = None,
        bearer_token: Optional[str] = None,
        sandbox_type: SandboxType = SandboxType.AGENTBAY,
        **kwargs,
    ):
        """
        Initialize the cloud sandbox.

        Args:
            sandbox_id: Optional sandbox ID for existing sessions
            timeout: Timeout for operations in seconds
            base_url: Base URL for cloud API (optional, may use default)
            bearer_token: Authentication token for cloud API
            sandbox_type: Type of sandbox (default: AGENTBAY)
            **kwargs: Additional cloud-specific configuration
        """
        # Initialize base attributes (similar to parent class but without
        # SandboxManager)
        # Note: We don't call super().__init__() because CloudSandbox uses a
        # different architecture - it doesn't need SandboxManager, instead it
        # communicates directly with cloud APIs through cloud_client.
        self.base_url = base_url
        self.embed_mode = False
        self.manager_api = None

        # Store cloud-specific configuration
        self.cloud_config = kwargs
        self.bearer_token = bearer_token

        # Initialize cloud client
        self.cloud_client = self._initialize_cloud_client()

        # Initialize sandbox ID
        if sandbox_id is None:
            sandbox_id = self._create_cloud_sandbox()
            if sandbox_id is None:
                raise RuntimeError(
                    "Failed to create cloud sandbox. "
                    "Please check your cloud API credentials and "
                    "configuration.",
                )

        self._sandbox_id = sandbox_id
        self.sandbox_type = sandbox_type
        self.timeout = timeout

        logger.info(f"Cloud sandbox initialized with ID: {self._sandbox_id}")

    @abstractmethod
    def _initialize_cloud_client(self):
        """
        Initialize the cloud client for API communication.

        This method should be implemented by subclasses to create
        the appropriate cloud client (e.g., AgentBay client).

        Returns:
            Cloud client instance
        """
        # Abstract method - must be implemented by subclasses

    @abstractmethod
    def _create_cloud_sandbox(self) -> Optional[str]:
        """
        Create a new cloud sandbox.

        This method should be implemented by subclasses to create
        a new sandbox using the cloud provider's API.

        Returns:
            Sandbox ID if successful, None otherwise
        """
        # Abstract method - must be implemented by subclasses

    @abstractmethod
    def _delete_cloud_sandbox(self, sandbox_id: str) -> bool:
        """
        Delete a cloud sandbox.

        Args:
            sandbox_id: ID of the sandbox to delete

        Returns:
            True if successful, False otherwise
        """
        # Abstract method - must be implemented by subclasses

    @abstractmethod
    def _call_cloud_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
    ) -> Any:
        """
        Call a tool in the cloud environment.

        Args:
            tool_name: Name of the tool to call
            arguments: Arguments for the tool

        Returns:
            Tool execution result
        """
        # Abstract method - must be implemented by subclasses

    def call_tool(
        self,
        name: str,
        arguments: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """
        Call a tool in the cloud sandbox.

        Args:
            name: Name of the tool to call
            arguments: Arguments for the tool

        Returns:
            Tool execution result
        """
        if arguments is None:
            arguments = {}

        return self._call_cloud_tool(name, arguments)

    def get_info(self) -> Dict[str, Any]:
        """
        Get information about the cloud sandbox.

        Returns:
            Dictionary containing sandbox information
        """
        return {
            "sandbox_id": self._sandbox_id,
            "sandbox_type": self.sandbox_type.value,
            "cloud_provider": self._get_cloud_provider_name(),
            "timeout": self.timeout,
        }

    @abstractmethod
    def _get_cloud_provider_name(self) -> str:
        """
        Get the name of the cloud provider.

        Returns:
            Name of the cloud provider (e.g., "AgentBay")
        """
        # Abstract method - must be implemented by subclasses

    def list_tools(self, tool_type: Optional[str] = None) -> Dict[str, Any]:
        """
        List available tools in the cloud sandbox.

        Args:
            tool_type: Optional filter for tool type

        Returns:
            Dictionary containing available tools
        """
        # Default implementation - subclasses can override
        return {
            "tools": [],
            "tool_type": tool_type,
            "sandbox_id": self._sandbox_id,
        }

    def add_mcp_servers(
        self,
        server_configs: Dict[str, Any],
        overwrite: bool = False,
    ) -> Dict[str, Any]:
        """
        Add MCP servers to the cloud sandbox.

        Args:
            server_configs: Configuration for MCP servers
            overwrite: Whether to overwrite existing configurations

        Returns:
            Result of the operation
        """
        # Default implementation - subclasses can override
        return {
            "success": True,
            "message": "MCP servers added successfully",
            "overwrite": overwrite,
        }

    def _cleanup(self):
        """
        Clean up cloud sandbox resources.

        This method is called when the sandbox is being destroyed.
        It ensures that cloud resources are properly released.
        """
        try:
            if self._sandbox_id:
                success = self._delete_cloud_sandbox(self._sandbox_id)
                if success:
                    logger.info(
                        f"Cloud session {self._sandbox_id} deleted "
                        f"successfully",
                    )
                else:
                    logger.warning(
                        f"Failed to delete cloud session {self._sandbox_id}",
                    )
        except Exception as e:
            logger.error(f"Error during cloud sandbox cleanup: {e}")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """Context manager exit with cleanup."""
        self._cleanup()
