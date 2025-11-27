# -*- coding: utf-8 -*-
# pylint: disable=redefined-outer-name, protected-access, unused-argument
# pylint: disable=too-many-public-methods
"""
Unit tests for CloudComputerSandbox implementation.
"""

import os
from unittest.mock import MagicMock, patch
import pytest

from agentscope_runtime.sandbox.box.cloud_api import (
    CloudComputerSandbox,
)
from agentscope_runtime.sandbox.enums import SandboxType


@pytest.fixture
def mock_instance_manager():
    """Create a mock instance manager."""
    manager = MagicMock()

    # Mock methods that will be called during tests
    manager.ecd_client = MagicMock()
    manager.ecd_client.search_desktop_info.return_value = [
        MagicMock(desktop_status="running"),
    ]
    manager.ecd_client.start_desktops.return_value = 200
    manager.ecd_client.wakeup_desktops.return_value = 200
    manager.ecd_client.hibernate_desktops.return_value = 200

    manager.refresh_aurh_code = MagicMock()
    manager.run_command_power_shell.return_value = (True, "command output")
    manager.run_code.return_value = (True, "code execution result")
    manager.press_key.return_value = (True, "key pressed")
    manager.tap.return_value = (True, "clicked")
    manager.right_tap.return_value = (True, "right clicked")
    manager.tap_type_enter.return_value = (True, "typed and entered")
    manager.append.return_value = (True, "text appended")
    manager.open_app.return_value = (True, "app launched")
    manager.home.return_value = (True, "went home")
    manager.mouse_move.return_value = (True, "mouse moved")
    manager.scroll.return_value = (True, "scrolled")
    manager.scroll_pos.return_value = (True, "scrolled at position")
    manager.write_file.return_value = (True, "file written")
    manager.read_file.return_value = (True, "file content")
    manager.remove_file.return_value = (True, "file removed")
    manager.get_screenshot_oss_url.return_value = (
        "http://screenshot.url/image.png"
    )

    return manager


@pytest.fixture
def mock_client_pool(mock_instance_manager):
    """Create a mock client pool."""
    pool = MagicMock()
    pool.get_instance_manager.return_value = mock_instance_manager
    pool.get_oss_client.return_value = MagicMock()
    return pool


@pytest.fixture
def cloud_computer_sandbox(mock_client_pool, mock_instance_manager):
    """Create a CloudComputerSandbox instance with mocked dependencies."""
    with patch(
        "agentscope_runtime.sandbox.box.cloud_api."
        "cloud_computer_sandbox.ClientPool",
    ) as mock_client_pool_class:
        mock_client_pool_class.return_value = mock_client_pool

        with patch.dict(os.environ, {"DESKTOP_ID": "test-desktop-id"}):
            # Mock _create_cloud_sandbox to avoid actual API
            # calls during initialization
            with patch.object(
                CloudComputerSandbox,
                "_create_cloud_sandbox",
                return_value="test-desktop-id",
            ):
                sandbox = CloudComputerSandbox()
                sandbox.instance_manager = mock_instance_manager
                return sandbox


