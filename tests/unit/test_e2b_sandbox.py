# -*- coding: utf-8 -*-
# pylint: disable=redefined-outer-name, protected-access, unused-argument
# pylint: disable=too-many-public-methods
"""
Unit tests for E2bSandBox implementation.
"""

import os
from unittest.mock import MagicMock, patch
import pytest
from PIL import Image

from agentscope_runtime.sandbox.box.e2b.e2b_sandbox import (
    E2bSandBox,
)
from agentscope_runtime.sandbox.enums import SandboxType


@pytest.fixture
def mock_device():
    """Create a mock E2B device."""
    device = MagicMock()
    device.sandbox_id = "test-sandbox-id"
    device.id = "test-device-id"

    # Mock stream
    device.stream = MagicMock()
    device.stream.start = MagicMock()
    device.stream.stop = MagicMock()

    # Mock commands
    device.commands = MagicMock()
    mock_command_result = MagicMock()
    mock_command_result.stdout = "command output"
    mock_command_result.stderr = ""
    device.commands.run = MagicMock(return_value=mock_command_result)

    # Mock screenshot
    mock_image = Image.new("RGB", (100, 100), color="red")
    device.screenshot = MagicMock(return_value=mock_image)

    # Mock mouse and keyboard operations
    device.move_mouse = MagicMock()
    device.left_click = MagicMock()
    device.right_click = MagicMock()
    device.double_click = MagicMock()
    device.press = MagicMock()
    device.write = MagicMock()
    device.launch = MagicMock()

    return device


@pytest.fixture
def e2b_sandbox(mock_device):
    """Create an E2bSandBox instance with mocked dependencies."""
    with patch(
        "agentscope_runtime.sandbox.box.e2b.e2b_sandbox.Sandbox",
    ) as mock_sandbox_class:
        mock_sandbox_class.create = MagicMock(return_value=mock_device)

        # Mock _create_cloud_sandbox to avoid actual API calls
        # during initialization
        with patch.object(
            E2bSandBox,
            "_create_cloud_sandbox",
            return_value="test-sandbox-id",
        ):
            sandbox = E2bSandBox()
            sandbox.device = mock_device
            return sandbox


