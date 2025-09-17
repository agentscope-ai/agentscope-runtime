# -*- coding: utf-8 -*-
"""Unit tests for LocalDeployManager using pytest."""

import pytest
import asyncio
import tempfile
import shutil
import os
import threading
import time
from unittest.mock import patch, Mock, MagicMock, AsyncMock

from agentscope_runtime.engine.deployers.local_deployer import (
    LocalDeployManager,
)
from agentscope_runtime.engine.deployers.utils.deployment_modes import (
    DeploymentMode,
)
from agentscope_runtime.engine.deployers.utils.service_utils import (
    ServicesConfig,
)


class TestLocalDeployManager:
    """Test cases for LocalDeployManager class."""

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """Set up and tear down test environment."""
        self.temp_dir = tempfile.mkdtemp()
        yield
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_local_deploy_manager_creation(self):
        """Test LocalDeployManager creation."""
        manager = LocalDeployManager()

        assert manager.host == "127.0.0.1"
        assert manager.port == 8000
        assert manager.is_running is False
        assert manager._server is None
        assert manager._server_thread is None
        assert manager._detached_process_pid is None

    def test_local_deploy_manager_custom_config(self):
        """Test LocalDeployManager creation with custom config."""
        manager = LocalDeployManager(
            host="0.0.0.0",
            port=9000,
            shutdown_timeout=60,
        )

        assert manager.host == "0.0.0.0"
        assert manager.port == 9000
        assert manager._shutdown_timeout == 60

    @patch(
        "agentscope_runtime.engine.deployers.local_deployer.FastAPIAppFactory"
    )
    @patch("uvicorn.Server")
    @pytest.mark.asyncio
    async def test_deploy_daemon_thread_mode(
        self, mock_server_class, mock_app_factory
    ):
        """Test deployment in daemon thread mode."""
        # Setup mocks
        mock_app = Mock()
        mock_app_factory.create_app.return_value = mock_app

        mock_server_instance = Mock()
        mock_server_class.return_value = mock_server_instance

        mock_runner = Mock()

        manager = LocalDeployManager()

        # Mock the server readiness check
        with patch.object(
            manager, "_wait_for_server_ready", new_callable=AsyncMock
        ):
            result = await manager.deploy(
                runner=mock_runner,
                mode=DeploymentMode.DAEMON_THREAD,
            )

        # Assertions
        assert isinstance(result, dict)
        assert "deploy_id" in result
        assert "url" in result
        assert result["url"] == "http://127.0.0.1:8000"
        assert manager.is_running is True

        # Verify FastAPI app was created
        mock_app_factory.create_app.assert_called_once()

        # Verify uvicorn server was created
        mock_server_class.assert_called_once()

    @patch(
        "agentscope_runtime.engine.deployers.local_deployer.package_project"
    )
    @pytest.mark.asyncio
    async def test_deploy_detached_process_mode(self, mock_package_project):
        """Test deployment in detached process mode."""
        # Setup mocks
        mock_agent = Mock()
        mock_runner = Mock()
        mock_runner._agent = mock_agent

        mock_package_project.return_value = (self.temp_dir, True)

        # Create a mock main.py file
        main_py_path = os.path.join(self.temp_dir, "main.py")
        with open(main_py_path, "w") as f:
            f.write("# Mock main.py\nprint('Hello')")

        manager = LocalDeployManager()

        # Mock process manager methods
        with patch.object(
            manager.process_manager,
            "start_detached_process",
            new_callable=AsyncMock,
        ) as mock_start, patch.object(
            manager.process_manager, "wait_for_port", new_callable=AsyncMock
        ) as mock_wait, patch.object(
            manager.process_manager, "create_pid_file"
        ) as mock_create_pid:
            mock_start.return_value = 12345
            mock_wait.return_value = True

            result = await manager.deploy(
                runner=mock_runner,
                mode=DeploymentMode.DETACHED_PROCESS,
            )

        # Assertions
        assert isinstance(result, dict)
        assert "deploy_id" in result
        assert "url" in result
        assert result["url"] == "http://127.0.0.1:8000"
        assert manager.is_running is True
        assert manager._detached_process_pid == 12345

        # Verify process was started
        mock_start.assert_called_once()
        mock_wait.assert_called_once()
        mock_create_pid.assert_called_once()

    @pytest.mark.asyncio
    async def test_deploy_detached_process_no_agent(self):
        """Test detached process deployment without agent."""
        mock_runner = Mock()
        mock_runner._agent = None

        manager = LocalDeployManager()

        with pytest.raises(
            ValueError, match="requires a runner with an agent"
        ):
            await manager.deploy(
                runner=mock_runner,
                mode=DeploymentMode.DETACHED_PROCESS,
            )

    @pytest.mark.asyncio
    async def test_deploy_unsupported_mode(self):
        """Test deployment with unsupported mode."""
        manager = LocalDeployManager()

        with pytest.raises(ValueError, match="Unsupported deployment mode"):
            await manager.deploy(mode="unsupported_mode")

    @pytest.mark.asyncio
    async def test_deploy_already_running(self):
        """Test deployment when service is already running."""
        manager = LocalDeployManager()
        manager.is_running = True

        with pytest.raises(RuntimeError, match="Service is already running"):
            await manager.deploy()

    @patch(
        "agentscope_runtime.engine.deployers.local_deployer.FastAPIAppFactory"
    )
    @patch("uvicorn.Server")
    @pytest.mark.asyncio
    async def test_deploy_with_custom_config(
        self, mock_server_class, mock_app_factory
    ):
        """Test deployment with custom configuration."""
        mock_app = Mock()
        mock_app_factory.create_app.return_value = mock_app

        mock_server_instance = Mock()
        mock_server_class.return_value = mock_server_instance

        mock_runner = Mock()
        services_config = ServicesConfig()

        manager = LocalDeployManager()

        with patch.object(
            manager, "_wait_for_server_ready", new_callable=AsyncMock
        ):
            result = await manager.deploy(
                runner=mock_runner,
                endpoint_path="/api/process",
                response_type="json",
                stream=False,
                services_config=services_config,
                mode=DeploymentMode.DAEMON_THREAD,
            )

        # Verify configuration was passed to FastAPI factory
        call_args = mock_app_factory.create_app.call_args
        assert call_args[1]["endpoint_path"] == "/api/process"
        assert call_args[1]["response_type"] == "json"
        assert call_args[1]["stream"] is False
        assert call_args[1]["services_config"] == services_config

    @patch("agentscope_runtime.engine.deployers.local_deployer.PackageConfig")
    @patch(
        "agentscope_runtime.engine.deployers.local_deployer.package_project"
    )
    @pytest.mark.asyncio
    async def test_create_detached_project(
        self, mock_package_project, mock_package_config
    ):
        """Test creating detached project."""
        mock_agent = Mock()
        mock_runner = Mock()
        mock_runner._agent = mock_agent

        mock_package_project.return_value = (self.temp_dir, True)

        services_config = ServicesConfig()
        protocol_adapters = [Mock()]

        manager = LocalDeployManager()

        result = await manager._create_detached_project(
            agent=mock_agent,
            runner=mock_runner,
            endpoint_path="/custom",
            services_config=services_config,
            protocol_adapters=protocol_adapters,
        )

        assert result == self.temp_dir

        # Verify PackageConfig was created with correct parameters
        mock_package_config.assert_called_once()
        call_args = mock_package_config.call_args[1]
        assert call_args["endpoint_path"] == "/custom"
        assert call_args["deployment_mode"] == "detached_process"
        assert call_args["protocol_adapters"] == protocol_adapters

    @pytest.mark.asyncio
    async def test_stop_daemon_thread(self):
        """Test stopping daemon thread service."""
        manager = LocalDeployManager()
        manager.is_running = True
        manager._server = Mock()
        manager._server_thread = Mock()
        manager._server_thread.is_alive.return_value = False

        await manager.stop()

        assert manager.is_running is False
        assert manager._server.should_exit is True
        manager._server_thread.join.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_detached_process(self):
        """Test stopping detached process service."""
        manager = LocalDeployManager()
        manager.is_running = True
        manager._detached_process_pid = 12345
        manager._detached_pid_file = "/tmp/test.pid"

        # Create mock PID file
        pid_file_path = os.path.join(self.temp_dir, "test.pid")
        with open(pid_file_path, "w") as f:
            f.write("12345")
        manager._detached_pid_file = pid_file_path

        with patch.object(
            manager.process_manager,
            "stop_process_gracefully",
            new_callable=AsyncMock,
        ) as mock_stop:
            await manager.stop()

        assert manager.is_running is False
        assert manager._detached_process_pid is None
        mock_stop.assert_called_once_with(12345)

    @pytest.mark.asyncio
    async def test_stop_not_running(self):
        """Test stopping service when not running."""
        manager = LocalDeployManager()
        manager.is_running = False

        # Should not raise exception
        await manager.stop()

    def test_is_server_ready(self):
        """Test server readiness check."""
        manager = LocalDeployManager()

        # Mock successful connection
        with patch("socket.socket") as mock_socket:
            mock_sock = Mock()
            mock_sock.connect_ex.return_value = 0  # Success
            mock_socket.return_value.__enter__.return_value = mock_sock

            result = manager._is_server_ready()
            assert result is True

        # Mock failed connection
        with patch("socket.socket") as mock_socket:
            mock_sock = Mock()
            mock_sock.connect_ex.return_value = 1  # Connection refused
            mock_socket.return_value.__enter__.return_value = mock_sock

            result = manager._is_server_ready()
            assert result is False

    @pytest.mark.asyncio
    async def test_wait_for_server_ready_success(self):
        """Test waiting for server to become ready (success case)."""
        manager = LocalDeployManager()

        with patch.object(manager, "_is_server_ready", return_value=True):
            # Should return without raising exception
            await manager._wait_for_server_ready(timeout=1)

    @pytest.mark.asyncio
    async def test_wait_for_server_ready_timeout(self):
        """Test waiting for server to become ready (timeout case)."""
        manager = LocalDeployManager()

        with patch.object(manager, "_is_server_ready", return_value=False):
            with pytest.raises(
                RuntimeError,
                match="Server did not become ready within timeout",
            ):
                await manager._wait_for_server_ready(timeout=0.1)

    def test_is_service_running_daemon_thread(self):
        """Test service running check for daemon thread mode."""
        manager = LocalDeployManager()
        manager.is_running = True
        manager._server = Mock()

        with patch.object(manager, "_is_server_ready", return_value=True):
            result = manager.is_service_running()
            assert result is True

    def test_is_service_running_detached_process(self):
        """Test service running check for detached process mode."""
        manager = LocalDeployManager()
        manager.is_running = True
        manager._detached_process_pid = 12345

        with patch.object(
            manager.process_manager, "is_process_running", return_value=True
        ):
            result = manager.is_service_running()
            assert result is True

    def test_is_service_running_not_running(self):
        """Test service running check when not running."""
        manager = LocalDeployManager()
        manager.is_running = False

        result = manager.is_service_running()
        assert result is False

    def test_get_deployment_info_daemon_thread(self):
        """Test getting deployment info for daemon thread mode."""
        manager = LocalDeployManager()
        manager.deploy_id = "daemon_127.0.0.1_8000"
        manager.is_running = True

        info = manager.get_deployment_info()

        assert info["deploy_id"] == "daemon_127.0.0.1_8000"
        assert info["host"] == "127.0.0.1"
        assert info["port"] == 8000
        assert info["is_running"] is True
        assert info["mode"] == "daemon_thread"
        assert info["pid"] is None
        assert info["url"] == "http://127.0.0.1:8000"

    def test_get_deployment_info_detached_process(self):
        """Test getting deployment info for detached process mode."""
        manager = LocalDeployManager()
        manager.deploy_id = "detached_12345"
        manager.is_running = True
        manager._detached_process_pid = 12345

        info = manager.get_deployment_info()

        assert info["mode"] == "detached_process"
        assert info["pid"] == 12345

    def test_service_url_property(self):
        """Test service_url property."""
        manager = LocalDeployManager()
        manager.is_running = False

        # Not running
        url = manager.service_url
        assert url is None

        # Running
        manager.is_running = True
        url = manager.service_url
        assert url == "http://127.0.0.1:8000"

    @patch(
        "agentscope_runtime.engine.deployers.local_deployer.package_project"
    )
    @pytest.mark.asyncio
    async def test_detached_process_service_not_ready(
        self, mock_package_project
    ):
        """Test detached process deployment when service doesn't become ready."""
        mock_agent = Mock()
        mock_runner = Mock()
        mock_runner._agent = mock_agent

        mock_package_project.return_value = (self.temp_dir, True)

        # Create a mock main.py file
        main_py_path = os.path.join(self.temp_dir, "main.py")
        with open(main_py_path, "w") as f:
            f.write("# Mock main.py\nprint('Hello')")

        manager = LocalDeployManager()

        with patch.object(
            manager.process_manager,
            "start_detached_process",
            new_callable=AsyncMock,
        ) as mock_start, patch.object(
            manager.process_manager, "wait_for_port", new_callable=AsyncMock
        ) as mock_wait:
            mock_start.return_value = 12345
            mock_wait.return_value = False  # Service not ready

            with pytest.raises(
                RuntimeError, match="Service did not start within timeout"
            ):
                await manager.deploy(
                    runner=mock_runner,
                    mode=DeploymentMode.DETACHED_PROCESS,
                )
