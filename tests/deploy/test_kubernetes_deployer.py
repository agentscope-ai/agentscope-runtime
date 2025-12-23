# -*- coding: utf-8 -*-
# pylint:disable=protected-access, unused-argument
# pylint:disable=use-implicit-booleaness-not-comparison


import os
import shutil
import tempfile
from unittest.mock import patch

import pytest
from kubernetes.client.exceptions import ApiException

from agentscope_runtime.engine.deployers.kubernetes_deployer import (
    KubernetesDeployManager,
    K8sConfig,
    BuildConfig,
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


class TestBuildConfigK8s:
    """Test cases for BuildConfig model."""

    def test_build_config_defaults(self):
        """Test BuildConfig default values."""
        config = BuildConfig()
        assert config.build_context_dir is None
        assert config.dockerfile_template is None
        assert config.build_timeout == 600
        assert config.push_timeout == 300
        assert config.cleanup_after_build is True


class TestKubernetesDeployManager:
    """Test cases for KubernetesDeployManager class."""

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """Set up and tear down test environment."""
        self.temp_dir = tempfile.mkdtemp()
        yield
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    @patch(
        "agentscope_runtime.engine.deployers.kubernetes_deployer.KubernetesClient",  # noqa E501
    )
    def test_kubernetes_deployer_creation(self, mock_k8s_client):
        """Test KubernetesDeployManager creation."""
        k8s_config = K8sConfig()
        registry_config = RegistryConfig()

        deployer = KubernetesDeployManager(
            kube_config=k8s_config,
            registry_config=registry_config,
        )

        assert deployer.kubeconfig == k8s_config
        assert deployer.registry_config == registry_config
        assert deployer.use_deployment is True
        assert deployer.build_context_dir is None

        # Verify that KubernetesClient was instantiated with correct parameters
        mock_k8s_client.assert_called_once_with(
            config=k8s_config,
            image_registry=registry_config.get_full_url(),
        )

    @patch(
        "agentscope_runtime.engine.deployers.kubernetes_deployer.KubernetesClient",  # noqa E501
    )
    @pytest.mark.asyncio
    async def test_deploy_with_runner_success(self, mock_k8s_client, mocker):
        """Test successful deployment with runner."""
        # Setup mocks
        mock_runner = mocker.Mock()
        mock_runner._agent = mocker.Mock()
        mock_runner.__class__.__name__ = "MockRunner"

        # Mock Kubernetes client
        mock_client_instance = mocker.Mock()
        mock_client_instance.create_deployment.return_value = (
            "service-id",
            [8090],
            "127.0.0.1",
        )
        mock_k8s_client.return_value = mock_client_instance

        # Create deployer
        deployer = KubernetesDeployManager()

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
                replicas=2,
            )

            # Assertions
            assert isinstance(result, dict)
            assert "deploy_id" in result
            assert "url" in result
            assert "resource_name" in result
            assert "replicas" in result

            assert result["url"] == "http://127.0.0.1:8090"
            assert result["replicas"] == 2

            # Verify image build was called
            mock_build.assert_called_once()

            # Verify Kubernetes deployment was called
            mock_client_instance.create_deployment.assert_called_once()

    @patch(
        "agentscope_runtime.engine.deployers.kubernetes_deployer.KubernetesClient",  # noqa E501
    )
    @pytest.mark.asyncio
    async def test_deploy_image_build_failure(self, mock_k8s_client, mocker):
        """Test deployment when image build fails."""
        mock_runner = mocker.Mock()

        # Mock Kubernetes client
        mock_client_instance = mocker.Mock()
        mock_k8s_client.return_value = mock_client_instance

        # Create deployer
        deployer = KubernetesDeployManager()

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
        "agentscope_runtime.engine.deployers.kubernetes_deployer.KubernetesClient",  # noqa E501
    )
    @pytest.mark.asyncio
    async def test_deploy_k8s_deployment_failure(
        self,
        mock_k8s_client,
        mocker,
    ):
        """Test deployment when Kubernetes deployment fails."""
        mock_runner = mocker.Mock()

        # Mock Kubernetes client failure
        mock_client_instance = mocker.Mock()
        mock_client_instance.create_deployment.return_value = (
            None,
            [],
            None,
        )  # Failure
        mock_k8s_client.return_value = mock_client_instance

        # Create deployer
        deployer = KubernetesDeployManager()

        # Mock the image builder to return success, but k8s deployment fails
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
        "agentscope_runtime.engine.deployers.kubernetes_deployer.KubernetesClient",  # noqa E501
    )
    @pytest.mark.asyncio
    async def test_deploy_with_app_only(self, mock_k8s_client, mocker):
        """Test deployment succeeds when only an app is provided."""
        mock_app = mocker.Mock()
        mock_app._runner = mocker.Mock()
        mock_app.endpoint_path = "/custom"
        mock_app.stream = False

        mock_client_instance = mocker.Mock()
        mock_client_instance.create_deployment.return_value = (
            "service-id",
            [8090],
            "10.0.0.1",
        )
        mock_k8s_client.return_value = mock_client_instance

        deployer = KubernetesDeployManager()

        with patch.object(
            deployer.image_factory,
            "build_image",
            return_value="app-image:latest",
        ) as mock_build:
            result = await deployer.deploy(app=mock_app, replicas=1)

        assert "url" in result
        mock_build.assert_called_once()

    @patch(
        "agentscope_runtime.engine.deployers.kubernetes_deployer.KubernetesClient",  # noqa E501
    )
    @pytest.mark.asyncio
    async def test_deploy_with_protocol_adapters(
        self,
        mock_k8s_client,
        mocker,
    ):
        """Test deployment with protocol adapters."""
        mock_runner = mocker.Mock()
        mock_adapters = [mocker.Mock(), mocker.Mock()]

        # Setup mocks
        mock_client_instance = mocker.Mock()
        mock_client_instance.create_deployment.return_value = (
            "service-id",
            [8090],
            "10.0.0.1",
        )
        mock_k8s_client.return_value = mock_client_instance

        deployer = KubernetesDeployManager()

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
        "agentscope_runtime.engine.deployers.kubernetes_deployer.KubernetesClient",  # noqa E501
    )
    @pytest.mark.asyncio
    async def test_deploy_with_volume_mount(self, mock_k8s_client, mocker):
        """Test deployment with volume mounting."""
        mock_runner = mocker.Mock()

        # Setup mocks
        mock_client_instance = mocker.Mock()
        mock_client_instance.create_deployment.return_value = (
            "service-id",
            [8090],
            "10.0.0.1",
        )
        mock_k8s_client.return_value = mock_client_instance

        deployer = KubernetesDeployManager()

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
            call_args = mock_client_instance.create_deployment.call_args
            volumes_arg = call_args[1]["volumes"]
            expected_volumes = {
                "/data": {
                    "bind": "/data",
                    "mode": "rw",
                },
            }
            assert volumes_arg == expected_volumes

    @patch(
        "agentscope_runtime.engine.deployers.kubernetes_deployer.KubernetesClient",  # noqa E501
    )
    @pytest.mark.asyncio
    async def test_deploy_validation_error(self, mock_k8s_client):
        """Test deployment with invalid parameters."""
        deployer = KubernetesDeployManager()

        # Test with neither runner nor func
        with pytest.raises(RuntimeError, match="Deployment failed"):
            await deployer.deploy(runner=None, func=None)

    @patch(
        "agentscope_runtime.engine.deployers.kubernetes_deployer.KubernetesClient",  # noqa E501
    )
    @pytest.mark.asyncio
    async def test_stop_deployment(self, mock_k8s_client, mocker):
        """Test stopping a deployment."""
        # Setup deployer with a mock deployment
        mock_client_instance = mocker.Mock()
        mock_client_instance.remove_deployment.return_value = True
        mock_k8s_client.return_value = mock_client_instance

        deployer = KubernetesDeployManager()
        deployer.deploy_id = "test-deploy-123"

        result = await deployer.stop("test-deploy-123")

        assert result["success"] is True
        mock_client_instance.remove_deployment.assert_called_once_with(
            "agent-test-dep",
        )

    @patch(
        "agentscope_runtime.engine.deployers.kubernetes_deployer.KubernetesClient",  # noqa E501
    )
    @pytest.mark.asyncio
    async def test_stop_nonexistent_deployment_raises(
        self,
        mock_k8s_client,
        mocker,
    ):
        """Test stopping a nonexistent deployment raises appropriate
        exception."""
        mock_client_instance = mocker.Mock()

        # Make remove_deployment raise ApiException (e.g., 404 Not Found)
        mock_client_instance.remove_deployment.side_effect = ApiException(
            status=404,
            reason="Not Found",
            http_resp=mocker.Mock(
                status=404,
                data='{"message": "Deployment not found"}',
            ),
        )
        mock_k8s_client.return_value = mock_client_instance

        deployer = KubernetesDeployManager()
        deploy_id = "nonexistent-deploy"

        # Option 1: If `deployer.stop()` is expected to catch & return {
        # "success": False}
        result = await deployer.stop(deploy_id)
        assert result["success"] is False

    @patch(
        "agentscope_runtime.engine.deployers.kubernetes_deployer.KubernetesClient",  # noqa E501
    )
    def test_get_status(self, mock_k8s_client, mocker):
        """Test getting deployment status."""

        deployer = KubernetesDeployManager()
        deployer.deploy_id = "test-deploy-123"

        status = deployer.get_status()

        assert status == "not_found"

    @patch(
        "agentscope_runtime.engine.deployers.kubernetes_deployer.KubernetesClient",  # noqa E501
    )
    def test_get_status_nonexistent(self, mock_k8s_client):
        """Test getting status of nonexistent deployment."""
        deployer = KubernetesDeployManager()
        deployer.deploy_id = "nonexistent-deploy"

        status = deployer.get_status()

        assert status == "not_found"

    @pytest.mark.asyncio
    async def test_minimal_functionality_without_heavy_mocking(self):
        """Test basic functionality with minimal mocking."""
        k8s_config = K8sConfig(k8s_namespace="test-namespace")
        registry_config = RegistryConfig()

        # Mock just the KubernetesClient constructor
        with patch(
            "agentscope_runtime.engine.deployers.kubernetes_deployer.KubernetesClient",  # noqa E501
        ):
            deployer = KubernetesDeployManager(
                kube_config=k8s_config,
                registry_config=registry_config,
                build_context_dir="/tmp/test-build",
            )

            # Test basic properties
            assert deployer.kubeconfig == k8s_config
            assert deployer.registry_config == registry_config
            assert deployer.use_deployment is True
            assert deployer.build_context_dir == "/tmp/test-build"
            assert deployer._built_images == {}

            # Test deploy_id generation (inherited from DeployManager)
            assert deployer.deploy_id is not None
            assert isinstance(deployer.deploy_id, str)

            # Test image builder initialization
            assert deployer.image_factory is not None

            # Test validation error handling
            with pytest.raises(RuntimeError, match="Deployment failed"):
                await deployer.deploy(runner=None, func=None)
