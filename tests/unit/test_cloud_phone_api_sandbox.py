# -*- coding: utf-8 -*-
# pylint: disable=redefined-outer-name, protected-access, unused-argument
# pylint: disable=too-many-public-methods
"""
Unit tests for CloudPhoneSandbox implementation.
"""

import os
from unittest.mock import MagicMock, patch
import pytest

from agentscope_runtime.sandbox.box.cloud_api import (
    CloudPhoneSandbox,
)
from agentscope_runtime.sandbox.enums import SandboxType


@pytest.fixture
def mock_instance_manager():
    """Create a mock instance manager."""
    manager = MagicMock()

    # Mock EDS client
    manager.eds_client = MagicMock()
    manager.eds_client.list_instance.return_value = (
        1,
        None,
        [MagicMock(android_instance_status="running")],
    )
    manager.eds_client.start_equipment.return_value = 200
    manager.eds_client.stop_equipment.return_value = 200

    # Mock instance manager methods
    manager.refresh_ticket = MagicMock()
    manager.run_command = MagicMock(return_value=(True, "command output"))
    manager.tab = MagicMock(return_value=(True, "clicked"))
    manager.type = MagicMock(return_value="text typed")
    manager.slide = MagicMock(return_value=(True, "slid"))
    manager.home = MagicMock(return_value=(True, "went home"))
    manager.back = MagicMock(return_value=(True, "pressed back"))
    manager.menu = MagicMock(return_value=(True, "pressed menu"))
    manager.enter = MagicMock(return_value=(True, "pressed enter"))
    manager.kill_the_front_app = MagicMock(return_value=(True, "killed app"))
    manager.get_screenshot_sdk = MagicMock(
        return_value="http://screenshot.url/image.png",
    )
    manager.send_file = MagicMock(return_value=200)
    manager.remove_file = MagicMock(return_value=(True, "file removed"))

    return manager


@pytest.fixture
def mock_client_pool(mock_instance_manager):
    """Create a mock client pool."""
    pool = MagicMock()
    pool.get_instance_manager.return_value = mock_instance_manager
    pool.get_eds_client.return_value = mock_instance_manager.eds_client
    pool.get_oss_client.return_value = MagicMock()
    return pool


@pytest.fixture
def cloud_phone_sandbox(mock_client_pool, mock_instance_manager):
    """Create a CloudPhoneSandbox instance with mocked dependencies."""
    with patch(
        "agentscope_runtime.sandbox.box.cloud_api"
        ".cloud_phone_sandbox.ClientPool",
    ) as mock_client_pool_class:
        mock_client_pool_class.return_value = mock_client_pool

        with patch.dict(
            os.environ,
            {"PHONE_INSTANCE_ID": "test-instance-id"},
        ):
            # Mock _create_cloud_sandbox to avoid actual API
            # calls during initialization
            with patch.object(
                CloudPhoneSandbox,
                "_create_cloud_sandbox",
                return_value="test-instance-id",
            ):
                sandbox = CloudPhoneSandbox()
                sandbox.instance_manager = mock_instance_manager
                sandbox.eds_client = mock_instance_manager.eds_client
                return sandbox


class TestCloudPhoneSandbox:
    """Test cases for CloudPhoneSandbox class."""

    def test_init_with_instance_id_from_env(
        self,
        mock_client_pool,
        mock_instance_manager,
    ):
        """Test initialization with instance_id from
        environment variable."""
        with patch(
            "agentscope_runtime.sandbox.box.cloud_api."
            "cloud_phone_sandbox.ClientPool",
        ) as mock_client_pool_class:
            mock_client_pool_class.return_value = mock_client_pool

            with patch.dict(
                os.environ,
                {"PHONE_INSTANCE_ID": "env-instance-id"},
            ):
                # Mock _create_cloud_sandbox to avoid actual API calls
                with patch.object(
                    CloudPhoneSandbox,
                    "_create_cloud_sandbox",
                    return_value="env-instance-id",
                ):
                    sandbox = CloudPhoneSandbox()
                    assert sandbox.instance_id == "env-instance-id"
                    assert sandbox.sandbox_type == SandboxType.CLOUD_PHONE
                    assert sandbox.auto_start is True

    def test_init_with_explicit_instance_id(
        self,
        mock_client_pool,
        mock_instance_manager,
    ):
        """Test initialization with explicit instance_id."""
        with patch(
            "agentscope_runtime.sandbox.box.cloud_api"
            ".cloud_phone_sandbox.ClientPool",
        ) as mock_client_pool_class:
            mock_client_pool_class.return_value = mock_client_pool

            # Mock _create_cloud_sandbox to avoid actual API calls
            with patch.object(
                CloudPhoneSandbox,
                "_create_cloud_sandbox",
                return_value="explicit-instance-id",
            ):
                sandbox = CloudPhoneSandbox(instance_id="explicit-instance-id")
                assert sandbox.instance_id == "explicit-instance-id"

    def test_init_without_instance_id_raises_error(self):
        """Test initialization without instance_id raises error."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="instance_id is required"):
                CloudPhoneSandbox()

    def test_initialize_cloud_client_success(self, mock_client_pool):
        """Test successful cloud client initialization."""
        with patch(
            "agentscope_runtime.sandbox.box.cloud_api."
            "cloud_phone_sandbox.ClientPool",
        ) as mock_client_pool_class:
            mock_client_pool_class.return_value = mock_client_pool

            # Mock _create_cloud_sandbox to avoid actual
            # API calls during initialization
            # This prevents _initialize_cloud_client from
            # being called during __init__
            with patch.object(
                CloudPhoneSandbox,
                "_create_cloud_sandbox",
                return_value="test-instance",
            ):
                sandbox = CloudPhoneSandbox(instance_id="test-instance")

                # Reset mock to only count the explicit call in the test
                mock_client_pool.get_instance_manager.reset_mock()
                mock_client_pool.get_eds_client.reset_mock()
                mock_client_pool.get_oss_client.reset_mock()

                eds_client = sandbox._initialize_cloud_client()

                assert eds_client is not None
                mock_client_pool.get_instance_manager.assert_called_once_with(
                    "test-instance",
                )
                mock_client_pool.get_eds_client.assert_called_once()
                mock_client_pool.get_oss_client.assert_called_once()

    def test_create_cloud_sandbox_success(
        self,
        cloud_phone_sandbox,
        mock_instance_manager,
    ):
        """Test successful cloud sandbox creation."""
        # Reset the call count since refresh_ticket may have been
        # called during fixture initialization
        mock_instance_manager.refresh_ticket.reset_mock()

        cloud_phone_sandbox.auto_start = True
        sandbox_id = cloud_phone_sandbox._create_cloud_sandbox()

        assert sandbox_id == "test-instance-id"
        mock_instance_manager.refresh_ticket.assert_called_once()

    def test_create_cloud_sandbox_with_start_failure(
        self,
        cloud_phone_sandbox,
        mock_instance_manager,
    ):
        """Test cloud sandbox creation when start fails."""
        # Reset the call count since refresh_ticket may have been
        # called during fixture initialization
        mock_instance_manager.refresh_ticket.reset_mock()

        cloud_phone_sandbox.auto_start = True
        # Mock _wait_for_phone_ready to raise exception to simulate
        # start failure
        # This avoids the long wait loop in _wait_for_phone_ready
        with patch.object(
            cloud_phone_sandbox,
            "_wait_for_phone_ready",
            side_effect=Exception("Connection error"),
        ):
            # Should still succeed even if start fails
            sandbox_id = cloud_phone_sandbox._create_cloud_sandbox()

            assert sandbox_id == "test-instance-id"
            mock_instance_manager.refresh_ticket.assert_called_once()

    def test_delete_cloud_sandbox_success(
        self,
        cloud_phone_sandbox,
        mock_instance_manager,
    ):
        """Test successful cloud sandbox deletion."""
        result = cloud_phone_sandbox._delete_cloud_sandbox("test-instance-id")

        assert result is True
        m_e = mock_instance_manager.eds_client
        m_e.stop_equipment.assert_called_once_with(
            ["test-instance-id"],
        )

    def test_delete_cloud_sandbox_failure(
        self,
        cloud_phone_sandbox,
        mock_instance_manager,
    ):
        """Test cloud sandbox deletion failure."""
        m_e = mock_instance_manager.eds_client
        m_e.stop_equipment.side_effect = Exception("Network error")

        result = cloud_phone_sandbox._delete_cloud_sandbox(
            "test-instance-id",
        )

        assert result is False

    def test_call_cloud_tool_supported_tool(
        self,
        cloud_phone_sandbox,
        mock_instance_manager,
    ):
        """Test calling a supported tool."""
        result = cloud_phone_sandbox._call_cloud_tool(
            "run_shell_command",
            {"command": "ls -la"},
        )

        assert result["success"] is True
        assert result["output"] == "command output"
        mock_instance_manager.run_command.assert_called_once_with("ls -la")

    def test_call_cloud_tool_unsupported_tool(self, cloud_phone_sandbox):
        """Test calling an unsupported tool."""
        result = cloud_phone_sandbox._call_cloud_tool(
            "unsupported_tool",
            {},
        )

        assert result["success"] is False
        assert "not supported" in result["error"]

    def test_call_cloud_tool_execution_exception(
        self,
        cloud_phone_sandbox,
        mock_instance_manager,
    ):
        """Test calling a tool that throws exception."""
        mock_instance_manager.run_command.side_effect = Exception(
            "Command failed",
        )

        result = cloud_phone_sandbox._call_cloud_tool(
            "run_shell_command",
            {"command": "ls -la"},
        )

        assert result["success"] is False
        assert "Command failed" in result["error"]

    def test_wait_for_phone_ready_success(
        self,
        cloud_phone_sandbox,
        mock_instance_manager,
    ):
        """Test waiting for phone ready successfully."""
        mock_instance_manager.eds_client.list_instance.return_value = (
            1,
            None,
            [MagicMock(android_instance_status="running")],
        )

        result = cloud_phone_sandbox._wait_for_phone_ready(
            "test-instance-id",
            max_wait_time=5,
            stability_check_duration=1,
        )

        assert result is True

    def test_tool_handlers(self, cloud_phone_sandbox, mock_instance_manager):
        """Test various tool handlers."""
        # Test run_shell_command
        result = cloud_phone_sandbox._tool_run_shell_command(
            {"command": "pwd"},
        )
        assert result["success"] is True
        assert result["output"] == "command output"

        # Test click
        result = cloud_phone_sandbox._tool_click(
            {
                "x1": 100,
                "y1": 200,
                "x2": 150,
                "y2": 250,
                "width": 1080,
                "height": 1920,
            },
        )
        assert result["success"] is True
        assert result["output"] == "clicked"

        # Test type_text
        result = cloud_phone_sandbox._tool_type_text({"text": "hello"})
        assert result["success"] is True
        assert result["output"] == "text typed"

        # Test slide
        result = cloud_phone_sandbox._tool_slide(
            {
                "x1": 100,
                "y1": 200,
                "x2": 150,
                "y2": 250,
            },
        )
        assert result["success"] is True
        assert result["output"] == "slid"

        # Test go_home
        result = cloud_phone_sandbox._tool_go_home({})
        assert result["success"] is True
        assert result["output"] == "went home"

        # Test back
        result = cloud_phone_sandbox._tool_back({})
        assert result["success"] is True
        assert result["output"] == "pressed back"

        # Test menu
        result = cloud_phone_sandbox._tool_menu({})
        assert result["success"] is True
        assert result["output"] == "pressed menu"

        # Test enter
        result = cloud_phone_sandbox._tool_enter({})
        assert result["success"] is True
        assert result["output"] == "pressed enter"

        # Test kill_front_app
        result = cloud_phone_sandbox._tool_kill_front_app({})
        assert result["success"] is True
        assert result["output"] == "killed app"

    def test_file_operation_tools(
        self,
        cloud_phone_sandbox,
        mock_instance_manager,
    ):
        """Test file operation tools."""
        # Test send_file
        result = cloud_phone_sandbox._tool_send_file(
            {
                "source_file_path": "/sdcard/test.txt",
                "upload_url": "http://example.com/file.txt",
            },
        )
        assert result["success"] is True
        assert result["status_code"] == 200

        # Test remove_file
        result = cloud_phone_sandbox._tool_remove_file(
            {
                "file_path": "/sdcard/test.txt",
            },
        )
        assert result["success"] is True
        assert result["output"] == "file removed"

    def test_screenshot_tool(self, cloud_phone_sandbox, mock_instance_manager):
        """Test screenshot tool."""
        result = cloud_phone_sandbox._tool_screenshot(
            {
                "max_retry": 3,
            },
        )

        assert result["success"] is True
        assert result["output"] == "http://screenshot.url/image.png"

    def test_list_tools_all_types(self, cloud_phone_sandbox):
        """Test listing all tools."""
        result = cloud_phone_sandbox.list_tools()

        assert "tools" in result
        assert "tools_by_type" in result
        assert result["total_count"] > 0

        # Check that we have tools of different types
        assert "run_shell_command" in result["tools"]  # command tool
        assert "click" in result["tools"]  # input tool
        assert "screenshot" in result["tools"]  # system tool

    def test_list_tools_by_type(self, cloud_phone_sandbox):
        """Test listing tools by specific type."""
        # Test input tools
        result = cloud_phone_sandbox.list_tools("input")
        assert result["tool_type"] == "input"
        assert "click" in result["tools"]
        assert "type_text" in result["tools"]

        # Test navigation tools
        result = cloud_phone_sandbox.list_tools("navigation")
        assert result["tool_type"] == "navigation"
        assert "go_home" in result["tools"]
        assert "back" in result["tools"]

        # Test command tools
        result = cloud_phone_sandbox.list_tools("command")
        assert result["tool_type"] == "command"
        assert "run_shell_command" in result["tools"]
        assert "kill_front_app" in result["tools"]

        # Test system tools
        result = cloud_phone_sandbox.list_tools("system")
        assert result["tool_type"] == "system"
        assert "screenshot" in result["tools"]
        assert "send_file" in result["tools"]

    def test_get_screenshot_methods(
        self,
        cloud_phone_sandbox,
        mock_instance_manager,
    ):
        """Test screenshot methods."""
        # Test get_screenshot_oss_phone success
        result = cloud_phone_sandbox.get_screenshot_oss_phone(max_retry=2)
        assert result == "http://screenshot.url/image.png"

        # Test get_screenshot_oss_phone failure
        # After fix, if get_screenshot_sdk returns None for all retries,
        # the method should return "Error"
        mock_instance_manager.get_screenshot_sdk.return_value = None
        result = cloud_phone_sandbox.get_screenshot_oss_phone(max_retry=2)
        assert result == "Error"
