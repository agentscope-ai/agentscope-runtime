# -*- coding: utf-8 -*-
# pylint:disable=protected-access, unused-argument
# pylint:disable=use-implicit-booleaness-not-comparison


import os
import shutil
import tempfile
from unittest.mock import patch

import pytest

from agentscope_runtime.engine.deployers.sandbox_deployer import (
    SandboxDeployManager,
    K8sConfig,
)
from agentscope_runtime.engine.deployers.utils.docker_image_utils import (
    RegistryConfig,
)


class TestK8sConfig:
    """Test cases for K8sConfig model."""

    def test_k8s_config_defaults(self):
        """Test K8sConfig default values."""
        config = K8sConfig()
        assert config.k8s_namespace == "agentscope-runtime"
        assert config.kubeconfig_path is None

    def test_k8s_config_creation(self):
        """Test K8sConfig creation with custom values."""
        config = K8sConfig(
            k8s_namespace="custom-namespace",
            kubeconfig_path="/path/to/kubeconfig",
        )
        assert config.k8s_namespace == "custom-namespace"
        assert config.kubeconfig_path == "/path/to/kubeconfig"


class TestSandboxDeployManager:  # pylint: disable=too-many-public-methods
    """Test cases for SandboxDeployManager class."""

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """Set up and tear down test environment."""
        self.temp_dir = tempfile.mkdtemp()
        yield
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    @patch(
        "agentscope_runtime.engine.deployers.sandbox_deployer.SandboxClient",
    )
    def test_sandbox_deployer_creation(self, mock_sandbox_client):
        """Test SandboxDeployManager creation."""
        k8s_config = K8sConfig()
        registry_config = RegistryConfig()

        deployer = SandboxDeployManager(
            kube_config=k8s_config,
            registry_config=registry_config,
        )

        assert deployer.kubeconfig == k8s_config
        assert deployer.registry_config == registry_config
        assert deployer.build_context_dir is None

        # Verify that SandboxClient was instantiated with correct parameters
        mock_sandbox_client.assert_called_once_with(
            config=k8s_config,
            image_registry=registry_config.get_full_url(),
        )

    @patch(
        "agentscope_runtime.engine.deployers.sandbox_deployer.SandboxClient",
    )
    @patch(
        "agentscope_runtime.engine.deployers.sandbox_deployer.time.sleep",
    )
    @patch(
        "agentscope_runtime.engine.deployers.sandbox_deployer.isLocalK8sEnvironment",  # noqa E501
        return_value=True,
    )
    @pytest.mark.asyncio
    async def test_deploy_with_runner_success(
        self,
        mock_is_local,
        mock_sleep,
        mock_sandbox_client,
        mocker,
    ):
        """Test successful sandbox deployment with runner."""
        # Setup mocks
        mock_runner = mocker.Mock()
        mock_runner._agent = mocker.Mock()
        mock_runner.__class__.__name__ = "MockRunner"

        # Mock SandboxClient instance
        mock_client_instance = mocker.Mock()
        mock_client_instance.create_sandbox.return_value = (
            "agent-test1234",
            "10.0.0.5",
        )
        mock_client_instance.create_service_for_sandbox.return_value = (
            True,
            "agent-test1234-lb-service",
        )
        mock_client_instance.get_loadbalancer_ip.return_value = "192.168.1.100"
        mock_sandbox_client.return_value = mock_client_instance

        # Create deployer
        deployer = SandboxDeployManager()
        deployer.state_manager = mocker.Mock()

        # Mock the image builder to avoid actual Docker operations
        with patch.object(
            deployer.image_factory,
            "build_image",
            return_value="test-image:latest",
        ) as mock_build:
            # Test deployment
            result = await deployer.deploy(
                runner=mock_runner,
                requirements=["fastapi", "uvicorn"],
                base_image="python:3.9-slim",
                port=8090,
            )

            # Assertions
            assert isinstance(result, dict)
            assert "deploy_id" in result
            assert "url" in result
            assert "resource_name" in result

            # Local K8s env → should use fallback_host (127.0.0.1)
            assert result["url"] == "http://127.0.0.1:8090"

            # Verify image build was called
            mock_build.assert_called_once()

            # Verify Sandbox CR was created
            mock_client_instance.create_sandbox.assert_called_once()

            # Verify Service was created for external access
            svc_mock = mock_client_instance.create_service_for_sandbox
            svc_mock.assert_called_once()

            # Verify deployment state was persisted
            deployer.state_manager.save.assert_called_once()

    @patch(
        "agentscope_runtime.engine.deployers.sandbox_deployer.SandboxClient",
    )
    @pytest.mark.asyncio
    async def test_deploy_image_build_failure(
        self,
        mock_sandbox_client,
        mocker,
    ):
        """Test deployment when image build fails."""
        mock_runner = mocker.Mock()

        # Mock SandboxClient
        mock_client_instance = mocker.Mock()
        mock_sandbox_client.return_value = mock_client_instance

        # Create deployer
        deployer = SandboxDeployManager()
        deployer.state_manager = mocker.Mock()

        # Mock the image builder to return None (build failure)
        with patch.object(
            deployer.image_factory,
            "build_image",
            return_value=None,
        ):
            # Test deployment failure
            with pytest.raises(RuntimeError, match="Image build failed"):
                await deployer.deploy(runner=mock_runner)

    @patch(
        "agentscope_runtime.engine.deployers.sandbox_deployer.SandboxClient",
    )
    @pytest.mark.asyncio
    async def test_deploy_sandbox_creation_failure(
        self,
        mock_sandbox_client,
        mocker,
    ):
        """Test deployment when Sandbox CR creation fails."""
        mock_runner = mocker.Mock()

        # Mock SandboxClient failure
        mock_client_instance = mocker.Mock()
        mock_client_instance.create_sandbox.return_value = (
            None,
            None,
        )  # Failure
        mock_sandbox_client.return_value = mock_client_instance

        # Create deployer
        deployer = SandboxDeployManager()
        deployer.state_manager = mocker.Mock()

        # Mock the image builder to return success, but sandbox creation fails
        with patch.object(
            deployer.image_factory,
            "build_image",
            return_value="test-image:latest",
        ):
            # Test deployment failure
            with pytest.raises(
                RuntimeError,
                match="Failed to create resource",
            ):
                await deployer.deploy(runner=mock_runner)

    @patch(
        "agentscope_runtime.engine.deployers.sandbox_deployer.SandboxClient",
    )
    @patch(
        "agentscope_runtime.engine.deployers.sandbox_deployer.isLocalK8sEnvironment",  # noqa E501
        return_value=True,
    )
    @pytest.mark.asyncio
    async def test_deploy_service_creation_failure_fallback(
        self,
        mock_is_local,
        mock_sandbox_client,
        mocker,
    ):
        """Test deployment falls back to sandbox IP when service fails."""
        mock_runner = mocker.Mock()

        mock_client_instance = mocker.Mock()
        mock_client_instance.create_sandbox.return_value = (
            "agent-test",
            "10.0.0.5",
        )
        mock_client_instance.create_service_for_sandbox.return_value = (
            False,
            None,
        )
        mock_sandbox_client.return_value = mock_client_instance

        deployer = SandboxDeployManager()
        deployer.state_manager = mocker.Mock()

        with patch.object(
            deployer.image_factory,
            "build_image",
            return_value="test-image:latest",
        ):
            result = await deployer.deploy(runner=mock_runner, port=8090)

        assert "url" in result
        # Falls back to sandbox IP via get_service_endpoint(sandbox_ip, port)
        # In local env, uses fallback_host
        assert result["url"] == "http://127.0.0.1:8090"
        # get_loadbalancer_ip should NOT be called
        mock_client_instance.get_loadbalancer_ip.assert_not_called()

    @patch(
        "agentscope_runtime.engine.deployers.sandbox_deployer.SandboxClient",
    )
    @patch(
        "agentscope_runtime.engine.deployers.sandbox_deployer.time.sleep",
    )
    @patch(
        "agentscope_runtime.engine.deployers.sandbox_deployer.isLocalK8sEnvironment",  # noqa E501
        return_value=True,
    )
    @pytest.mark.asyncio
    async def test_deploy_with_app_only(
        self,
        mock_is_local,
        mock_sleep,
        mock_sandbox_client,
        mocker,
    ):
        """Test deployment succeeds when only an app is provided."""
        mock_app = mocker.Mock()
        mock_app._runner = mocker.Mock()
        mock_app.stream = False

        mock_client_instance = mocker.Mock()
        mock_client_instance.create_sandbox.return_value = (
            "agent-test",
            "10.0.0.5",
        )
        mock_client_instance.create_service_for_sandbox.return_value = (
            True,
            "agent-test-lb-service",
        )
        mock_client_instance.get_loadbalancer_ip.return_value = "192.168.1.100"
        mock_sandbox_client.return_value = mock_client_instance

        deployer = SandboxDeployManager()
        deployer.state_manager = mocker.Mock()

        with patch.object(
            deployer.image_factory,
            "build_image",
            return_value="app-image:latest",
        ) as mock_build:
            result = await deployer.deploy(app=mock_app)

        assert "url" in result
        mock_build.assert_called_once()

    @patch(
        "agentscope_runtime.engine.deployers.sandbox_deployer.SandboxClient",
    )
    @patch(
        "agentscope_runtime.engine.deployers.sandbox_deployer.time.sleep",
    )
    @patch(
        "agentscope_runtime.engine.deployers.sandbox_deployer.isLocalK8sEnvironment",  # noqa E501
        return_value=True,
    )
    @pytest.mark.asyncio
    async def test_deploy_with_protocol_adapters(
        self,
        mock_is_local,
        mock_sleep,
        mock_sandbox_client,
        mocker,
    ):
        """Test deployment with protocol adapters."""
        mock_runner = mocker.Mock()
        mock_adapters = [mocker.Mock(), mocker.Mock()]

        # Setup mocks
        mock_client_instance = mocker.Mock()
        mock_client_instance.create_sandbox.return_value = (
            "agent-test",
            "10.0.0.5",
        )
        mock_client_instance.create_service_for_sandbox.return_value = (
            True,
            "agent-test-lb-service",
        )
        mock_client_instance.get_loadbalancer_ip.return_value = "192.168.1.100"
        mock_sandbox_client.return_value = mock_client_instance

        deployer = SandboxDeployManager()
        deployer.state_manager = mocker.Mock()

        # Mock the image builder
        with patch.object(
            deployer.image_factory,
            "build_image",
            return_value="test-image:latest",
        ) as mock_build:
            result = await deployer.deploy(
                runner=mock_runner,
                protocol_adapters=mock_adapters,
            )
            assert "deploy_id" in result
            # Verify protocol_adapters were passed to image builder
            call_args = mock_build.call_args
            assert call_args[1]["protocol_adapters"] == mock_adapters

    @patch(
        "agentscope_runtime.engine.deployers.sandbox_deployer.SandboxClient",
    )
    @patch(
        "agentscope_runtime.engine.deployers.sandbox_deployer.time.sleep",
    )
    @patch(
        "agentscope_runtime.engine.deployers.sandbox_deployer.isLocalK8sEnvironment",  # noqa E501
        return_value=True,
    )
    @pytest.mark.asyncio
    async def test_deploy_with_volume_mount(
        self,
        mock_is_local,
        mock_sleep,
        mock_sandbox_client,
        mocker,
    ):
        """Test deployment with volume mounting."""
        mock_runner = mocker.Mock()

        # Setup mocks
        mock_client_instance = mocker.Mock()
        mock_client_instance.create_sandbox.return_value = (
            "agent-test",
            "10.0.0.5",
        )
        mock_client_instance.create_service_for_sandbox.return_value = (
            True,
            "agent-test-lb-service",
        )
        mock_client_instance.get_loadbalancer_ip.return_value = "192.168.1.100"
        mock_sandbox_client.return_value = mock_client_instance

        deployer = SandboxDeployManager()
        deployer.state_manager = mocker.Mock()

        # Mock the image builder
        with patch.object(
            deployer.image_factory,
            "build_image",
            return_value="test-image:latest",
        ):
            result = await deployer.deploy(
                runner=mock_runner,
                mount_dir="/data",
            )
            assert "deploy_id" in result
            # Verify volume mounting configuration was passed
            call_args = mock_client_instance.create_sandbox.call_args
            volumes_arg = call_args[1]["volumes"]
            expected_volumes = {
                "/data": {
                    "bind": "/data",
                    "mode": "rw",
                },
            }
            assert volumes_arg == expected_volumes

    @patch(
        "agentscope_runtime.engine.deployers.sandbox_deployer.SandboxClient",
    )
    @pytest.mark.asyncio
    async def test_deploy_validation_error(self, mock_sandbox_client):
        """Test deployment with invalid parameters."""
        deployer = SandboxDeployManager()

        # Test with neither runner nor app
        with pytest.raises(
            RuntimeError,
            match="Sandbox deployment failed",
        ):
            await deployer.deploy(runner=None, func=None)

    @patch(
        "agentscope_runtime.engine.deployers.sandbox_deployer.SandboxClient",
    )
    @pytest.mark.asyncio
    async def test_stop_sandbox(self, mock_sandbox_client, mocker):
        """Test stopping a sandbox deployment."""
        # Setup deployer with a mock sandbox
        mock_client_instance = mocker.Mock()
        mock_client_instance.delete_service_for_sandbox.return_value = True
        mock_client_instance.delete_sandbox.return_value = True
        mock_sandbox_client.return_value = mock_client_instance

        deployer = SandboxDeployManager()
        deployer.deploy_id = "test-deploy-123"
        deployer.state_manager = mocker.Mock()

        result = await deployer.stop("test-deploy-123")

        assert result["success"] is True
        # Verify service was deleted first
        del_svc = mock_client_instance.delete_service_for_sandbox
        del_svc.assert_called_once_with(
            "agent-test-dep",
        )
        # Verify sandbox CR was deleted
        mock_client_instance.delete_sandbox.assert_called_once_with(
            "agent-test-dep",
        )
        # Verify state was updated
        deployer.state_manager.update_status.assert_called_once_with(
            "test-deploy-123",
            "stopped",
        )

    @patch(
        "agentscope_runtime.engine.deployers.sandbox_deployer.SandboxClient",
    )
    @pytest.mark.asyncio
    async def test_stop_nonexistent_sandbox(
        self,
        mock_sandbox_client,
        mocker,
    ):
        """Test stopping a nonexistent sandbox."""
        mock_client_instance = mocker.Mock()
        mock_client_instance.delete_service_for_sandbox.return_value = True
        mock_client_instance.delete_sandbox.return_value = False
        mock_sandbox_client.return_value = mock_client_instance

        deployer = SandboxDeployManager()
        deployer.state_manager = mocker.Mock()
        deploy_id = "nonexistent-deploy"

        result = await deployer.stop(deploy_id)

        assert result["success"] is False

    @patch(
        "agentscope_runtime.engine.deployers.sandbox_deployer.SandboxClient",
    )
    @pytest.mark.asyncio
    async def test_stop_with_exception(self, mock_sandbox_client, mocker):
        """Test stopping when an exception occurs."""
        mock_client_instance = mocker.Mock()
        mock_client_instance.delete_service_for_sandbox.side_effect = (
            RuntimeError("Connection refused")
        )
        mock_sandbox_client.return_value = mock_client_instance

        deployer = SandboxDeployManager()
        deployer.state_manager = mocker.Mock()

        result = await deployer.stop("some-deploy-id")

        assert result["success"] is False
        assert "error" in result["details"]

    @patch(
        "agentscope_runtime.engine.deployers.sandbox_deployer.SandboxClient",
    )
    def test_get_status(self, mock_sandbox_client, mocker):
        """Test getting sandbox status."""
        mock_client_instance = mocker.Mock()
        mock_client_instance.get_sandbox_status.return_value = {
            "name": "agent-test-depl",
            "phase": "Running",
        }
        mock_sandbox_client.return_value = mock_client_instance

        deployer = SandboxDeployManager()
        deployer.deploy_id = "test-deploy-123"

        # Mock state_manager to return a deployment with config
        mock_deployment = mocker.Mock()
        mock_deployment.config = {"service_name": "agent-test-depl"}
        deployer.state_manager = mocker.Mock()
        deployer.state_manager.get.return_value = mock_deployment

        status = deployer.get_status()

        assert status == {"name": "agent-test-depl", "phase": "Running"}
        mock_client_instance.get_sandbox_status.assert_called_once_with(
            "agent-test-depl",
        )

    @patch(
        "agentscope_runtime.engine.deployers.sandbox_deployer.SandboxClient",
    )
    def test_get_status_not_found(self, mock_sandbox_client, mocker):
        """Test getting status of nonexistent deployment."""
        deployer = SandboxDeployManager()
        deployer.deploy_id = "nonexistent-deploy"

        deployer.state_manager = mocker.Mock()
        deployer.state_manager.get.return_value = None

        status = deployer.get_status()

        assert status == "not_found"

    @patch(
        "agentscope_runtime.engine.deployers.sandbox_deployer.SandboxClient",
    )
    def test_get_status_no_service_name(self, mock_sandbox_client, mocker):
        """Test getting status when config has no service_name."""
        deployer = SandboxDeployManager()
        deployer.deploy_id = "test-deploy-123"

        mock_deployment = mocker.Mock()
        mock_deployment.config = {}
        deployer.state_manager = mocker.Mock()
        deployer.state_manager.get.return_value = mock_deployment

        status = deployer.get_status()

        assert status == "unknown"

    @pytest.mark.asyncio
    async def test_minimal_functionality_without_heavy_mocking(self):
        """Test basic functionality with minimal mocking."""
        k8s_config = K8sConfig(k8s_namespace="test-namespace")
        registry_config = RegistryConfig()

        # Mock just the SandboxClient constructor
        with patch(
            "agentscope_runtime.engine.deployers.sandbox_deployer.SandboxClient",  # noqa E501
        ):
            deployer = SandboxDeployManager(
                kube_config=k8s_config,
                registry_config=registry_config,
                build_context_dir="/tmp/test-build",
            )

            # Test basic properties
            assert deployer.kubeconfig == k8s_config
            assert deployer.registry_config == registry_config
            assert deployer.build_context_dir == "/tmp/test-build"
            assert deployer._built_images == {}

            # Test deploy_id generation (inherited from DeployManager)
            assert deployer.deploy_id is not None
            assert isinstance(deployer.deploy_id, str)

            # Test image builder initialization
            assert deployer.image_factory is not None

            # Test validation error handling
            with pytest.raises(
                RuntimeError,
                match="Sandbox deployment failed",
            ):
                await deployer.deploy(runner=None, func=None)

    def test_get_resource_name(self):
        """Test resource name generation from deploy_id."""
        assert (
            SandboxDeployManager.get_resource_name("abcdef12-3456-7890")
            == "agent-abcdef12"
        )
        assert (
            SandboxDeployManager.get_resource_name("12345678")
            == "agent-12345678"
        )

    @patch(
        "agentscope_runtime.engine.deployers.sandbox_deployer.isLocalK8sEnvironment",  # noqa E501
        return_value=True,
    )
    def test_get_service_endpoint_local(self, mock_is_local):
        """Test service endpoint generation in local environment."""
        url = SandboxDeployManager.get_service_endpoint(
            "10.0.0.100",
            [8090],
        )
        assert url == "http://127.0.0.1:8090"

    @patch(
        "agentscope_runtime.engine.deployers.sandbox_deployer.isLocalK8sEnvironment",  # noqa E501
        return_value=False,
    )
    def test_get_service_endpoint_cloud(self, mock_is_local):
        """Test service endpoint generation in cloud environment."""
        url = SandboxDeployManager.get_service_endpoint(
            "10.0.0.100",
            [8090],
        )
        assert url == "http://10.0.0.100:8090"

    @patch(
        "agentscope_runtime.engine.deployers.sandbox_deployer.isLocalK8sEnvironment",  # noqa E501
        return_value=True,
    )
    def test_get_service_endpoint_fallback(self, mock_is_local):
        """Test service endpoint fallback when no IP/port provided."""
        url = SandboxDeployManager.get_service_endpoint(None, None)
        assert url == "http://127.0.0.1:8080"

    @patch(
        "agentscope_runtime.engine.deployers.sandbox_deployer.isLocalK8sEnvironment",  # noqa E501
        return_value=False,
    )
    def test_get_service_endpoint_int_port(self, mock_is_local):
        """Test service endpoint with integer port (not list)."""
        url = SandboxDeployManager.get_service_endpoint("1.2.3.4", 9090)
        assert url == "http://1.2.3.4:9090"

    @patch(
        "agentscope_runtime.engine.deployers.sandbox_deployer.isLocalK8sEnvironment",  # noqa E501
        return_value=False,
    )
    def test_get_service_endpoint_list_port_picks_first(self, mock_is_local):
        """Test service endpoint picks first port from list."""
        url = SandboxDeployManager.get_service_endpoint(
            "1.2.3.4",
            [8080, 8090],
        )
        assert url == "http://1.2.3.4:8080"
