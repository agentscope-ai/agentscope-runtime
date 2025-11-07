# -*- coding: utf-8 -*-
# pylint: disable=redefined-outer-name, protected-access, abstract-method
"""
Unit tests for CloudSandbox base class.
"""
from typing import Any, Dict, Optional
from unittest.mock import MagicMock, patch

import pytest

from agentscope_runtime.sandbox.box.cloud.cloud_sandbox import CloudSandbox
from agentscope_runtime.sandbox.enums import SandboxType


class MockCloudSandbox(CloudSandbox):
    """Mock implementation of CloudSandbox for testing."""

    def _initialize_cloud_client(self):
        """Initialize mock cloud client."""
        return MagicMock()

    def _create_cloud_sandbox(self) -> Optional[str]:
        """Create mock cloud sandbox."""
        return "test-session-123"

    def _delete_cloud_sandbox(
        self,
        sandbox_id: str,  # pylint: disable=unused-argument
    ) -> bool:
        """Delete mock cloud sandbox."""
        return True

    def _call_cloud_tool(
        self,
        tool_name: str,  # pylint: disable=unused-argument
        arguments: Dict[str, Any],  # pylint: disable=unused-argument
    ) -> Any:
        """Call mock cloud tool."""
        return {"success": True, "result": "mock_result"}

    def _get_cloud_provider_name(self) -> str:
        """Get mock cloud provider name."""
        return "MockCloudProvider"


@pytest.fixture
def mock_cloud_sandbox():
    """Create a mock CloudSandbox instance."""
    return MockCloudSandbox(
        sandbox_id="test-sandbox-123",
        timeout=3000,
        base_url="https://api.example.com",
        bearer_token="test-token",
        sandbox_type=SandboxType.AGENTBAY,
    )


@pytest.fixture
def mock_cloud_sandbox_with_auto_create():
    """Create a CloudSandbox instance that auto-creates session."""
    return MockCloudSandbox(
        sandbox_id=None,
        timeout=3000,
        base_url="https://api.example.com",
        bearer_token="test-token",
        sandbox_type=SandboxType.AGENTBAY,
    )