class TestE2bSandBox:
    """Test cases for E2bSandBox class."""

    def test_init(self, mock_device):
        """Test initialization."""
        with patch(
            "agentscope_runtime.sandbox.box.e2b.e2b_sandbox.Sandbox",
        ) as mock_sandbox_class:
            mock_sandbox_class.create = MagicMock(return_value=mock_device)

            # Mock _create_cloud_sandbox to avoid actual API calls
            with patch.object(
                E2bSandBox,
                "_create_cloud_sandbox",
                return_value="test-sandbox-id",
            ):
                sandbox = E2bSandBox(timeout=300, command_timeout=30)
                assert sandbox.command_timeout == 30
                assert sandbox.sandbox_type == SandboxType.E2B

    def test_initialize_cloud_client(self, e2b_sandbox):
        """Test cloud client initialization."""
        result = e2b_sandbox._initialize_cloud_client()
        assert result == ""

    def test_create_cloud_sandbox_success(self, mock_device):
        """Test successful cloud sandbox creation."""
        with patch(
            "agentscope_runtime.sandbox.box.e2b.e2b_sandbox.Sandbox",
        ) as mock_sandbox_class:
            mock_sandbox_class.create = MagicMock(return_value=mock_device)

            # Mock _create_cloud_sandbox to avoid actual API
            # calls during initialization
            # This prevents Sandbox.create from being called during __init__
            with patch.object(
                E2bSandBox,
                "_create_cloud_sandbox",
                return_value="test-sandbox-id",
            ):
                sandbox = E2bSandBox()

            # Reset mock to only count the explicit call in the test
            mock_sandbox_class.create.reset_mock()
            mock_device.stream.start.reset_mock()

            sandbox_id = sandbox._create_cloud_sandbox(timeout=300)

            assert sandbox_id == "test-sandbox-id"
            mock_sandbox_class.create.assert_called_once_with(timeout=300)
            mock_device.stream.start.assert_called_once()

    def test_create_cloud_sandbox_failure(self, mock_device):
        """Test cloud sandbox creation failure."""
        with patch(
            "agentscope_runtime.sandbox.box.e2b.e2b_sandbox.Sandbox",
        ) as mock_sandbox_class:
            mock_sandbox_class.create = MagicMock(
                side_effect=Exception("Connection error"),
            )

            # Mock _create_cloud_sandbox to avoid RuntimeError
            # during initialization
            # We'll test the actual failure in the explicit call
            with patch.object(
                E2bSandBox,
                "_create_cloud_sandbox",
                return_value="test-sandbox-id",
            ):
                sandbox = E2bSandBox()

            # Now test the actual failure scenario
            sandbox_id = sandbox._create_cloud_sandbox()

            assert sandbox_id is None

    def test_delete_cloud_sandbox_success(self, e2b_sandbox, mock_device):
        """Test successful cloud sandbox deletion."""
        result = e2b_sandbox._delete_cloud_sandbox("test-sandbox-id")

        assert result is True
        mock_device.stream.stop.assert_called_once()

    def test_delete_cloud_sandbox_failure(self, e2b_sandbox, mock_device):
        """Test cloud sandbox deletion failure."""
        mock_device.stream.stop.side_effect = Exception("Stop error")

        result = e2b_sandbox._delete_cloud_sandbox("test-sandbox-id")

        assert result is False

    def test_call_cloud_tool_supported_tool(self, e2b_sandbox, mock_device):
        """Test calling a supported tool."""
        result = e2b_sandbox._call_cloud_tool(
            "run_shell_command",
            {"command": "ls -la"},
        )

        assert result["success"] is True
        assert "output" in result

    def test_call_cloud_tool_unsupported_tool(self, e2b_sandbox):
        """Test calling an unsupported tool."""
        result = e2b_sandbox._call_cloud_tool(
            "unsupported_tool",
            {},
        )

        assert result["success"] is False
        assert "not supported" in result["error"]

    def test_call_cloud_tool_execution_exception(
        self,
        e2b_sandbox,
        mock_device,
    ):
        """Test calling a tool that throws exception."""
        mock_device.commands.run.side_effect = Exception("Command failed")

        result = e2b_sandbox._call_cloud_tool(
            "run_shell_command",
            {"command": "ls -la"},
        )

        assert result["success"] is False
        assert "Command failed" in result["error"]

    def test_tool_run_command(self, e2b_sandbox, mock_device):
        """Test run command tool."""
        result = e2b_sandbox._tool_run_command({"command": "pwd"})

        assert result["success"] is True
        assert "output" in result
        mock_device.commands.run.assert_called_once()

    def test_tool_run_command_background(self, e2b_sandbox, mock_device):
        """Test run command tool in background."""
        result = e2b_sandbox._tool_run_command(
            {
                "command": "long-running-task",
                "background": True,
            },
        )

        assert result["success"] is True
        assert result["output"] == "The command has been started."
        mock_device.commands.run.assert_called_once_with(
            "long-running-task",
            background=True,
        )

    def test_tool_run_command_missing_command(self, e2b_sandbox):
        """Test run command tool without command."""
        result = e2b_sandbox._tool_run_command({})

        assert result["success"] is False
        assert "command" in result["error"]

    def test_tool_press_key(self, e2b_sandbox, mock_device):
        """Test press key tool."""
        result = e2b_sandbox._tool_press_key({"key": "Enter"})

        assert result["success"] is True
        assert "Enter" in result["output"]
        mock_device.press.assert_called_once_with("Enter")

    def test_tool_press_key_combination(self, e2b_sandbox, mock_device):
        """Test press key combination tool."""
        result = e2b_sandbox._tool_press_key({"key_combination": "Ctrl+C"})

        assert result["success"] is True
        assert "Ctrl+C" in result["output"]
        mock_device.press.assert_called_once_with("Ctrl+C")

    def test_tool_press_key_invalid(self, e2b_sandbox):
        """Test press key with invalid arguments."""
        result = e2b_sandbox._tool_press_key(
            {"key": "Enter", "key_combination": "Ctrl+C"},
        )

        assert result["success"] is False
        assert "Invalid" in result["error"]

    def test_tool_type_text(self, e2b_sandbox, mock_device):
        """Test type text tool."""
        result = e2b_sandbox._tool_type_text({"text": "Hello World"})

        assert result["success"] is True
        assert "typed" in result["output"]
        mock_device.write.assert_called_once()

    def test_tool_type_text_missing_text(self, e2b_sandbox):
        """Test type text tool without text."""
        result = e2b_sandbox._tool_type_text({})

        assert result["success"] is False
        assert "text" in result["error"]

    def test_tool_click(self, e2b_sandbox, mock_device):
        """Test click tool."""
        result = e2b_sandbox._tool_click({"x": 100, "y": 200})

        assert result["success"] is True
        assert "100" in result["output"]
        assert "200" in result["output"]
        mock_device.move_mouse.assert_called_once_with(100, 200)
        mock_device.left_click.assert_called_once()

    def test_tool_click_double_click(self, e2b_sandbox, mock_device):
        """Test double click tool."""
        result = e2b_sandbox._tool_click({"x": 100, "y": 200, "count": 2})

        assert result["success"] is True
        assert "2 times" in result["output"]
        mock_device.double_click.assert_called_once()

    def test_tool_click_with_query(self, e2b_sandbox, mock_device):
        """Test click tool with visual query."""
        with patch(
            "agentscope_runtime.sandbox.box.e2b."
            "e2b_sandbox.perform_gui_grounding_with_api",
        ) as mock_grounding:
            mock_grounding.return_value = (150, 250)

            result = e2b_sandbox._tool_click({"query": "click button"})

            assert result["success"] is True
            mock_device.screenshot.assert_called_once()
            mock_grounding.assert_called_once()
            mock_device.move_mouse.assert_called_once_with(150, 250)

    def test_tool_click_invalid_count(self, e2b_sandbox):
        """Test click tool with invalid count."""
        result = e2b_sandbox._tool_click({"x": 100, "y": 200, "count": 3})

        assert result["success"] is False
        assert "Invalid count" in result["error"]

    def test_tool_right_click(self, e2b_sandbox, mock_device):
        """Test right click tool."""
        result = e2b_sandbox._tool_right_click({"x": 100, "y": 200})

        assert result["success"] is True
        assert "right clicked" in result["output"]
        mock_device.move_mouse.assert_called_once_with(100, 200)
        mock_device.right_click.assert_called_once()

    def test_tool_click_and_type(self, e2b_sandbox, mock_device):
        """Test click and type tool."""
        result = e2b_sandbox._tool_click_and_type(
            {
                "x": 100,
                "y": 200,
                "text": "Hello",
            },
        )

        assert result["success"] is True
        assert "clicked and typed" in result["output"]
        mock_device.move_mouse.assert_called_once_with(100, 200)
        mock_device.left_click.assert_called_once()
        mock_device.write.assert_called_once_with("Hello")

    def test_tool_click_and_type_missing_text(self, e2b_sandbox):
        """Test click and type tool without text."""
        result = e2b_sandbox._tool_click_and_type({"x": 100, "y": 200})

        assert result["success"] is False
        assert "text" in result["error"]

    def test_tool_launch_app(self, e2b_sandbox, mock_device):
        """Test launch app tool."""
        result = e2b_sandbox._tool_launch_app({"app": "notepad"})

        assert result["success"] is True
        assert "notepad" in result["output"]
        mock_device.launch.assert_called_once_with("notepad")

    def test_tool_launch_app_missing_app(self, e2b_sandbox):
        """Test launch app tool without app."""
        result = e2b_sandbox._tool_launch_app({})

        assert result["success"] is False
        assert "app" in result["error"]

    def test_tool_screenshot(self, e2b_sandbox, mock_device, tmpdir):
        """Test screenshot tool."""
        file_path = tmpdir.join("screenshot.png").strpath

        result = e2b_sandbox._tool_screenshot({"file_path": file_path})

        assert result["success"] is True
        assert result["output"] == file_path
        mock_device.screenshot.assert_called_once()
        assert os.path.exists(file_path)

    def test_tool_screenshot_missing_file_path(self, e2b_sandbox):
        """Test screenshot tool without file_path."""
        result = e2b_sandbox._tool_screenshot({})

        assert result["success"] is False
        assert "file_path" in result["error"]

    def test_list_tools_all_types(self, e2b_sandbox):
        """Test listing all tools."""
        result = e2b_sandbox.list_tools()

        assert "tools" in result
        assert "tools_by_type" in result
        assert result["total_count"] > 0

        # Check that we have tools of different types
        assert "run_shell_command" in result["tools"]  # command tool
        assert "click" in result["tools"]  # desktop tool
        assert "screenshot" in result["tools"]  # system tool

    def test_list_tools_by_type(self, e2b_sandbox):
        """Test listing tools by specific type."""
        # Test desktop tools
        result = e2b_sandbox.list_tools("desktop")
        assert result["tool_type"] == "desktop"
        assert "click" in result["tools"]
        assert "press_key" in result["tools"]

        # Test command tools
        result = e2b_sandbox.list_tools("command")
        assert result["tool_type"] == "command"
        assert "run_shell_command" in result["tools"]

        # Test system tools
        result = e2b_sandbox.list_tools("system")
        assert result["tool_type"] == "system"
        assert "screenshot" in result["tools"]
