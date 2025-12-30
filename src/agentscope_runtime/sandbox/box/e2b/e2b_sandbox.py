# -*- coding: utf-8 -*-
"""
E2BSandbox implementation for E2B cloud environment.

This module provides a sandbox implementation that integrates with E2B,
a cloud-native sandbox environment service.
"""
import logging
from typing import Optional, Dict, Any
from e2b_desktop import Sandbox
from PIL import Image
from agentscope_runtime.sandbox.enums import (
    SandboxType,
)
from agentscope_runtime.sandbox.registry import SandboxRegistry
from agentscope_runtime.sandbox.box.cloud.cloud_sandbox import CloudSandbox
from .utils.grounding_utils import (
    perform_gui_grounding_with_api,
)


logger = logging.getLogger(__name__)

execute_wait_time_: int = 5


@SandboxRegistry.register(
    "e2b-desktop",  # Virtual image name indicating cloud service
    sandbox_type=SandboxType.E2B,
    security_level="high",
    timeout=300,
    description="E2B Desktop Sandbox Environment",
)
class E2bSandBox(CloudSandbox):
    def __init__(
        self,
        *,
        timeout: int = 600,
        sandbox_type: SandboxType = SandboxType.E2B,
        command_timeout: int = 60,
        **kwargs,
    ) -> None:
        self.command_timeout = command_timeout

        super().__init__(
            timeout=timeout,
            sandbox_type=sandbox_type,
            **kwargs,
        )

    # ------------------------------------------------------------------
    # CloudSandbox abstract implementations
    # ------------------------------------------------------------------
    def _initialize_cloud_client(self):  # type: ignore[override]
        return ""

    def _create_cloud_sandbox(self, timeout: int = 600) -> Optional[str]:
        try:
            self.device = Sandbox.create(timeout=timeout)
            self.device.stream.start()
            logger.info(
                f"E2B sandbox initialized with ID: {self.device.sandbox_id}",
            )
            return self.device.sandbox_id
        except Exception as error:  # pylint: disable=broad-except
            logger.error(
                f"Error preparing cloud phone sandbox: {error}",
            )
            return None

    def _delete_cloud_sandbox(self, sandbox_id: str = None) -> bool:
        """Stop cloud phone instance (optional cleanup)."""
        try:
            # Note: We don't delete the instance, just stop it
            # The instance can be reused later
            print(f"Stopping sandbox {sandbox_id}...")
            self.device.stream.stop()
            return True
        except Exception as error:  # pylint: disable=broad-except
            logger.error("Failed to stop instance %s", error)
            return False

    def _call_cloud_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
    ) -> Any:
        """
        Call a tool in the E2B environment.

        Args:
            tool_name: Name of the tool to call
            arguments: Arguments for the tool

        Returns:
            Tool execution result
        """
        try:
            # Map tool names to E2B methods
            tool_mapping = {
                "run_shell_command": self._tool_run_command,
                "screenshot": self._tool_screenshot,
                "click": self._tool_click,
                "right_click": self._tool_right_click,
                "click_and_type": self._tool_click_and_type,
                "type_text": self._tool_type_text,
                "press_key": self._tool_press_key,
                "launch_app": self._tool_launch_app,
            }

            if tool_name in tool_mapping:
                return tool_mapping[tool_name](arguments)
            else:
                logger.warning(
                    f"Tool {tool_name} not supported in E2B sandbox",
                )
                return {
                    "success": False,
                    "error": f"Tool '{tool_name}' not supported",
                    "tool_name": tool_name,
                }

        except Exception as e:
            logger.error(f"Error calling tool {tool_name}: {e}")
            return {
                "success": False,
                "error": str(e),
                "tool_name": tool_name,
                "arguments": arguments,
            }

    def _get_cloud_provider_name(self) -> str:  # type: ignore[override]
        """Get the name of the cloud provider."""
        return "E2B DESKTOP"

    def list_tools(self, tool_type: Optional[str] = None) -> Dict[str, Any]:
        """
        List available tools in the E2B sandbox.

        Args:
            tool_type: Optional filter for tool type

        Returns:
            Dictionary containing available tools
        """
        # Define tool categories
        desktop_tools = [
            "click",
            "right_click",
            "type_text",
            "press_key",
            "launch_app",
            "click_and_type",
        ]
        command_tools = ["run_shell_command"]
        system_tools = [
            "screenshot",
        ]
        # Organize tools by type
        tools_by_type = {
            "desktop": desktop_tools,
            "command": command_tools,
            "system": system_tools,
        }

        # If tool_type is specified, return only that type
        if tool_type:
            tools = tools_by_type.get(tool_type, [])
            return {
                "tools": tools,
                "tool_type": tool_type,
                "sandbox_id": self.device.id,
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
            "sandbox_id": self.device.id,
            "total_count": len(all_tools),
        }

    def _tool_run_command(
        self,
        arguments: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute a shell command in E2B."""
        try:
            command = arguments.get("command")
            if not command:
                return {
                    "success": False,
                    "error": "'command' argument is required",
                }

            background = arguments.get("background")
            timeout = arguments.get("timeout", self.command_timeout)
            if background:
                self.device.commands.run(command, background=True)
                return {
                    "success": True,
                    "output": "The command has been started.",
                }
            else:
                result = self.device.commands.run(command, timeout=timeout)
                stdout, stderr = result.stdout, result.stderr
                if stdout and stderr:
                    output = stdout + "\n" + stderr
                elif stdout or stderr:
                    output = stdout + stderr
                else:
                    output = "The command finished running."

                return {
                    "success": True,
                    "output": output,
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    def _tool_press_key(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Press a key or key combination.

        Args:
            arguments: Dictionary containing 'key' or
             'key_combination' parameters

        Returns:
            Execution result dictionary with success status and output or
             error message
        """
        try:
            key = arguments.get("key")
            key_combination = arguments.get("key_combination")

            if key and not key_combination:
                self.device.press(key)
                return {
                    "success": True,
                    "output": f"The key {key} has been pressed.",
                }
            elif key_combination and not key:
                self.device.press(key_combination)
                return {
                    "success": True,
                    "output": f"The key combination {key_combination} "
                    "has been pressed.",
                }
            else:
                raise ValueError("Invalid key or key combination")
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    def _tool_type_text(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Type text in the sandbox environment.

        Args:
            arguments: Dictionary containing 'text' parameter

        Returns:
            Execution result dictionary with success status and
            output or error message
        """
        try:
            text = arguments.get("text")
            if not text:
                return {
                    "success": False,
                    "error": "'text' argument is required",
                }

            self.device.write(
                text,
                chunk_size=50,
                delay_in_ms=12,
            )
            return {
                "success": True,
                "output": "The text has been typed.",
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    def _tool_click(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Click at specific coordinates or based on visual query.

        Args:
            arguments: Dictionary containing click parameters

        Returns:
            Execution result dictionary with success status and
            output or error message
        """
        try:
            x = arguments.get("x", 0)
            y = arguments.get("y", 0)
            count = arguments.get("count", 1)
            query = arguments.get("query", "")
            if isinstance(count, str):
                count = int(count)
            if query:
                # Visual query-based clicking
                img_bytes = self.device.screenshot()
                position = perform_gui_grounding_with_api(
                    min_pixels=4096,
                    screenshot=img_bytes,
                    user_query=query,
                )
                x, y = position

            self.device.move_mouse(x, y)
            if count == 1:
                self.device.left_click()
            elif count == 2:
                self.device.double_click()
            else:
                raise ValueError(
                    f"Invalid count: {count}, only support 1 or 2",
                )

            return {
                "success": True,
                "output": f"The mouse has clicked {count} times "
                f"at ({x}, {y}).",
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    def _tool_right_click(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Right click at specific coordinates.

        Args:
            arguments: Dictionary containing 'x' and 'y' parameters

        Returns:
            Execution result dictionary with success status and
            output or error message
        """
        try:
            x = arguments.get("x", 0)
            y = arguments.get("y", 0)

            self.device.move_mouse(x, y)
            self.device.right_click()
            return {
                "success": True,
                "output": f"The mouse has right clicked at ({x}, {y}).",
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    def _tool_click_and_type(
        self,
        arguments: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Click at coordinates and then type text.

        Args:
            arguments: Dictionary containing 'x', 'y', and 'text' parameters

        Returns:
            Execution result dictionary with success status
             and output or error message
        """
        try:
            x = arguments.get("x", 0)
            y = arguments.get("y", 0)
            text = arguments.get("text", "")

            if not text:
                return {
                    "success": False,
                    "error": "'text' argument is required",
                }

            self.device.move_mouse(x, y)
            self.device.left_click()
            self.device.write(text)
            return {
                "success": True,
                "output": "The mouse has clicked and typed "
                f"the text at ({x}, {y}).",
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    def _tool_launch_app(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Launch an application.

        Args:
            arguments: Dictionary containing 'app' parameter

        Returns:
            Execution result dictionary with success status and
             output or error message
        """
        try:
            app = arguments.get("app")
            if not app:
                return {
                    "success": False,
                    "error": "'app' argument is required",
                }

            self.device.launch(app)
            return {
                "success": True,
                "output": f"The application {app} has been launched.",
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    def _tool_screenshot(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Take a screenshot and save it to a file.

        Args:
            arguments: Dictionary containing 'file_path' parameter

        Returns:
            Execution result dictionary with success status
             and output or error message
        """
        try:
            file = self.device.screenshot()
            file_path = arguments.get("file_path")

            # 检查 file_path 是否存在
            if not file_path:
                return {
                    "success": False,
                    "error": "'file_path' argument is required",
                }

            if isinstance(file, Image.Image):
                file.save(file_path)
            else:
                with open(file_path, "wb") as f:
                    f.write(file)
            return {
                "success": True,
                "output": file_path,
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }
