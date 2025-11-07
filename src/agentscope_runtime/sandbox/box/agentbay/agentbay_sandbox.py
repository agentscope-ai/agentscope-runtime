# -*- coding: utf-8 -*-
"""
AgentbaySandbox implementation for AgentBay cloud environment.

This module provides a sandbox implementation that integrates with AgentBay,
a cloud-native sandbox environment service.
"""
import logging
import os
from typing import Any, Dict, Optional

from ...registry import SandboxRegistry
from ...enums import SandboxType
from ..cloud.cloud_sandbox import CloudSandbox

logger = logging.getLogger(__name__)


@SandboxRegistry.register(
    "agentbay-cloud",  # Virtual image name indicating cloud service
    sandbox_type=SandboxType.AGENTBAY,
    security_level="high",
    timeout=300,
    description="AgentBay Cloud Sandbox Environment",
)
class AgentbaySandbox(CloudSandbox):
    """
    AgentBay cloud sandbox implementation.

    This sandbox provides access to AgentBay's cloud-native sandbox environment
    with support for various image types including Linux, Windows, Browser,
    CodeSpace, and Mobile environments.

    Features:
    - Cloud-native environment (no local containers)
    - Support for multiple image types
    - Direct API communication with AgentBay
    - Session management and lifecycle control
    - Tool execution in cloud environment
    """

    def __init__(
        self,
        sandbox_id: Optional[str] = None,
        timeout: int = 3000,
        base_url: Optional[str] = None,
        bearer_token: Optional[str] = None,
        sandbox_type: SandboxType = SandboxType.AGENTBAY,
        api_key: Optional[str] = None,
        image_id: str = "linux_latest",
        labels: Optional[Dict[str, str]] = None,
        **kwargs,
    ):
        """
        Initialize the AgentBay sandbox.

        Args:
            sandbox_id: Optional sandbox ID for existing sessions
            timeout: Timeout for operations in seconds
            base_url: Base URL for AgentBay API (optional)
            bearer_token: Authentication token (deprecated, use api_key)
            sandbox_type: Type of sandbox (default: AGENTBAY)
            api_key: AgentBay API key (from environment or parameter)
            image_id: AgentBay image type (linux_latest, windows_latest, etc.)
            labels: Optional labels for session organization
            **kwargs: Additional configuration
        """
        # Get API key from parameter, environment, or bearer_token
        self.api_key = api_key or os.getenv("AGENTBAY_API_KEY") or bearer_token
        if not self.api_key:
            raise ValueError(
                "AgentBay API key is required. Set AGENTBAY_API_KEY "
                "environment variable or pass api_key parameter.",
            )

        # Store AgentBay-specific configuration
        self.image_id = image_id
        self.labels = labels or {}
        self.base_url = base_url

        super().__init__(
            sandbox_id=sandbox_id,
            timeout=timeout,
            base_url=base_url,
            bearer_token=self.api_key,
            sandbox_type=sandbox_type,
            **kwargs,
        )

    def _initialize_cloud_client(self):
        """
        Initialize the AgentBay client.

        Returns:
            AgentBay client instance
        """
        try:
            # Import AgentBay SDK
            from agentbay import AgentBay

            # Initialize client with API key
            client = AgentBay(api_key=self.api_key)

            logger.info("AgentBay client initialized successfully")
            return client

        except ImportError as e:
            raise ImportError(
                "AgentBay SDK is not installed. Please install it with: "
                "pip install wuying-agentbay-sdk",
            ) from e
        except Exception as e:
            raise RuntimeError(
                f"Failed to initialize AgentBay client: {e}",
            ) from e

    def _create_cloud_sandbox(self) -> Optional[str]:
        """
        Create a new AgentBay session.

        Returns:
            Session ID if successful, None otherwise
        """
        try:
            from agentbay.session_params import CreateSessionParams

            # Create session parameters
            params = CreateSessionParams(
                image_id=self.image_id,
                labels=self.labels,
            )

            # Create session
            result = self.cloud_client.create(params)

            if result.success:
                session_id = result.session.session_id
                logger.info(f"AgentBay session created: {session_id}")
                return session_id
            else:
                logger.error(
                    f"Failed to create AgentBay session: "
                    f"{result.error_message}",
                )
                return None

        except Exception as e:
            logger.error(f"Error creating AgentBay session: {e}")
            return None

    def _delete_cloud_sandbox(self, sandbox_id: str) -> bool:
        """
        Delete an AgentBay session.

        Args:
            sandbox_id: ID of the session to delete

        Returns:
            True if successful, False otherwise
        """
        try:
            # Get session object first
            get_result = self.cloud_client.get(sandbox_id)
            if not get_result.success:
                logger.warning(
                    f"Session {sandbox_id} not found or already deleted",
                )
                return True  # Consider it successful if already gone

            # Delete the session
            delete_result = self.cloud_client.delete(get_result.session)

            if delete_result.success:
                logger.info(
                    f"AgentBay session {sandbox_id} deleted successfully",
                )
                return True
            else:
                logger.error(
                    f"Failed to delete AgentBay session: "
                    f"{delete_result.error_message}",
                )
                return False

        except Exception as e:
            logger.error(
                f"Error deleting AgentBay session {sandbox_id}: {e}",
            )
            return False

    def _call_cloud_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
    ) -> Any:
        """
        Call a tool in the AgentBay environment.

        Args:
            tool_name: Name of the tool to call
            arguments: Arguments for the tool

        Returns:
            Tool execution result
        """
        try:
            # Get the session object
            get_result = self.cloud_client.get(self._sandbox_id)
            if not get_result.success:
                raise RuntimeError(f"Sandbox {self._sandbox_id} not found")

            session = get_result.session

            # Map tool names to AgentBay session methods
            tool_mapping = {
                "run_shell_command": self._execute_command,
                "run_ipython_cell": self._execute_code,
                "read_file": self._read_file,
                "write_file": self._write_file,
                "list_directory": self._list_directory,
                "create_directory": self._create_directory,
                "move_file": self._move_file,
                "delete_file": self._delete_file,
                "screenshot": self._take_screenshot,
                "browser_navigate": self._browser_navigate,
                "browser_click": self._browser_click,
                "browser_input": self._browser_input,
            }

            if tool_name in tool_mapping:
                return tool_mapping[tool_name](session, arguments)
            else:
                # Try to call as a generic method
                return self._generic_tool_call(session, tool_name, arguments)

        except Exception as e:
            logger.error(f"Error calling tool {tool_name}: {e}")
            return {
                "success": False,
                "error": str(e),
                "tool_name": tool_name,
                "arguments": arguments,
            }

    def _execute_command(
        self,
        session,
        arguments: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute a shell command in AgentBay."""
        command = arguments.get("command", "")
        result = session.command.execute_command(command)

        return {
            "success": result.success,
            "output": result.output,
            "error": result.error if hasattr(result, "error") else None,
            "exit_code": result.exit_code
            if hasattr(result, "exit_code")
            else 0,
        }

    def _execute_code(
        self,
        session,
        arguments: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute Python code in AgentBay."""
        code = arguments.get("code", "")
        result = session.code.run_code(code, "python")

        return {
            "success": result.success,
            "output": result.result,
            "error": result.error if hasattr(result, "error") else None,
        }

    def _read_file(self, session, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Read a file from AgentBay."""
        path = arguments.get("path", "")
        result = session.file_system.read_file(path)

        return {
            "success": result.success,
            "content": result.content if hasattr(result, "content") else None,
            "error": result.error if hasattr(result, "error") else None,
        }

    def _write_file(
        self,
        session,
        arguments: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Write a file to AgentBay."""
        path = arguments.get("path", "")
        content = arguments.get("content", "")
        result = session.file_system.write_file(path, content)

        return {
            "success": result.success,
            "error": result.error if hasattr(result, "error") else None,
        }

    def _list_directory(
        self,
        session,
        arguments: Dict[str, Any],
    ) -> Dict[str, Any]:
        """List directory contents in AgentBay."""
        path = arguments.get("path", ".")
        result = session.file_system.list_directory(path)

        return {
            "success": result.success,
            "files": result.files if hasattr(result, "files") else [],
            "error": result.error if hasattr(result, "error") else None,
        }

    def _create_directory(
        self,
        session,
        arguments: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Create a directory in AgentBay."""
        path = arguments.get("path", "")
        result = session.file_system.create_directory(path)

        return {
            "success": result.success,
            "error": result.error if hasattr(result, "error") else None,
        }

    def _move_file(self, session, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Move a file in AgentBay."""
        source = arguments.get("source", "")
        destination = arguments.get("destination", "")
        result = session.file_system.move_file(source, destination)

        return {
            "success": result.success,
            "error": result.error if hasattr(result, "error") else None,
        }

    def _delete_file(
        self,
        session,
        arguments: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Delete a file in AgentBay."""
        path = arguments.get("path", "")
        result = session.file_system.delete_file(path)

        return {
            "success": result.success,
            "error": result.error if hasattr(result, "error") else None,
        }

    def _take_screenshot(
        self,
        session,
        arguments: Dict[str, Any],  # pylint: disable=unused-argument
    ) -> Dict[str, Any]:
        """Take a screenshot in AgentBay."""
        result = session.computer.screenshot()

        return {
            "success": result.success,
            "screenshot_url": result.data if hasattr(result, "data") else None,
            "error": result.error if hasattr(result, "error") else None,
        }

    def _browser_navigate(
        self,
        session,
        arguments: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Navigate browser in AgentBay."""
        url = arguments.get("url", "")
        result = session.browser.agent.navigate(url)

        return {
            "success": result.success,
            "error": result.error if hasattr(result, "error") else None,
        }

    def _browser_click(
        self,
        session,
        arguments: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Click element in browser."""
        selector = arguments.get("selector", "")
        result = session.browser.agent.click(selector)

        return {
            "success": result.success,
            "error": result.error if hasattr(result, "error") else None,
        }

    def _browser_input(
        self,
        session,
        arguments: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Input text in browser."""
        selector = arguments.get("selector", "")
        text = arguments.get("text", "")
        result = session.browser.agent.input_text(selector, text)

        return {
            "success": result.success,
            "error": result.error if hasattr(result, "error") else None,
        }

    def _generic_tool_call(
        self,
        session,
        tool_name: str,
        arguments: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Generic tool call fallback."""
        try:
            # Try to find and call the method on the session
            if hasattr(session, tool_name):
                method = getattr(session, tool_name)
                result = method(**arguments)

                return {
                    "success": True,
                    "result": result,
                }
            else:
                return {
                    "success": False,
                    "error": (
                        f"Tool '{tool_name}' not found in AgentBay session"
                    ),
                }
        except Exception as e:
            return {
                "success": False,
                "error": f"Error calling tool '{tool_name}': {str(e)}",
            }

    def _get_cloud_provider_name(self) -> str:
        """Get the name of the cloud provider."""
        return "AgentBay"

    def list_tools(self, tool_type: Optional[str] = None) -> Dict[str, Any]:
        """
        List available tools in the AgentBay sandbox.

        Args:
            tool_type: Optional filter for tool type (e.g., "file", "browser")

        Returns:
            Dictionary containing available tools organized by type
        """
        # Define tool categories
        file_tools = [
            "read_file",
            "write_file",
            "list_directory",
            "create_directory",
            "move_file",
            "delete_file",
        ]
        command_tools = ["run_shell_command", "run_ipython_cell"]
        browser_tools = ["browser_navigate", "browser_click", "browser_input"]
        system_tools = ["screenshot"]

        # Organize tools by type
        tools_by_type = {
            "file": file_tools,
            "command": command_tools,
            "browser": browser_tools,
            "system": system_tools,
        }

        # If tool_type is specified, return only that type
        if tool_type:
            tools = tools_by_type.get(tool_type, [])
            return {
                "tools": tools,
                "tool_type": tool_type,
                "sandbox_id": self._sandbox_id,
                "total_count": len(tools),
            }

        # Return all tools organized by type
        all_tools = []
        for tool_list in tools_by_type.values():
            all_tools.extend(tool_list)

        return {
            "tools": all_tools,
            "tools_by_type": tools_by_type,
            "tool_type": tool_type,
            "sandbox_id": self._sandbox_id,
            "total_count": len(all_tools),
        }

    def get_session_info(self) -> Dict[str, Any]:
        """
        Get detailed information about the AgentBay session.

        Returns:
            Dictionary containing session information
        """
        try:
            get_result = self.cloud_client.get(self._sandbox_id)
            if not get_result.success:
                return {"error": "Session not found"}

            session = get_result.session
            info_result = session.info()

            if info_result.success:
                return {
                    "session_id": info_result.data.session_id,
                    "resource_id": info_result.data.resource_id,
                    "resource_url": info_result.data.resource_url,
                    "app_id": info_result.data.app_id,
                    "resource_type": info_result.data.resource_type,
                    "request_id": info_result.request_id,
                }
            else:
                return {"error": info_result.error_message}

        except Exception as e:
            return {"error": str(e)}

    def list_sessions(
        self,
        labels: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        List AgentBay sessions.

        Args:
            labels: Optional labels to filter sessions

        Returns:
            Dictionary containing session list
        """
        try:
            result = self.cloud_client.list(labels=labels)

            return {
                "success": result.success,
                "session_ids": result.session_ids,
                "total_count": result.total_count,
                "request_id": result.request_id,
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }
