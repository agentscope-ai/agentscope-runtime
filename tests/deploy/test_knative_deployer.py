# -*- coding: utf-8 -*-
# pylint:disable=protected-access, unused-argument
# pylint:disable=use-implicit-booleaness-not-comparison


import os
import shutil
import tempfile
from unittest.mock import patch

import pytest

from agentscope_runtime.engine.deployers.knative_deployer import (
    KnativeDeployManager,
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
        assert config.build_context_dir == "/tmp/k8s_build"
        assert config.dockerfile_template is None
        assert config.build_timeout == 600
        assert config.push_timeout == 300
        assert config.cleanup_after_build is True


class TestKnativeDeployManager:
    """Test cases for KnativeDeployManager class."""

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """Set up and tear down test environment."""
        self.temp_dir = tempfile.mkdtemp()
        yield
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    @patch(
        "agentscope_runtime.engine.deployers.knative_deployer.KnativeClient",  # noqa E501
    )
    def test_knative_deployer_creation(self, mock_k8s_client):
        """Test KnativeDeployManager creation."""
        k8s_config = K8sConfig()
        registry_config = RegistryConfig()

        deployer = KnativeDeployManager(
            kube_config=k8s_config,
            registry_config=registry_config,
        )

        assert deployer.kubeconfig == k8s_config
        assert deployer.registry_config == registry_config
        assert deployer.build_context_dir == "/tmp/k8s_build"

        # Verify that KubernetesClient was instantiated with correct parameters
        mock_k8s_client.assert_called_once_with(
            config=k8s_config,
            image_registry=registry_config.get_full_url(),
        )

    @patch(
        "agentscope_runtime.engine.deployers.knative_deployer.KnativeClient",  # noqa E501
    )
    @pytest.mark.asyncio
    async def test_deploy_kservice_with_runner_success(
        self,
        mock_k8s_client,
        mocker,
    ):
        """Test successful kservice with runner."""
        # Setup mocks
        mock_runner = mocker.Mock()
        mock_runner._agent = mocker.Mock()
        mock_runner.__class__.__name__ = "MockRunner"

        # Mock Kubernetes client
        mock_client_instance = mocker.Mock()
        mock_client_instance.create_kservice.return_value = (
            "agent-test",
            "http://agent-291cb894.agentscope-runtime.example.com",
        )
        mock_k8s_client.return_value = mock_client_instance

        # Create deployer
        deployer = KnativeDeployManager()

        # Mock the image builder to avoid actual Docker operations
        with patch.object(
            deployer.image_factory,
            "build_image",
            return_value="test-image:latest",
        ) as mock_build:
            # Test kservice
            result = await deployer.deploy(
                runner=mock_runner,
                requirements=["fastapi", "uvicorn"],
                base_image="python:3.9-slim",
                port=8080,
            )

            # Assertions
            assert isinstance(result, dict)
            assert "deploy_id" in result
            assert "url" in result
            assert "resource_name" in result

            assert (
                result["url"]
                == "http://agent-291cb894.agentscope-runtime.example.com"
            )

            # Verify image build was called
            mock_build.assert_called_once()

            # Verify Knative service was called
            mock_client_instance.create_kservice.assert_called_once()

    @patch(
        "agentscope_runtime.engine.deployers.knative_deployer.KnativeClient",  # noqa E501
    )
    @pytest.mark.asyncio
    async def test_deploy_image_build_failure(self, mock_k8s_client, mocker):
        """Test kservice when image build fails."""
        mock_runner = mocker.Mock()

        # Mock Kubernetes client
        mock_client_instance = mocker.Mock()
        mock_k8s_client.return_value = mock_client_instance

        # Create deployer
        deployer = KnativeDeployManager()

        # Mock the image builder to return None (build failure)
        with patch.object(
            deployer.image_factory,
            "build_image",
            return_value=None,
        ):
            # Test kservice failure
            with pytest.raises(RuntimeError, match="Image build failed"):
                await deployer.deploy(runner=mock_runner)

    @patch(
        "agentscope_runtime.engine.deployers.knative_deployer.KnativeClient",  # noqa E501
    )
    @pytest.mark.asyncio
    async def test_deploy_knative_service_failure(
        self,
        mock_k8s_client,
        mocker,
    ):
        """Test kservice when Knative service fails."""
        mock_runner = mocker.Mock()

        # Mock Kubernetes client failure
        mock_client_instance = mocker.Mock()
        mock_client_instance.create_kservice.return_value = (
            None,
            None,
        )  # Failure
        mock_k8s_client.return_value = mock_client_instance

        # Create deployer
        deployer = KnativeDeployManager()

        # Mock the image builder to return success, but knative service fails
        with patch.object(
            deployer.image_factory,
            "build_image",
            return_value="test-image:latest",
        ):
            # Test kservice failure
            with pytest.raises(
                RuntimeError,
                match="Failed to create resource",
            ):
                await deployer.deploy(runner=mock_runner)

    @patch(
        "agentscope_runtime.engine.deployers.knative_deployer.KnativeClient",  # noqa E501
    )
    @pytest.mark.asyncio
    async def test_deploy_kservice_with_app_only(
        self,
        mock_k8s_client,
        mocker,
    ):
        """Test kservice succeeds when only an app is provided."""
        mock_app = mocker.Mock()
        mock_app._runner = mocker.Mock()
        mock_app.stream = False

        mock_client_instance = mocker.Mock()
        mock_client_instance.create_kservice.return_value = (
            "agent-test",
            "http://agent-291cb894.agentscope-runtime.example.com",
        )
        mock_k8s_client.return_value = mock_client_instance

        deployer = KnativeDeployManager()

        with patch.object(
            deployer.image_factory,
            "build_image",
            return_value="app-image:latest",
        ) as mock_build:
            result = await deployer.deploy(app=mock_app, replicas=1)

        assert "url" in result
        mock_build.assert_called_once()

    @patch(
        "agentscope_runtime.engine.deployers.knative_deployer.KnativeClient",  # noqa E501
    )
    @pytest.mark.asyncio
    async def test_deploy_with_protocol_adapters(
        self,
        mock_k8s_client,
        mocker,
    ):
        """Test kservice with protocol adapters."""
        mock_runner = mocker.Mock()
        mock_adapters = [mocker.Mock(), mocker.Mock()]

        # Setup mocks
        mock_client_instance = mocker.Mock()
        mock_client_instance.create_kservice.return_value = (
            "agent-test",
            "http://agent-291cb894.agentscope-runtime.example.com",
        )
        mock_k8s_client.return_value = mock_client_instance

        deployer = KnativeDeployManager()

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
        "agentscope_runtime.engine.deployers.knative_deployer.KnativeClient",  # noqa E501
    )
    @pytest.mark.asyncio
    async def test_deploy_kservice_with_volume_mount(
        self,
        mock_k8s_client,
        mocker,
    ):
        """Test kservice with volume mounting."""
        mock_runner = mocker.Mock()

        # Setup mocks
        mock_client_instance = mocker.Mock()
        mock_client_instance.create_kservice.return_value = (
            "agent-test",
            "http://agent-291cb894.agentscope-runtime.example.com",
        )
        mock_k8s_client.return_value = mock_client_instance

        deployer = KnativeDeployManager()

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
            call_args = mock_client_instance.create_kservice.call_args
            volumes_arg = call_args[1]["volumes"]
            expected_volumes = {
                "/data": {
                    "bind": "/data",
                    "mode": "rw",
                },
            }
            assert volumes_arg == expected_volumes

    @patch(
        "agentscope_runtime.engine.deployers.knative_deployer.KnativeClient",  # noqa E501
    )
    @pytest.mark.asyncio
    async def test_deploy_validation_error(self, mock_k8s_client):
        """Test kservice with invalid parameters."""
        deployer = KnativeDeployManager()

        # Test with neither runner nor func
        with pytest.raises(RuntimeError, match="Knative Service failed"):
            await deployer.deploy(runner=None, func=None)

    @patch(
        "agentscope_runtime.engine.deployers.knative_deployer.KnativeClient",  # noqa E501
    )
    @pytest.mark.asyncio
    async def test_stop_kservice(self, mock_k8s_client, mocker):
        """Test stopping a kservice."""
        # Setup deployer with a mock kservice
        mock_client_instance = mocker.Mock()
        mock_client_instance.delete_kservice.return_value = True
        mock_k8s_client.return_value = mock_client_instance

        deployer = KnativeDeployManager()
        deployer.deploy_id = "test-deploy-123"

        result = await deployer.stop("test-deploy-123")

        assert result["success"] is True
        mock_client_instance.delete_kservice.assert_called_once_with(
            "agent-test-dep",
        )

    @patch(
        "agentscope_runtime.engine.deployers.knative_deployer.KnativeClient",  # noqa E501
    )
    @pytest.mark.asyncio
    async def test_stop_nonexistent_kservice(self, mock_k8s_client, mocker):
        """Test stopping a nonexistent kservice."""
        mock_client_instance = mocker.Mock()

        mock_client_instance.delete_kservice.return_value = False
        mock_k8s_client.return_value = mock_client_instance

        deployer = KnativeDeployManager()
        deploy_id = "nonexistent-deploy"

        result = await deployer.stop(deploy_id)

        assert result["success"] is False

    @patch(
        "agentscope_runtime.engine.deployers.knative_deployer.KnativeClient",  # noqa E501
    )
    def test_get_status(self, mock_k8s_client, mocker):
        """Test getting kservice status."""
        mock_client_instance = mocker.Mock()
        mock_client_instance.get_kservice_status.return_value = "running"
        mock_k8s_client.return_value = mock_client_instance

        deployer = KnativeDeployManager()
        deployer.deploy_id = "test-deploy-123"
        deployer._deployed_resources["test-deploy-123"] = {
            "resource_name": "agent-test-depl",
        }

        status = deployer.get_status()

        assert status == "running"
        mock_client_instance.get_kservice_status.assert_called_once_with(
            "agent-test-depl",
        )

    @patch(
        "agentscope_runtime.engine.deployers.knative_deployer.KnativeClient",  # noqa E501
    )
    def test_get_status_nonexistent(self, mock_k8s_client):
        """Test getting status of nonexistent kservice."""
        deployer = KnativeDeployManager()
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
            "agentscope_runtime.engine.deployers.knative_deployer.KnativeClient",  # noqa E501
        ):
            deployer = KnativeDeployManager(
                kube_config=k8s_config,
                registry_config=registry_config,
                build_context_dir="/tmp/test-build",
            )

            # Test basic properties
            assert deployer.kubeconfig == k8s_config
            assert deployer.registry_config == registry_config
            assert deployer.build_context_dir == "/tmp/test-build"
            assert deployer._deployed_resources == {}
            assert deployer._built_images == {}

            # Test deploy_id generation (inherited from DeployManager)
            assert deployer.deploy_id is not None
            assert isinstance(deployer.deploy_id, str)

            # Test image builder initialization
            assert deployer.image_factory is not None

            # Test validation error handling
            with pytest.raises(RuntimeError, match="Knative Service failed"):
                await deployer.deploy(runner=None, func=None)