class TestCloudComputerSandbox:
    """Test cases for CloudComputerSandbox class."""

    def test_init_with_desktop_id_from_env(
        self,
        mock_client_pool,
        mock_instance_manager,
    ):
        """Test initialization with desktop_id from environment variable."""
        with patch(
            "agentscope_runtime.sandbox.box.cloud_api."
            "cloud_computer_sandbox.ClientPool",
        ) as mock_client_pool_class:
            mock_client_pool_class.return_value = mock_client_pool

            with patch.dict(os.environ, {"DESKTOP_ID": "env-desktop-id"}):
                # Mock _create_cloud_sandbox to avoid actual API calls
                with patch.object(
                    CloudComputerSandbox,
                    "_create_cloud_sandbox",
                    return_value="env-desktop-id",
                ):
                    sandbox = CloudComputerSandbox()
                    assert sandbox.desktop_id == "env-desktop-id"
                    assert sandbox.sandbox_type == SandboxType.CLOUD_COMPUTER
                    assert sandbox.auto_wakeup is True

    def test_init_with_explicit_desktop_id(
        self,
        mock_client_pool,
        mock_instance_manager,
    ):
        """Test initialization with explicit desktop_id."""
        with patch(
            "agentscope_runtime.sandbox.box.cloud_api."
            "cloud_computer_sandbox.ClientPool",
        ) as mock_client_pool_class:
            mock_client_pool_class.return_value = mock_client_pool

            # Mock _create_cloud_sandbox to avoid actual API calls
            with patch.object(
                CloudComputerSandbox,
                "_create_cloud_sandbox",
                return_value="explicit-desktop-id",
            ):
                sandbox = CloudComputerSandbox(
                    desktop_id="explicit-desktop-id",
                )
                assert sandbox.desktop_id == "explicit-desktop-id"

    def test_init_without_desktop_id_raises_error(self):
        """Test initialization without desktop_id raises error."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="desktop_id is required"):
                CloudComputerSandbox()

    def test_screenshot_dir_creation(
        self,
        tmpdir,
        mock_client_pool,
        mock_instance_manager,
    ):
        """Test screenshot directory creation."""
        screenshot_dir = tmpdir.join("screenshots").strpath
        with patch(
            "agentscope_runtime.sandbox.box.cloud_api."
            "cloud_computer_sandbox.ClientPool",
        ) as mock_client_pool_class:
            mock_client_pool_class.return_value = mock_client_pool

            # Mock _create_cloud_sandbox to avoid actual API calls
            with patch.object(
                CloudComputerSandbox,
                "_create_cloud_sandbox",
                return_value="test-desktop",
            ):
                CloudComputerSandbox(
                    desktop_id="test-desktop",
                    screenshot_dir=screenshot_dir,
                )
                assert os.path.exists(screenshot_dir)

    def test_initialize_cloud_client_success(self, mock_client_pool):
        """Test successful cloud client initialization."""
        with patch(
            "agentscope_runtime.sandbox.box.cloud_api."
            "cloud_computer_sandbox.ClientPool",
        ) as mock_client_pool_class:
            mock_client_pool_class.return_value = mock_client_pool

            # Mock _create_cloud_sandbox to avoid actual API
            # calls during initialization
            # This prevents _initialize_cloud_client from being
            # called during __init__
            with patch.object(
                CloudComputerSandbox,
                "_create_cloud_sandbox",
                return_value="test-desktop",
            ):
                sandbox = CloudComputerSandbox(desktop_id="test-desktop")

                # Reset mock to only count the explicit call in the test
                mock_client_pool.get_instance_manager.reset_mock()
                mock_client_pool.get_oss_client.reset_mock()

                instance_manager = sandbox._initialize_cloud_client()

                assert instance_manager is not None
                mock_client_pool.get_instance_manager.assert_called_once_with(
                    "test-desktop",
                )
                mock_client_pool.get_oss_client.assert_called_once()

    def test_create_cloud_sandbox_success(
        self,
        cloud_computer_sandbox,
        mock_instance_manager,
    ):
        """Test successful cloud sandbox creation."""
        # Reset the call count since refresh_aurh_code may have
        # been called during fixture initialization
        mock_instance_manager.refresh_aurh_code.reset_mock()

        cloud_computer_sandbox.auto_wakeup = True
        sandbox_id = cloud_computer_sandbox._create_cloud_sandbox()

        assert sandbox_id == "test-desktop-id"
        mock_instance_manager.refresh_aurh_code.assert_called_once()

    def test_create_cloud_sandbox_with_wakeup_failure(
        self,
        cloud_computer_sandbox,
        mock_instance_manager,
    ):
        """Test cloud sandbox creation when wakeup fails."""
        # Reset the call count since refresh_aurh_code may
        # have been
        # called during fixture initialization
        mock_instance_manager.refresh_aurh_code.reset_mock()

        cloud_computer_sandbox.auto_wakeup = True
        # Mock _wait_for_pc_ready to raise exception to
        # simulate wakeup failure
        # This avoids the long wait loop in _wait_for_pc_ready
        with patch.object(
            cloud_computer_sandbox,
            "_wait_for_pc_ready",
            side_effect=Exception("Connection error"),
        ):
            # Should still succeed even if wakeup fails
            sandbox_id = cloud_computer_sandbox._create_cloud_sandbox()

            assert sandbox_id == "test-desktop-id"
            mock_instance_manager.refresh_aurh_code.assert_called_once()

    def test_delete_cloud_sandbox_success(
        self,
        cloud_computer_sandbox,
        mock_instance_manager,
    ):
        """Test successful cloud sandbox deletion."""
        result = cloud_computer_sandbox._delete_cloud_sandbox(
            "test-desktop-id",
        )

        assert result is True
        m_ec = mock_instance_manager.ecd_client
        m_ec.hibernate_desktops.assert_called_once_with(
            ["test-desktop-id"],
        )

    def test_delete_cloud_sandbox_failure(
        self,
        cloud_computer_sandbox,
        mock_instance_manager,
    ):
        """Test cloud sandbox deletion failure."""
        m_ec = mock_instance_manager.ecd_client
        m_ec.hibernate_desktops.side_effect = Exception("Network error")

        result = cloud_computer_sandbox._delete_cloud_sandbox(
            "test-desktop-id",
        )

        assert result is False

    def test_call_cloud_tool_supported_tool(
        self,
        cloud_computer_sandbox,
        mock_instance_manager,
    ):
        """Test calling a supported tool."""
        result = cloud_computer_sandbox._call_cloud_tool(
            "run_shell_command",
            {"command": "ls -la"},
        )

        assert result["success"] is True
        assert result["output"] == "command output"
        mock_instance_manager.run_command_power_shell.assert_called_once_with(
            "ls -la",
            None,
            60,
        )

    def test_call_cloud_tool_unsupported_tool(self, cloud_computer_sandbox):
        """Test calling an unsupported tool."""
        result = cloud_computer_sandbox._call_cloud_tool(
            "unsupported_tool",
            {},
        )

        assert result["success"] is False
        assert "not supported" in result["error"]

    def test_call_cloud_tool_execution_exception(
        self,
        cloud_computer_sandbox,
        mock_instance_manager,
    ):
        """Test calling a tool that throws exception."""
        mock_instance_manager.run_command_power_shell.side_effect = Exception(
            "Command failed",
        )

        result = cloud_computer_sandbox._call_cloud_tool(
            "run_shell_command",
            {"command": "ls -la"},
        )

        assert result["success"] is False
        assert "Command failed" in result["error"]

    def test_wait_for_pc_ready_success(
        self,
        cloud_computer_sandbox,
        mock_instance_manager,
    ):
        """Test waiting for PC ready successfully."""
        mock_instance_manager.ecd_client.search_desktop_info.return_value = [
            MagicMock(desktop_status="running"),
        ]

        result = cloud_computer_sandbox._wait_for_pc_ready(
            "test-desktop-id",
            max_wait_time=5,
        )

        assert result is True

    def test_handle_desktop_status_stopped(
        self,
        cloud_computer_sandbox,
        mock_instance_manager,
    ):
        """Test handling stopped desktop status."""
        cloud_computer_sandbox._handle_desktop_status(
            "test-desktop-id",
            "stopped",
        )
        m_ec = mock_instance_manager.ecd_client
        m_ec.start_desktops.assert_called_once_with(
            ["test-desktop-id"],
        )

    def test_handle_desktop_status_hibernated(
        self,
        cloud_computer_sandbox,
        mock_instance_manager,
    ):
        """Test handling hibernated desktop status."""
        cloud_computer_sandbox._handle_desktop_status(
            "test-desktop-id",
            "hibernated",
        )
        m_ec = mock_instance_manager.ecd_client
        m_ec.wakeup_desktops.assert_called_once_with(
            ["test-desktop-id"],
        )

    def test_tool_handlers(
        self,
        cloud_computer_sandbox,
        mock_instance_manager,
    ):
        """Test various tool handlers."""
        # Test run_shell_command
        result = cloud_computer_sandbox._tool_run_shell_command(
            {"command": "pwd"},
        )
        assert result["success"] is True
        assert result["output"] == "command output"

        # Test execute_code
        result = cloud_computer_sandbox._tool_execute_code(
            {"code": "print('hello')"},
        )
        assert result["success"] is True
        assert result["output"] == "code execution result"

        # Test press_key
        result = cloud_computer_sandbox._tool_press_key({"key": "enter"})
        assert result["success"] is True
        assert result["output"] == "key pressed"

        # Test click
        result = cloud_computer_sandbox._tool_click({"x": 100, "y": 200})
        assert result["success"] is True
        assert result["output"] == "clicked"

        # Test right_click
        result = cloud_computer_sandbox._tool_right_click({"x": 100, "y": 200})
        assert result["success"] is True
        assert result["output"] == "right clicked"

        # Test click_and_type
        result = cloud_computer_sandbox._tool_click_and_type(
            {"x": 100, "y": 200, "text": "hello"},
        )
        assert result["success"] is True
        assert result["output"] == "typed and entered"

        # Test append_text
        result = cloud_computer_sandbox._tool_append_text(
            {"x": 100, "y": 200, "text": "world"},
        )
        assert result["success"] is True
        assert result["output"] == "text appended"

        # Test launch_app
        result = cloud_computer_sandbox._tool_launch_app({"app": "notepad"})
        assert result["success"] is True
        assert result["output"] == "app launched"

        # Test go_home
        result = cloud_computer_sandbox._tool_go_home({})
        assert result["success"] is True
        assert result["output"] == "went home"

        # Test mouse_move
        result = cloud_computer_sandbox._tool_mouse_move({"x": 100, "y": 200})
        assert result["success"] is True
        assert result["output"] == "mouse moved"

        # Test scroll
        result = cloud_computer_sandbox._tool_scroll({"pixels": 100})
        assert result["success"] is True
        assert result["output"] == "scrolled"

        # Test scroll_pos
        result = cloud_computer_sandbox._tool_scroll_pos(
            {"x": 100, "y": 200, "pixels": 100},
        )
        assert result["success"] is True
        assert result["output"] == "scrolled at position"

    def test_file_operation_tools(
        self,
        cloud_computer_sandbox,
        mock_instance_manager,
    ):
        """Test file operation tools."""
        # Test write_file
        result = cloud_computer_sandbox._tool_write_file(
            {
                "file_path": "/test/file.txt",
                "content": "test content",
            },
        )
        assert result["success"] is True
        assert result["file_path"] == "/test/file.txt"

        # Test read_file
        result = cloud_computer_sandbox._tool_read_file(
            {
                "file_path": "/test/file.txt",
            },
        )
        assert result["success"] is True
        assert result["output"] == "file content"
        assert result["file_path"] == "/test/file.txt"

        # Test remove_file
        result = cloud_computer_sandbox._tool_remove_file(
            {
                "file_path": "/test/file.txt",
            },
        )
        assert result["success"] is True
        assert result["file_path"] == "/test/file.txt"

    def test_screenshot_tool(
        self,
        cloud_computer_sandbox,
        mock_instance_manager,
    ):
        """Test screenshot tool."""
        with patch("uuid.uuid4") as mock_uuid:
            mock_uuid.return_value.hex = "test-uuid"

            result = cloud_computer_sandbox._tool_screenshot(
                {
                    "file_name": "test-screenshot",
                },
            )

            assert result["success"] is True
            assert result["output"] == "http://screenshot.url/image.png"

    def test_list_tools_all_types(self, cloud_computer_sandbox):
        """Test listing all tools."""
        result = cloud_computer_sandbox.list_tools()

        assert "tools" in result
        assert "tools_by_type" in result
        assert result["total_count"] > 0

        # Check that we have tools of different types
        assert "run_shell_command" in result["tools"]  # command tool
        assert "click" in result["tools"]  # input tool
        assert "screenshot" in result["tools"]  # system tool

    def test_list_tools_by_type(self, cloud_computer_sandbox):
        """Test listing tools by specific type."""
        # Test command tools
        result = cloud_computer_sandbox.list_tools("command")
        assert result["tool_type"] == "command"
        assert "run_shell_command" in result["tools"]
        assert "run_ipython_cell" in result["tools"]

        # Test input tools
        result = cloud_computer_sandbox.list_tools("input")
        assert result["tool_type"] == "input"
        assert "click" in result["tools"]
        assert "press_key" in result["tools"]

        # Test system tools
        result = cloud_computer_sandbox.list_tools("system")
        assert result["tool_type"] == "system"
        assert "screenshot" in result["tools"]
        assert "go_home" in result["tools"]

    def test_get_screenshot_methods(
        self,
        cloud_computer_sandbox,
        mock_instance_manager,
    ):
        """Test screenshot methods."""
        # Test get_screenshot_oss_save_local success
        result = cloud_computer_sandbox.get_screenshot_oss_save_local(
            "test-file",
            "/tmp/test.png",
        )
        assert result == "http://screenshot.url/image.png"

        # Test get_screenshot_oss_save_local failure
        mock_instance_manager.get_screenshot_oss_url.return_value = None
        result = cloud_computer_sandbox.get_screenshot_oss_save_local(
            "test-file",
            "/tmp/test.png",
            max_retry=2,
        )
        assert result == "Error"