class TestCloudSandbox:
    """Test cases for CloudSandbox class."""

    def test_init_with_sandbox_id(self, mock_cloud_sandbox):
        """Test initialization with existing sandbox ID."""
        assert mock_cloud_sandbox._sandbox_id == "test-sandbox-123"
        assert mock_cloud_sandbox.sandbox_type == SandboxType.AGENTBAY
        assert mock_cloud_sandbox.timeout == 3000
        assert mock_cloud_sandbox.base_url == "https://api.example.com"
        assert mock_cloud_sandbox.bearer_token == "test-token"
        assert mock_cloud_sandbox.embed_mode is False
        assert mock_cloud_sandbox.manager_api is None
        assert mock_cloud_sandbox.cloud_client is not None

    def test_init_without_sandbox_id(
        self,
        mock_cloud_sandbox_with_auto_create,
    ):
        """Test initialization without sandbox ID (auto-creates session)."""
        assert (
            mock_cloud_sandbox_with_auto_create._sandbox_id
            == "test-session-123"
        )
        assert (
            mock_cloud_sandbox_with_auto_create.sandbox_type
            == SandboxType.AGENTBAY
        )

    def test_init_create_sandbox_fails(self):
        """Test initialization when sandbox creation fails."""
        with patch.object(
            MockCloudSandbox,
            "_create_cloud_sandbox",
            return_value=None,
        ):

            class FailingCloudSandbox(MockCloudSandbox):
                def _create_cloud_sandbox(self) -> Optional[str]:
                    return None

            with pytest.raises(
                RuntimeError,
                match="Failed to create cloud sandbox",
            ):
                FailingCloudSandbox(
                    sandbox_id=None,
                    bearer_token="test-token",
                )

    def test_call_tool(self, mock_cloud_sandbox):
        """Test calling a tool."""
        result = mock_cloud_sandbox.call_tool("test_tool", {"arg1": "value1"})
        assert result["success"] is True
        assert result["result"] == "mock_result"

    def test_call_tool_with_none_arguments(self, mock_cloud_sandbox):
        """Test calling a tool with None arguments."""
        result = mock_cloud_sandbox.call_tool("test_tool", None)
        assert result["success"] is True

    def test_get_info(self, mock_cloud_sandbox):
        """Test getting sandbox information."""
        info = mock_cloud_sandbox.get_info()
        assert info["sandbox_id"] == "test-sandbox-123"
        assert info["sandbox_type"] == SandboxType.AGENTBAY.value
        assert info["cloud_provider"] == "MockCloudProvider"
        assert info["timeout"] == 3000

    def test_list_tools(self, mock_cloud_sandbox):
        """Test listing tools."""
        tools = mock_cloud_sandbox.list_tools()
        assert tools["tools"] == []
        assert tools["sandbox_id"] == "test-sandbox-123"
        assert tools["tool_type"] is None

    def test_list_tools_with_type(self, mock_cloud_sandbox):
        """Test listing tools with specific type."""
        tools = mock_cloud_sandbox.list_tools(tool_type="file")
        assert tools["tool_type"] == "file"

    def test_add_mcp_servers(self, mock_cloud_sandbox):
        """Test adding MCP servers."""
        server_configs = {
            "mcpServers": {"server1": {"url": "http://test.com"}},
        }
        result = mock_cloud_sandbox.add_mcp_servers(
            server_configs,
            overwrite=False,
        )
        assert result["success"] is True
        assert result["overwrite"] is False
        assert "MCP servers added successfully" in result["message"]

    def test_add_mcp_servers_with_overwrite(self, mock_cloud_sandbox):
        """Test adding MCP servers with overwrite."""
        server_configs = {
            "mcpServers": {"server1": {"url": "http://test.com"}},
        }
        result = mock_cloud_sandbox.add_mcp_servers(
            server_configs,
            overwrite=True,
        )
        assert result["overwrite"] is True

    def test_cleanup_success(self, mock_cloud_sandbox):
        """Test cleanup with successful deletion."""
        with patch.object(
            mock_cloud_sandbox,
            "_delete_cloud_sandbox",
            return_value=True,
        ) as mock_delete:
            mock_cloud_sandbox._cleanup()
            mock_delete.assert_called_once_with("test-sandbox-123")

    def test_cleanup_failure(self, mock_cloud_sandbox):
        """Test cleanup with failed deletion."""
        with patch.object(
            mock_cloud_sandbox,
            "_delete_cloud_sandbox",
            return_value=False,
        ) as mock_delete:
            mock_cloud_sandbox._cleanup()
            mock_delete.assert_called_once_with("test-sandbox-123")

    def test_cleanup_with_exception(self, mock_cloud_sandbox):
        """Test cleanup with exception."""
        with patch.object(
            mock_cloud_sandbox,
            "_delete_cloud_sandbox",
            side_effect=Exception("Test error"),
        ):
            # Should not raise exception
            mock_cloud_sandbox._cleanup()

    def test_cleanup_without_sandbox_id(self):
        """Test cleanup when sandbox_id is None."""
        sandbox = MockCloudSandbox(
            sandbox_id=None,
            bearer_token="test-token",
        )
        # Set sandbox_id to None after creation
        sandbox._sandbox_id = None
        # Should not raise exception
        sandbox._cleanup()

    def test_context_manager(self, mock_cloud_sandbox):
        """Test context manager functionality."""
        with patch.object(
            mock_cloud_sandbox,
            "_delete_cloud_sandbox",
            return_value=True,
        ) as mock_delete:
            with mock_cloud_sandbox:
                assert mock_cloud_sandbox._sandbox_id == "test-sandbox-123"
            mock_delete.assert_called_once()

    def test_context_manager_with_exception(self, mock_cloud_sandbox):
        """Test context manager with exception."""
        with patch.object(
            mock_cloud_sandbox,
            "_delete_cloud_sandbox",
            return_value=True,
        ):
            try:
                with mock_cloud_sandbox:
                    raise ValueError("Test exception")
            except ValueError:
                pass
            # Cleanup should still be called

    def test_cloud_config_storage(self):
        """Test that cloud-specific config is stored."""
        sandbox = MockCloudSandbox(
            sandbox_id="test-123",
            bearer_token="token",
            custom_param="value",
            another_param=42,
        )
        assert sandbox.cloud_config["custom_param"] == "value"
        assert sandbox.cloud_config["another_param"] == 42

    def test_abstract_methods_must_be_implemented(self):
        """Test that abstract methods must be implemented."""
        with pytest.raises(TypeError):
            # This should fail because abstract methods are not implemented
            # pylint: disable=abstract-class-instantiated
            CloudSandbox(sandbox_id="test", bearer_token="token")
