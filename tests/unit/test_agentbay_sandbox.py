# -*- coding: utf-8 -*-
# pylint: disable=redefined-outer-name, protected-access, unused-argument
# pylint: disable=too-many-public-methods
"""
Unit tests for AgentbaySandbox implementation.
"""
import os
from unittest.mock import MagicMock, patch

import pytest

from agentscope_runtime.sandbox.box.agentbay.agentbay_sandbox import (
    AgentbaySandbox,
)
from agentscope_runtime.sandbox.enums import SandboxType


@pytest.fixture
def mock_agentbay_client():
    """Create a mock AgentBay client."""
    client = MagicMock()
    return client


@pytest.fixture
def mock_session():
    """Create a mock AgentBay session."""
    session = MagicMock()

    # Mock command execution
    command_result = MagicMock()
    command_result.success = True
    command_result.output = "test output"
    command_result.exit_code = 0
    session.command.execute_command.return_value = command_result

    # Mock code execution
    code_result = MagicMock()
    code_result.success = True
    code_result.result = "test result"
    session.code.run_code.return_value = code_result

    # Mock file system operations
    file_result = MagicMock()
    file_result.success = True
    file_result.content = "file content"
    session.file_system.read_file.return_value = file_result
    session.file_system.write_file.return_value = file_result
    session.file_system.list_directory.return_value = file_result
    session.file_system.create_directory.return_value = file_result
    session.file_system.move_file.return_value = file_result
    session.file_system.delete_file.return_value = file_result
    file_result.files = ["file1.txt", "file2.txt"]

    # Mock computer operations
    screenshot_result = MagicMock()
    screenshot_result.success = True
    screenshot_result.data = "screenshot_url"
    session.computer.screenshot.return_value = screenshot_result

    # Mock browser operations
    browser_result = MagicMock()
    browser_result.success = True
    session.browser.agent.navigate.return_value = browser_result
    session.browser.agent.click.return_value = browser_result
    session.browser.agent.input_text.return_value = browser_result

    # Mock session info
    session.info.return_value = MagicMock(
        success=True,
        data=MagicMock(
            session_id="test-session-123",
            resource_id="resource-123",
            resource_url="https://test.com",
            app_id="app-123",
            resource_type="linux",
        ),
        request_id="req-123",
    )

    return session


@pytest.fixture
def mock_create_session_result(mock_session):
    """Create a mock create session result."""
    result = MagicMock()
    result.success = True
    result.session = MagicMock()
    result.session.session_id = "test-session-123"
    return result


@pytest.fixture
def mock_get_session_result(mock_session):
    """Create a mock get session result."""
    result = MagicMock()
    result.success = True
    result.session = mock_session
    return result


@pytest.fixture
def mock_delete_session_result():
    """Create a mock delete session result."""
    result = MagicMock()
    result.success = True
    return result


@pytest.fixture
def mock_list_sessions_result():
    """Create a mock list sessions result."""
    result = MagicMock()
    result.success = True
    result.session_ids = ["session-1", "session-2"]
    result.total_count = 2
    result.request_id = "req-123"
    return result


@pytest.fixture
def agentbay_sandbox(mock_agentbay_client, mock_create_session_result):
    """Create an AgentbaySandbox instance with mocked dependencies."""
    with patch("agentbay.AgentBay") as mock_agentbay_class:
        mock_agentbay_class.return_value = mock_agentbay_client
        mock_agentbay_client.create.return_value = mock_create_session_result

        sandbox = AgentbaySandbox(
            api_key="test-api-key",
            image_id="linux_latest",
            labels={"test": "label"},
        )
        return sandbox


@pytest.fixture
def agentbay_sandbox_with_existing_session(
    mock_agentbay_client,
    mock_get_session_result,
):
    """Create an AgentbaySandbox instance with existing session."""
    with patch("agentbay.AgentBay") as mock_agentbay_class:
        mock_agentbay_class.return_value = mock_agentbay_client
        mock_agentbay_client.get.return_value = mock_get_session_result

        sandbox = AgentbaySandbox(
            sandbox_id="existing-session-123",
            api_key="test-api-key",
        )
        return sandbox


class TestAgentbaySandbox:
    """Test cases for AgentbaySandbox class."""

    def test_init_with_api_key(self, agentbay_sandbox):
        """Test initialization with API key."""
        assert agentbay_sandbox.api_key == "test-api-key"
        assert agentbay_sandbox.image_id == "linux_latest"
        assert agentbay_sandbox.labels == {"test": "label"}
        assert agentbay_sandbox.sandbox_type == SandboxType.AGENTBAY

    def test_init_with_env_var(
        self,
        mock_agentbay_client,
        mock_create_session_result,
    ):
        """Test initialization with environment variable."""
        with patch.dict(os.environ, {"AGENTBAY_API_KEY": "env-api-key"}):
            with patch("agentbay.AgentBay") as mock_agentbay_class:
                mock_agentbay_class.return_value = mock_agentbay_client
                mock_agentbay_client.create.return_value = (
                    mock_create_session_result
                )

                sandbox = AgentbaySandbox(image_id="windows_latest")
                assert sandbox.api_key == "env-api-key"

    def test_init_without_api_key(self, mock_agentbay_client):
        """Test initialization without API key raises error."""
        with patch.dict(os.environ, {}, clear=True):
            with patch("agentbay.AgentBay"):
                with pytest.raises(
                    ValueError,
                    match="AgentBay API key is required",
                ):
                    AgentbaySandbox()

    def test_init_with_bearer_token(
        self,
        mock_agentbay_client,
        mock_create_session_result,
    ):
        """Test initialization with bearer_token (deprecated)."""
        with patch("agentbay.AgentBay") as mock_agentbay_class:
            mock_agentbay_class.return_value = mock_agentbay_client
            mock_agentbay_client.create.return_value = (
                mock_create_session_result
            )

            sandbox = AgentbaySandbox(bearer_token="bearer-token")
            assert sandbox.api_key == "bearer-token"

    def test_init_with_existing_session(
        self,
        agentbay_sandbox_with_existing_session,
    ):
        """Test initialization with existing session ID."""
        assert (
            agentbay_sandbox_with_existing_session._sandbox_id
            == "existing-session-123"
        )

    def test_initialize_cloud_client_success(self):
        """Test successful cloud client initialization."""
        with patch("agentbay.AgentBay") as mock_agentbay_class:
            mock_client = MagicMock()
            mock_agentbay_class.return_value = mock_client

            with patch(
                "agentscope_runtime.sandbox.box.agentbay.agentbay_sandbox."
                "AgentbaySandbox._create_cloud_sandbox",
                return_value="test-session",
            ):
                sandbox = AgentbaySandbox(api_key="test-key")
                assert sandbox.cloud_client is not None

    def test_initialize_cloud_client_import_error(self):
        """Test cloud client initialization with import error."""
        with patch.dict("sys.modules", {"agentbay": None}):
            with pytest.raises(
                ImportError,
                match="AgentBay SDK is not installed",
            ):
                with patch(
                    "agentscope_runtime.sandbox.box.agentbay.agentbay_sandbox."
                    "AgentbaySandbox._create_cloud_sandbox",
                    return_value="test-session",
                ):
                    AgentbaySandbox(api_key="test-key")

    def test_create_cloud_sandbox_success(
        self,
        mock_agentbay_client,
        mock_create_session_result,
    ):
        """Test successful cloud sandbox creation."""
        with patch("agentbay.AgentBay") as mock_agentbay_class:
            mock_agentbay_class.return_value = mock_agentbay_client
            mock_agentbay_client.create.return_value = (
                mock_create_session_result
            )

            with patch("agentbay.session_params.CreateSessionParams"):
                sandbox = AgentbaySandbox(api_key="test-key")
                assert sandbox._sandbox_id == "test-session-123"

    def test_create_cloud_sandbox_failure(self, mock_agentbay_client):
        """Test cloud sandbox creation failure."""
        failed_result = MagicMock()
        failed_result.success = False
        failed_result.error_message = "Creation failed"

        with patch("agentbay.AgentBay") as mock_agentbay_class:
            mock_agentbay_class.return_value = mock_agentbay_client
            mock_agentbay_client.create.return_value = failed_result

            with patch("agentbay.session_params.CreateSessionParams"):
                sandbox = AgentbaySandbox(
                    api_key="test-key",
                    sandbox_id="existing",
                )
                # Should not raise error when sandbox_id is provided
                result = sandbox._create_cloud_sandbox()
                assert result is None

    def test_delete_cloud_sandbox_success(
        self,
        agentbay_sandbox,
        mock_get_session_result,
        mock_delete_session_result,
    ):
        """Test successful cloud sandbox deletion."""
        agentbay_sandbox.cloud_client.get.return_value = (
            mock_get_session_result
        )
        agentbay_sandbox.cloud_client.delete.return_value = (
            mock_delete_session_result
        )

        result = agentbay_sandbox._delete_cloud_sandbox("test-session-123")
        assert result is True

    def test_delete_cloud_sandbox_not_found(self, agentbay_sandbox):
        """Test deleting non-existent sandbox."""
        not_found_result = MagicMock()
        not_found_result.success = False

        agentbay_sandbox.cloud_client.get.return_value = not_found_result

        result = agentbay_sandbox._delete_cloud_sandbox("non-existent")
        assert result is True  # Should return True if already gone

    def test_delete_cloud_sandbox_failure(
        self,
        agentbay_sandbox,
        mock_get_session_result,
    ):
        """Test cloud sandbox deletion failure."""
        failed_result = MagicMock()
        failed_result.success = False
        failed_result.error_message = "Deletion failed"

        agentbay_sandbox.cloud_client.get.return_value = (
            mock_get_session_result
        )
        agentbay_sandbox.cloud_client.delete.return_value = failed_result

        result = agentbay_sandbox._delete_cloud_sandbox("test-session-123")
        assert result is False

    def test_execute_command(self, agentbay_sandbox, mock_session):
        """Test executing a shell command."""
        agentbay_sandbox._sandbox_id = "test-session"
        with patch.object(
            agentbay_sandbox.cloud_client,
            "get",
            return_value=MagicMock(success=True, session=mock_session),
        ):
            result = agentbay_sandbox._execute_command(
                mock_session,
                {"command": "echo hello"},
            )
            assert result["success"] is True
            assert result["output"] == "test output"
            assert result["exit_code"] == 0

    def test_execute_code(self, agentbay_sandbox, mock_session):
        """Test executing Python code."""
        result = agentbay_sandbox._execute_code(
            mock_session,
            {"code": "print('hello')"},
        )
        assert result["success"] is True
        assert result["output"] == "test result"

    def test_read_file(self, agentbay_sandbox, mock_session):
        """Test reading a file."""
        result = agentbay_sandbox._read_file(
            mock_session,
            {"path": "/test.txt"},
        )
        assert result["success"] is True
        assert result["content"] == "file content"

    def test_write_file(self, agentbay_sandbox, mock_session):
        """Test writing a file."""
        result = agentbay_sandbox._write_file(
            mock_session,
            {"path": "/test.txt", "content": "test"},
        )
        assert result["success"] is True

    def test_list_directory(self, agentbay_sandbox, mock_session):
        """Test listing directory contents."""
        result = agentbay_sandbox._list_directory(
            mock_session,
            {"path": "/tmp"},
        )
        assert result["success"] is True
        assert "file1.txt" in result["files"]
        assert "file2.txt" in result["files"]

    def test_create_directory(self, agentbay_sandbox, mock_session):
        """Test creating a directory."""
        result = agentbay_sandbox._create_directory(
            mock_session,
            {"path": "/newdir"},
        )
        assert result["success"] is True

    def test_move_file(self, agentbay_sandbox, mock_session):
        """Test moving a file."""
        result = agentbay_sandbox._move_file(
            mock_session,
            {"source": "/src.txt", "destination": "/dst.txt"},
        )
        assert result["success"] is True

    def test_delete_file(self, agentbay_sandbox, mock_session):
        """Test deleting a file."""
        result = agentbay_sandbox._delete_file(
            mock_session,
            {"path": "/test.txt"},
        )
        assert result["success"] is True

    def test_take_screenshot(self, agentbay_sandbox, mock_session):
        """Test taking a screenshot."""
        result = agentbay_sandbox._take_screenshot(mock_session, {})
        assert result["success"] is True
        assert result["screenshot_url"] == "screenshot_url"

    def test_browser_navigate(self, agentbay_sandbox, mock_session):
        """Test browser navigation."""
        result = agentbay_sandbox._browser_navigate(
            mock_session,
            {"url": "https://example.com"},
        )
        assert result["success"] is True

    def test_browser_click(self, agentbay_sandbox, mock_session):
        """Test browser click."""
        result = agentbay_sandbox._browser_click(
            mock_session,
            {"selector": "#button"},
        )
        assert result["success"] is True

    def test_browser_input(self, agentbay_sandbox, mock_session):
        """Test browser input."""
        result = agentbay_sandbox._browser_input(
            mock_session,
            {"selector": "#input", "text": "test"},
        )
        assert result["success"] is True

    def test_call_cloud_tool_success(
        self,
        agentbay_sandbox,
        mock_get_session_result,
    ):
        """Test calling a cloud tool successfully."""
        agentbay_sandbox._sandbox_id = "test-session"
        agentbay_sandbox.cloud_client.get.return_value = (
            mock_get_session_result
        )

        result = agentbay_sandbox._call_cloud_tool(
            "run_shell_command",
            {"command": "echo hello"},
        )
        assert result["success"] is True

    def test_call_cloud_tool_sandbox_not_found(self, agentbay_sandbox):
        """Test calling a tool when sandbox is not found."""
        not_found_result = MagicMock()
        not_found_result.success = False

        agentbay_sandbox._sandbox_id = "test-session"
        agentbay_sandbox.cloud_client.get.return_value = not_found_result

        result = agentbay_sandbox._call_cloud_tool(
            "run_shell_command",
            {"command": "echo hello"},
        )
        assert result["success"] is False
        assert "Sandbox test-session not found" in result["error"]

    def test_call_cloud_tool_generic(
        self,
        agentbay_sandbox,
        mock_get_session_result,
    ):
        """Test calling a generic tool."""
        mock_session = mock_get_session_result.session
        mock_session.unknown_tool = MagicMock(return_value="result")

        agentbay_sandbox._sandbox_id = "test-session"
        agentbay_sandbox.cloud_client.get.return_value = (
            mock_get_session_result
        )

        result = agentbay_sandbox._call_cloud_tool(
            "unknown_tool",
            {"arg1": "value1"},
        )
        assert result["success"] is True
        assert result["result"] == "result"

    def test_call_cloud_tool_not_found(
        self,
        agentbay_sandbox,
        mock_get_session_result,
    ):
        """Test calling a non-existent tool."""
        # Configure session to not have the attribute
        mock_session = mock_get_session_result.session
        # Use spec to limit available attributes
        from unittest.mock import Mock

        mock_session = Mock(spec=[])  # Empty spec means no attributes
        mock_get_session_result.session = mock_session

        agentbay_sandbox._sandbox_id = "test-session"
        agentbay_sandbox.cloud_client.get.return_value = (
            mock_get_session_result
        )

        result = agentbay_sandbox._call_cloud_tool(
            "non_existent_tool",
            {},
        )
        assert result["success"] is False
        assert "not found in AgentBay session" in result["error"]

    def test_get_session_info_success(
        self,
        agentbay_sandbox,
        mock_get_session_result,
    ):
        """Test getting session info successfully."""
        agentbay_sandbox._sandbox_id = "test-session"
        agentbay_sandbox.cloud_client.get.return_value = (
            mock_get_session_result
        )

        info = agentbay_sandbox.get_session_info()
        assert info["session_id"] == "test-session-123"
        assert info["resource_id"] == "resource-123"
        assert info["resource_url"] == "https://test.com"

    def test_get_session_info_not_found(self, agentbay_sandbox):
        """Test getting session info when session not found."""
        not_found_result = MagicMock()
        not_found_result.success = False

        agentbay_sandbox._sandbox_id = "test-session"
        agentbay_sandbox.cloud_client.get.return_value = not_found_result

        info = agentbay_sandbox.get_session_info()
        assert "error" in info
        assert info["error"] == "Session not found"

    def test_list_sessions_success(
        self,
        agentbay_sandbox,
        mock_list_sessions_result,
    ):
        """Test listing sessions successfully."""
        agentbay_sandbox.cloud_client.list.return_value = (
            mock_list_sessions_result
        )

        result = agentbay_sandbox.list_sessions()
        assert result["success"] is True
        assert result["session_ids"] == ["session-1", "session-2"]
        assert result["total_count"] == 2

    def test_list_sessions_with_labels(
        self,
        agentbay_sandbox,
        mock_list_sessions_result,
    ):
        """Test listing sessions with labels filter."""
        agentbay_sandbox.cloud_client.list.return_value = (
            mock_list_sessions_result
        )

        result = agentbay_sandbox.list_sessions(labels={"test": "label"})
        assert result["success"] is True
        agentbay_sandbox.cloud_client.list.assert_called_once_with(
            labels={"test": "label"},
        )

    def test_list_sessions_with_exception(self, agentbay_sandbox):
        """Test listing sessions with exception."""
        agentbay_sandbox.cloud_client.list.side_effect = Exception(
            "Test error",
        )

        result = agentbay_sandbox.list_sessions()
        assert result["success"] is False
        assert "error" in result

    def test_get_cloud_provider_name(self, agentbay_sandbox):
        """Test getting cloud provider name."""
        assert agentbay_sandbox._get_cloud_provider_name() == "AgentBay"

    def test_list_tools_all(self, agentbay_sandbox):
        """Test listing all tools."""
        result = agentbay_sandbox.list_tools()
        assert "tools" in result
        assert "tools_by_type" in result
        assert "total_count" in result
        assert result["total_count"] == 12  # All tools
        assert "run_shell_command" in result["tools"]
        assert "read_file" in result["tools"]
        assert "browser_navigate" in result["tools"]

    def test_list_tools_by_type_file(self, agentbay_sandbox):
        """Test listing file tools."""
        result = agentbay_sandbox.list_tools(tool_type="file")
        assert result["tool_type"] == "file"
        assert "read_file" in result["tools"]
        assert "write_file" in result["tools"]
        assert "list_directory" in result["tools"]
        assert result["total_count"] == 6  # File tools

    def test_list_tools_by_type_command(self, agentbay_sandbox):
        """Test listing command tools."""
        result = agentbay_sandbox.list_tools(tool_type="command")
        assert result["tool_type"] == "command"
        assert "run_shell_command" in result["tools"]
        assert "run_ipython_cell" in result["tools"]
        assert result["total_count"] == 2  # Command tools

    def test_list_tools_by_type_browser(self, agentbay_sandbox):
        """Test listing browser tools."""
        result = agentbay_sandbox.list_tools(tool_type="browser")
        assert result["tool_type"] == "browser"
        assert "browser_navigate" in result["tools"]
        assert "browser_click" in result["tools"]
        assert "browser_input" in result["tools"]
        assert result["total_count"] == 3  # Browser tools

    def test_list_tools_by_type_system(self, agentbay_sandbox):
        """Test listing system tools."""
        result = agentbay_sandbox.list_tools(tool_type="system")
        assert result["tool_type"] == "system"
        assert "screenshot" in result["tools"]
        assert result["total_count"] == 1  # System tools

    def test_list_tools_unknown_type(self, agentbay_sandbox):
        """Test listing tools with unknown type."""
        result = agentbay_sandbox.list_tools(tool_type="unknown")
        assert result["tool_type"] == "unknown"
        assert result["tools"] == []
        assert result["total_count"] == 0

    def test_call_tool_method(self, agentbay_sandbox, mock_get_session_result):
        """Test the public call_tool method."""
        agentbay_sandbox._sandbox_id = "test-session"
        agentbay_sandbox.cloud_client.get.return_value = (
            mock_get_session_result
        )

        result = agentbay_sandbox.call_tool(
            "run_shell_command",
            {"command": "echo"},
        )
        assert result["success"] is True
