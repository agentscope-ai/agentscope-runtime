# -*- coding: utf-8 -*-
# pylint: disable=protected-access,unused-argument,too-many-public-methods
"""
Unit tests for AgentRunDeployer.
"""

import base64
from unittest.mock import AsyncMock, Mock, patch
import pytest

from agentscope_runtime.engine.deployers import AgentRunDeployer
from agentscope_runtime.engine.deployers.agentrun_deployer import (
    CodeConfig,
    ContainerConfig,
    NetworkConfig,
    EndpointConfig,
    LogConfig,
    ProtocolConfig,
)


class TestAgentRunDeployer:
    """Test cases for AgentRunDeployer."""

    @pytest.fixture
    def deployer(self):
        """Create an AgentRunDeployer instance for testing."""
        return AgentRunDeployer(
            account_id="test-account-id",
            access_key_id="test-access-key-id",
            access_key_secret="test-access-key-secret",
            region_id="cn-hangzhou",
        )

    def test_init(self, deployer):
        """Test AgentRunDeployer initialization."""
        assert deployer.account_id == "test-account-id"
        assert deployer.access_key_id == "test-access-key-id"
        assert deployer.access_key_secret == "test-access-key-secret"
        assert deployer.region_id == "cn-hangzhou"
        assert deployer.client is not None
        assert (
            deployer._get_agent_runtime_status_max_attempts
            == AgentRunDeployer.GET_AGENT_RUNTIME_STATUS_MAX_ATTEMPTS
        )
        assert (
            deployer._get_agent_runtime_status_interval
            == AgentRunDeployer.GET_AGENT_RUNTIME_STATUS_INTERVAL
        )

    def test_adapt_code_config(self, deployer):
        """Test _adapt_code_config method."""
        # Test with None config
        result = deployer._adapt_code_config(None)
        assert result is None

        # Test with valid config
        config = CodeConfig(
            checksum="test-checksum",
            command=["python3", "app.py"],
            language="python3.10",
            zip_file="test-zip-content",
        )
        result = deployer._adapt_code_config(config)
        assert result is not None
        assert result.checksum == "test-checksum"
        assert result.command == ["python3", "app.py"]
        assert result.language == "python3.10"
        assert result.zip_file == "test-zip-content"

    def test_adapt_container_config(self, deployer):
        """Test _adapt_container_config method."""
        # Test with None config
        result = deployer._adapt_container_config(None)
        assert result is None

        # Test with valid config
        config = ContainerConfig(
            command=["python3", "app.py"],
            image="test-image:latest",
        )
        result = deployer._adapt_container_config(config)
        assert result is not None
        assert result.command == ["python3", "app.py"]
        assert result.image == "test-image:latest"

    def test_adapt_network_config(self, deployer):
        """Test _adapt_network_config method."""
        # Test with None config
        result = deployer._adapt_network_config(None)
        assert result is None

        # Test with valid config
        config = NetworkConfig(
            network_mode="PUBLIC",
            security_group_id="test-sg-id",
            vpc_id="test-vpc-id",
            vswitch_ids=["test-vswitch-id"],
        )
        result = deployer._adapt_network_config(config)
        assert result is not None
        assert result.network_mode == "PUBLIC"
        assert result.security_group_id == "test-sg-id"
        assert result.vpc_id == "test-vpc-id"
        assert result.vswitch_ids == ["test-vswitch-id"]

    def test_adapt_log_config(self, deployer):
        """Test _adapt_log_config method."""
        # Test with None config
        result = deployer._adapt_log_config(None)
        assert result is None

        # Test with valid config
        config = LogConfig(
            logstore="test-logstore",
            project="test-project",
        )
        result = deployer._adapt_log_config(config)
        assert result is not None
        assert result.logstore == "test-logstore"
        assert result.project == "test-project"

    def test_adapt_protocol_config(self, deployer):
        """Test _adapt_protocol_config method."""
        # Test with None config
        result = deployer._adapt_protocol_config(None)
        assert result is None

        # Test with valid config
        config = ProtocolConfig(
            type="HTTP",
        )
        result = deployer._adapt_protocol_config(config)
        assert result is not None
        assert result.type == "HTTP"

    @pytest.mark.asyncio
    async def test_deploy_code_runtime_success(self, deployer):
        """Test successful deployment of code-based runtime."""
        # Mock the client responses
        with patch.object(
            deployer.client,
            "create_agent_runtime_async",
            new=AsyncMock(),
        ) as mock_create, patch.object(
            deployer.client,
            "create_agent_runtime_endpoint_async",
            new=AsyncMock(),
        ) as mock_create_endpoint, patch.object(
            deployer,
            "_poll_agent_runtime_status",
            new=AsyncMock(),
        ) as mock_poll_runtime, patch.object(
            deployer,
            "_poll_agent_runtime_endpoint_status",
            new=AsyncMock(),
        ) as mock_poll_endpoint:
            # Mock responses
            mock_response = Mock()
            mock_response.body.code = "SUCCESS"
            mock_response.body.data.agent_runtime_id = "test-runtime-id"
            mock_response.body.request_id = "test-request-id"
            mock_create.return_value = mock_response

            mock_endpoint_response = Mock()
            mock_endpoint_response.body.code = "SUCCESS"
            mock_endpoint_response.body.data.agent_runtime_endpoint_id = (
                "test-endpoint-id"
            )
            mock_endpoint_response.body.data.agent_runtime_endpoint_name = (
                "test-endpoint"
            )
            mock_endpoint_response.body.data.endpoint_public_url = (
                "https://test-endpoint.url"
            )
            mock_endpoint_response.body.data.status = "READY"
            mock_endpoint_response.body.request_id = "test-request-id"
            mock_create_endpoint.return_value = mock_endpoint_response

            mock_poll_runtime.return_value = {
                "success": True,
                "status": "READY",
            }
            mock_poll_endpoint.return_value = {
                "success": True,
                "status": "READY",
            }

            # Test deployment
            zip_content = base64.b64encode(
                b"print('Hello, AgentRun!')",
            ).decode("utf-8")
            code_config = CodeConfig(
                language="python3.10",
                command=["python3", "app.py"],
                zip_file=zip_content,
            )
            network_config = NetworkConfig(network_mode="PUBLIC")

            result = await deployer.deploy(
                agent_runtime_name="test-runtime",
                artifact_type="Code",
                cpu=0.5,
                memory=512,
                port=8080,
                code_configuration=code_config,
                network_configuration=network_config,
            )

            # Verify result
            assert result["success"] is True
            assert result["agent_runtime_id"] == "test-runtime-id"
            assert result["agent_runtime_endpoint_id"] == "test-endpoint-id"
            assert result["agent_runtime_endpoint_name"] == "test-endpoint"
            assert (
                result["agent_runtime_public_endpoint_url"]
                == "https://test-endpoint.url"
            )
            assert result["status"] == "READY"

            # Verify calls were made
            mock_create.assert_called_once()
            mock_create_endpoint.assert_called_once()
            mock_poll_runtime.assert_called_once()
            mock_poll_endpoint.assert_called_once()

    @pytest.mark.asyncio
    async def test_deploy_container_runtime_success(self, deployer):
        """Test successful deployment of container-based runtime."""
        # Mock the client responses
        with patch.object(
            deployer.client,
            "create_agent_runtime_async",
            new=AsyncMock(),
        ) as mock_create, patch.object(
            deployer.client,
            "create_agent_runtime_endpoint_async",
            new=AsyncMock(),
        ) as mock_create_endpoint, patch.object(
            deployer,
            "_poll_agent_runtime_status",
            new=AsyncMock(),
        ) as mock_poll_runtime, patch.object(
            deployer,
            "_poll_agent_runtime_endpoint_status",
            new=AsyncMock(),
        ) as mock_poll_endpoint:
            # Mock responses
            mock_response = Mock()
            mock_response.body.code = "SUCCESS"
            mock_response.body.data.agent_runtime_id = (
                "test-container-runtime-id"
            )
            mock_response.body.request_id = "test-request-id"
            mock_create.return_value = mock_response

            mock_endpoint_response = Mock()
            mock_endpoint_response.body.code = "SUCCESS"
            mock_endpoint_response.body.data.agent_runtime_endpoint_id = (
                "test-container-endpoint-id"
            )
            mock_endpoint_response.body.data.agent_runtime_endpoint_name = (
                "test-container-endpoint"
            )
            mock_endpoint_response.body.data.endpoint_public_url = (
                "https://test-container-endpoint.url"
            )
            mock_endpoint_response.body.data.status = "READY"
            mock_endpoint_response.body.request_id = "test-request-id"
            mock_create_endpoint.return_value = mock_endpoint_response

            mock_poll_runtime.return_value = {
                "success": True,
                "status": "READY",
            }
            mock_poll_endpoint.return_value = {
                "success": True,
                "status": "READY",
            }

            # Test deployment
            container_config = ContainerConfig(
                command=["python3", "app.py"],
                image="test-image:latest",
            )
            network_config = NetworkConfig(network_mode="PUBLIC")

            result = await deployer.deploy(
                agent_runtime_name="test-container-runtime",
                artifact_type="Container",
                cpu=1.0,
                memory=1024,
                port=80,
                container_configuration=container_config,
                network_configuration=network_config,
            )

            # Verify result
            assert result["success"] is True
            assert result["agent_runtime_id"] == "test-container-runtime-id"
            assert (
                result["agent_runtime_endpoint_id"]
                == "test-container-endpoint-id"
            )
            assert (
                result["agent_runtime_endpoint_name"]
                == "test-container-endpoint"
            )
            assert (
                result["agent_runtime_public_endpoint_url"]
                == "https://test-container-endpoint.url"
            )
            assert result["status"] == "READY"

    @pytest.mark.asyncio
    async def test_deploy_failure_create_runtime(self, deployer):
        """Test deployment failure when creating runtime fails."""
        # Mock the client responses
        with patch.object(
            deployer.client,
            "create_agent_runtime_async",
            new=AsyncMock(),
        ) as mock_create:
            # Mock failure response
            mock_response = Mock()
            mock_response.body.code = "FAILURE"
            mock_response.body.request_id = "test-request-id"
            mock_create.return_value = mock_response

            # Test deployment
            code_config = CodeConfig(
                language="python3.10",
                command=["python3", "app.py"],
                zip_file="test-zip-content",
            )
            network_config = NetworkConfig(network_mode="PUBLIC")

            result = await deployer.deploy(
                agent_runtime_name="test-runtime",
                artifact_type="Code",
                cpu=0.5,
                memory=512,
                port=8080,
                code_configuration=code_config,
                network_configuration=network_config,
            )

            # Verify result
            assert result["success"] is False
            assert result["code"] == "FAILURE"

    @pytest.mark.asyncio
    async def test_deploy_failure_create_endpoint(self, deployer):
        """Test deployment failure when creating endpoint fails."""
        # Mock the client responses
        with patch.object(
            deployer.client,
            "create_agent_runtime_async",
            new=AsyncMock(),
        ) as mock_create, patch.object(
            deployer.client,
            "create_agent_runtime_endpoint_async",
            new=AsyncMock(),
        ) as mock_create_endpoint, patch.object(
            deployer,
            "_poll_agent_runtime_status",
            new=AsyncMock(),
        ) as mock_poll_runtime:
            # Mock responses
            mock_response = Mock()
            mock_response.body.code = "SUCCESS"
            mock_response.body.data.agent_runtime_id = "test-runtime-id"
            mock_response.body.request_id = "test-request-id"
            mock_create.return_value = mock_response

            mock_endpoint_response = Mock()
            mock_endpoint_response.body.code = "FAILURE"
            mock_endpoint_response.body.request_id = "test-request-id"
            mock_create_endpoint.return_value = mock_endpoint_response

            mock_poll_runtime.return_value = {
                "success": True,
                "status": "READY",
            }

            # Test deployment
            code_config = CodeConfig(
                language="python3.10",
                command=["python3", "app.py"],
                zip_file="test-zip-content",
            )
            network_config = NetworkConfig(network_mode="PUBLIC")

            result = await deployer.deploy(
                agent_runtime_name="test-runtime",
                artifact_type="Code",
                cpu=0.5,
                memory=512,
                port=8080,
                code_configuration=code_config,
                network_configuration=network_config,
            )

            # Verify result
            assert result["success"] is False
            assert result["code"] == "FAILURE"

    @pytest.mark.asyncio
    async def test_create_agent_runtime_success(self, deployer):
        """Test successful creation of agent runtime."""
        # Mock the client response
        with patch.object(
            deployer.client,
            "create_agent_runtime_async",
            new=AsyncMock(),
        ) as mock_create, patch.object(
            deployer,
            "_poll_agent_runtime_status",
            new=AsyncMock(),
        ) as mock_poll:
            # Mock responses
            mock_response = Mock()
            mock_response.body.code = "SUCCESS"
            mock_response.body.data.agent_runtime_id = "test-runtime-id"
            mock_response.body.request_id = "test-request-id"
            mock_create.return_value = mock_response

            mock_poll.return_value = {"success": True, "status": "READY"}

            # Test creation
            code_config = CodeConfig(
                language="python3.10",
                command=["python3", "app.py"],
                zip_file="test-zip-content",
            )

            result = await deployer.create_agent_runtime(
                agent_runtime_name="test-runtime",
                artifact_type="Code",
                cpu=0.5,
                memory=512,
                port=8080,
                code_configuration=code_config,
            )

            # Verify result
            assert result["success"] is True
            assert result["agent_runtime_id"] == "test-runtime-id"
            assert result["status"] == "READY"

    @pytest.mark.asyncio
    async def test_update_agent_runtime_success(self, deployer):
        """Test successful update of agent runtime."""
        # Mock the client response
        with patch.object(
            deployer.client,
            "update_agent_runtime_async",
            new=AsyncMock(),
        ) as mock_update, patch.object(
            deployer,
            "_poll_agent_runtime_status",
            new=AsyncMock(),
        ) as mock_poll:
            # Mock responses
            mock_response = Mock()
            mock_response.body.code = "SUCCESS"
            mock_response.body.request_id = "test-request-id"
            mock_update.return_value = mock_response

            mock_poll.return_value = {"success": True, "status": "READY"}

            # Test update
            result = await deployer.update_agent_runtime(
                agent_runtime_id="test-runtime-id",
                agent_runtime_name="updated-test-runtime",
                cpu=1.0,
                memory=1024,
            )

            # Verify result
            assert result["success"] is True
            assert result["agent_runtime_id"] == "test-runtime-id"
            assert result["status"] == "READY"

    @pytest.mark.asyncio
    async def test_delete_agent_runtime_success(self, deployer):
        """Test successful deletion of agent runtime."""
        # Mock the client response
        with patch.object(
            deployer.client,
            "delete_agent_runtime_async",
            new=AsyncMock(),
        ) as mock_delete, patch.object(
            deployer,
            "_poll_agent_runtime_status",
            new=AsyncMock(),
        ) as mock_poll:
            # Mock responses
            mock_response = Mock()
            mock_response.body.code = "SUCCESS"
            mock_response.body.request_id = "test-request-id"
            mock_delete.return_value = mock_response

            mock_poll.return_value = {"success": True, "status": "DELETING"}

            # Test deletion
            result = await deployer.delete(agent_runtime_id="test-runtime-id")

            # Verify result
            assert result["success"] is True
            assert result["agent_runtime_id"] == "test-runtime-id"
            assert result["status"] == "DELETING"

    @pytest.mark.asyncio
    async def test_get_agent_runtime_success(self, deployer):
        """Test successful retrieval of agent runtime details."""
        # Mock the client response
        with patch.object(
            deployer.client,
            "get_agent_runtime_async",
            new=AsyncMock(),
        ) as mock_get:
            # Mock responses
            mock_data = Mock()
            mock_data.to_map.return_value = {
                "agent_runtime_id": "test-runtime-id",
                "agent_runtime_name": "test-runtime",
                "status": "READY",
            }

            mock_response = Mock()
            mock_response.body.code = "SUCCESS"
            mock_response.body.data = mock_data
            mock_response.body.request_id = "test-request-id"
            mock_get.return_value = mock_response

            # Test get
            result = await deployer.get_agent_runtime(
                agent_runtime_id="test-runtime-id",
            )

            # Verify result
            assert result["success"] is True
            assert result["data"]["agent_runtime_id"] == "test-runtime-id"
            assert result["data"]["agent_runtime_name"] == "test-runtime"
            assert result["data"]["status"] == "READY"

    @pytest.mark.asyncio
    async def test_create_agent_runtime_endpoint_success(self, deployer):
        """Test successful creation of agent runtime endpoint."""
        # Mock the client response
        with patch.object(
            deployer.client,
            "create_agent_runtime_endpoint_async",
            new=AsyncMock(),
        ) as mock_create, patch.object(
            deployer,
            "_poll_agent_runtime_endpoint_status",
            new=AsyncMock(),
        ) as mock_poll:
            # Mock responses
            mock_response = Mock()
            mock_response.body.code = "SUCCESS"
            mock_response.body.data.agent_runtime_endpoint_id = (
                "test-endpoint-id"
            )
            mock_response.body.data.agent_runtime_endpoint_name = (
                "test-endpoint"
            )
            mock_response.body.data.endpoint_public_url = (
                "https://test-endpoint.url"
            )
            mock_response.body.request_id = "test-request-id"
            mock_create.return_value = mock_response

            mock_poll.return_value = {"success": True, "status": "READY"}

            # Test creation
            endpoint_config = EndpointConfig(
                agent_runtime_endpoint_name="test-endpoint",
                target_version="LATEST",
            )

            result = await deployer.create_agent_runtime_endpoint(
                agent_runtime_id="test-runtime-id",
                endpoint_config=endpoint_config,
            )

            # Verify result
            assert result["success"] is True
            assert result["agent_runtime_endpoint_id"] == "test-endpoint-id"
            assert result["agent_runtime_endpoint_name"] == "test-endpoint"
            assert (
                result["agent_runtime_public_endpoint_url"]
                == "https://test-endpoint.url"
            )
            assert result["status"] == "READY"

    @pytest.mark.asyncio
    async def test_update_agent_runtime_endpoint_success(self, deployer):
        """Test successful update of agent runtime endpoint."""
        # Mock the client response
        with patch.object(
            deployer.client,
            "update_agent_runtime_endpoint_async",
            new=AsyncMock(),
        ) as mock_update, patch.object(
            deployer,
            "_poll_agent_runtime_endpoint_status",
            new=AsyncMock(),
        ) as mock_poll:
            # Mock responses
            mock_response = Mock()
            mock_response.body.code = "SUCCESS"
            mock_response.body.request_id = "test-request-id"
            mock_update.return_value = mock_response

            mock_poll.return_value = {"success": True, "status": "READY"}

            # Test update
            endpoint_config = EndpointConfig(
                agent_runtime_endpoint_name="updated-test-endpoint",
                target_version="LATEST",
            )

            result = await deployer.update_agent_runtime_endpoint(
                agent_runtime_id="test-runtime-id",
                agent_runtime_endpoint_id="test-endpoint-id",
                endpoint_config=endpoint_config,
            )

            # Verify result
            assert result["success"] is True
            assert result["agent_runtime_endpoint_id"] == "test-endpoint-id"
            assert result["status"] == "READY"

    @pytest.mark.asyncio
    async def test_get_agent_runtime_endpoint_success(self, deployer):
        """Test successful retrieval of agent runtime endpoint details."""
        # Mock the client response
        with patch.object(
            deployer.client,
            "get_agent_runtime_endpoint_async",
            new=AsyncMock(),
        ) as mock_get:
            # Mock responses
            mock_data = Mock()
            mock_data.agent_runtime_endpoint_id = "test-endpoint-id"
            mock_data.agent_runtime_endpoint_name = "test-endpoint"
            mock_data.agent_runtime_id = "test-runtime-id"
            mock_data.endpoint_public_url = "https://test-endpoint.url"
            mock_data.status = "READY"

            mock_response = Mock()
            mock_response.body.code = "SUCCESS"
            mock_response.body.data = mock_data
            mock_response.body.request_id = "test-request-id"
            mock_get.return_value = mock_response

            # Test get
            result = await deployer.get_agent_runtime_endpoint(
                agent_runtime_id="test-runtime-id",
                agent_runtime_endpoint_id="test-endpoint-id",
            )

            # Verify result
            assert result["success"] is True
            assert result["agent_runtime_endpoint_id"] == "test-endpoint-id"
            assert result["agent_runtime_endpoint_name"] == "test-endpoint"
            assert result["agent_runtime_id"] == "test-runtime-id"
            assert (
                result["agent_runtime_public_endpoint_url"]
                == "https://test-endpoint.url"
            )
            assert result["status"] == "READY"

    @pytest.mark.asyncio
    async def test_delete_agent_runtime_endpoint_success(self, deployer):
        """Test successful deletion of agent runtime endpoint."""
        # Mock the client response
        with patch.object(
            deployer.client,
            "delete_agent_runtime_endpoint_async",
            new=AsyncMock(),
        ) as mock_delete:
            # Mock responses
            mock_response = Mock()
            mock_response.body.code = "SUCCESS"
            mock_response.body.request_id = "test-request-id"
            mock_delete.return_value = mock_response

            # Test deletion
            result = await deployer.delete_agent_runtime_endpoint(
                agent_runtime_id="test-runtime-id",
                agent_runtime_endpoint_id="test-endpoint-id",
            )

            # Verify result
            assert result["success"] is True
            assert result["agent_runtime_endpoint_id"] == "test-endpoint-id"

    @pytest.mark.asyncio
    async def test_publish_agent_runtime_version_success(self, deployer):
        """Test successful publishing of agent runtime version."""
        # Mock the client response
        with patch.object(
            deployer.client,
            "publish_runtime_version_async",
            new=AsyncMock(),
        ) as mock_publish:
            # Mock responses
            mock_data = Mock()
            mock_data.agent_runtime_id = "test-runtime-id"
            mock_data.agent_runtime_version = "v1.0"
            mock_data.description = "Test version"

            mock_response = Mock()
            mock_response.body.code = "SUCCESS"
            mock_response.body.data = mock_data
            mock_response.body.request_id = "test-request-id"
            mock_publish.return_value = mock_response

            # Test publish
            result = await deployer.publish_agent_runtime_version(
                agent_runtime_id="test-runtime-id",
                description="Test version",
            )

            # Verify result
            assert result["success"] is True
            assert result["agent_runtime_id"] == "test-runtime-id"
            assert result["agent_runtime_version"] == "v1.0"
            assert result["description"] == "Test version"


if __name__ == "__main__":
    pytest.main([__file__])
