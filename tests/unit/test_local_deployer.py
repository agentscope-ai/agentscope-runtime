# -*- coding: utf-8 -*-
# pylint:disable=too-many-return-statements, unused-variable
# pylint:disable=protected-access, too-many-public-methods

import os
import shutil
import tempfile

# Mock classes will be provided by pytest-mock plugin

import pytest

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

    @pytest.mark.asyncio
    async def test_deploy_daemon_thread_mode(self, mocker):
        """Test deployment in daemon thread mode."""
        mock_app_factory = mocker.patch(
            "agentscope_runtime.engine.deployers.local_deployer.FastAPIAppFactory",  # noqa E501
        )
        mock_server_class = mocker.patch("uvicorn.Server")
        # Setup mocks
        mock_app = mocker.Mock()
        mock_app_factory.create_app.return_value = mock_app

        # Create a proper mock server instance with async serve method
        mock_server_instance = mocker.MagicMock()
        mock_server_instance.serve = mocker.AsyncMock()
        mock_server_class.return_value = mock_server_instance

        mock_runner = mocker.Mock()

        manager = LocalDeployManager()

        # Mock the server readiness check
        mocker.patch.object(
            manager,
            "_wait_for_server_ready",
            new_callable=mocker.AsyncMock,
        )
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

        # Stop the manager to clean up the thread
        await manager.stop()

    @pytest.mark.asyncio
    async def test_deploy_detached_process_mode(self, mocker):
        """Test deployment in detached process mode."""
        mock_package_project = mocker.patch(
            "agentscope_runtime.engine.deployers.local_deployer.package_project",  # noqa E501
        )
        # Setup mocks
        mock_agent = mocker.Mock()
        mock_runner = mocker.Mock()
        mock_runner._agent = mock_agent

        mock_package_project.return_value = (self.temp_dir, True)

        # Create a mock main.py file
        main_py_path = os.path.join(self.temp_dir, "main.py")
        with open(main_py_path, "w", encoding="utf-8") as f:
            f.write("# Mock main.py\nprint('Hello')")

        manager = LocalDeployManager()

        # Mock process manager methods
        mock_start = mocker.patch.object(
            manager.process_manager,
            "start_detached_process",
            new_callable=mocker.AsyncMock,
        )
        mock_wait = mocker.patch.object(
            manager.process_manager,
            "wait_for_port",
            new_callable=mocker.AsyncMock,
        )
        mock_create_pid = mocker.patch.object(
            manager.process_manager,
            "create_pid_file",
        )
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
    async def test_deploy_detached_process_no_agent(self, mocker):
        """Test detached process deployment without agent."""
        # Test with runner but no agent
        mock_runner = mocker.Mock()
        mock_runner._agent = None

        manager = LocalDeployManager()

        # The validation happens in _deploy_detached_process but after
        # template creation
        # So it raises a RuntimeError wrapping the original ValueError
        with pytest.raises(
            RuntimeError,
            match="Failed to deploy service",
        ):
            await manager.deploy(
                runner=mock_runner,
                mode=DeploymentMode.DETACHED_PROCESS,
            )

        # Test with no runner at all
        with pytest.raises(
            RuntimeError,
            match="Failed to deploy service",
        ):
            await manager.deploy(
                runner=None,
                mode=DeploymentMode.DETACHED_PROCESS,
            )

    @pytest.mark.asyncio
    async def test_deploy_unsupported_mode(self):
        """Test deployment with unsupported mode."""
        manager = LocalDeployManager()

        with pytest.raises(RuntimeError, match="Failed to deploy service"):
            await manager.deploy(mode="unsupported_mode")

    @pytest.mark.asyncio
    async def test_deploy_already_running(self):
        """Test deployment when service is already running."""
        manager = LocalDeployManager()
        manager.is_running = True

        with pytest.raises(RuntimeError, match="Service is already running"):
            await manager.deploy()

    @pytest.mark.asyncio
    async def test_deploy_with_custom_config(self, mocker):
        """Test deployment with custom configuration."""
        mock_app_factory = mocker.patch(
            "agentscope_runtime.engine.deployers.local_deployer.FastAPIAppFactory",  # noqa E501
        )
        mock_server_class = mocker.patch("uvicorn.Server")
        mock_app = mocker.Mock()
        mock_app_factory.create_app.return_value = mock_app

        mock_server_instance = mocker.Mock()
        mock_server_class.return_value = mock_server_instance

        mock_runner = mocker.Mock()
        services_config = ServicesConfig()

        manager = LocalDeployManager()

        mocker.patch.object(
            manager,
            "_wait_for_server_ready",
            new_callable=mocker.AsyncMock,
        )
        _ = await manager.deploy(
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

        # Stop the manager to clean up the thread
        await manager.stop()

    @pytest.mark.asyncio
    async def test_create_detached_project(self, mocker):
        """Test creating detached project."""
        mock_package_config = mocker.patch(
            "agentscope_runtime.engine.deployers.local_deployer.PackageConfig",
        )
        mock_package_project = mocker.patch(
            "agentscope_runtime.engine.deployers.local_deployer.package_project",  # noqa E501
        )
        mock_agent = mocker.Mock()
        mock_runner = mocker.Mock()
        mock_runner._agent = mock_agent

        mock_package_project.return_value = (self.temp_dir, True)

        services_config = ServicesConfig()
        protocol_adapters = [mocker.Mock()]

        manager = LocalDeployManager()

        result = await manager.create_detached_project(
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
    async def test_stop_daemon_thread(self, mocker):
        """Test stopping daemon thread service."""
        manager = LocalDeployManager()
        manager.is_running = True
        mock_server = mocker.Mock()
        mock_thread = mocker.Mock()
        manager._server = mock_server
        manager._server_thread = mock_thread
        # Set is_alive to True first to trigger join(), then to False to
        # avoid warning
        mock_thread.is_alive.side_effect = [True, False]

        await manager.stop()

        assert manager.is_running is False
        # After cleanup, _server is set to None, so check the mock that
        # was used
        assert mock_server.should_exit is True
        mock_thread.join.assert_called_once_with(
            timeout=manager._shutdown_timeout,
        )
        # After cleanup, these should be None
        assert manager._server is None
        assert manager._server_thread is None

    @pytest.mark.asyncio
    async def test_stop_detached_process(self, mocker):
        """Test stopping detached process service."""
        manager = LocalDeployManager()
        manager.is_running = True
        manager._detached_process_pid = 12345
        manager._detached_pid_file = "/tmp/test.pid"

        # Create mock PID file
        pid_file_path = os.path.join(self.temp_dir, "test.pid")
        with open(pid_file_path, "w", encoding="utf-8") as f:
            f.write("12345")
        manager._detached_pid_file = pid_file_path

        mock_stop = mocker.patch.object(
            manager.process_manager,
            "stop_process_gracefully",
            new_callable=mocker.AsyncMock,
        )
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

    @pytest.mark.asyncio
    async def test_minimal_functionality_without_heavy_mocking(self):
        """Test basic functionality with minimal mocking."""
        manager = LocalDeployManager(host="localhost", port=9999)

        # Test initial state
        assert manager.host == "localhost"
        assert manager.port == 9999
        assert not manager.is_running
        assert manager.service_url is None

        # Test deployment info when not running
        info = manager.get_deployment_info()
        assert info["host"] == "localhost"
        assert info["port"] == 9999
        assert info["is_running"] is False
        assert info["url"] is None

        # Test server readiness check (should fail for unused port)
        assert not manager._is_server_ready()

        # Test process manager functionality
        process_manager = manager.process_manager
        assert process_manager.shutdown_timeout == 120  # default

        # Mock just the essential parts for testing wait_for_port
        result = await process_manager.wait_for_port(
            "127.0.0.1",
            9999,
            timeout=0.1,
        )
        assert result is False  # Should timeout quickly

        # Test template manager
        template_manager = manager.template_manager
        assert template_manager is not None

    def test_is_server_ready(self, mocker):
        """Test server readiness check."""
        manager = LocalDeployManager()

        # Mock successful connection
        mock_socket = mocker.patch("socket.socket")
        mock_sock = mocker.Mock()
        mock_sock.connect_ex.return_value = 0  # Success
        mock_socket.return_value.__enter__.return_value = mock_sock

        result = manager._is_server_ready()
        assert result is True

        # Mock failed connection
        mock_socket.reset_mock()
        mock_sock = mocker.Mock()
        mock_sock.connect_ex.return_value = 1  # Connection refused
        mock_socket.return_value.__enter__.return_value = mock_sock

        result = manager._is_server_ready()
        assert result is False

    @pytest.mark.asyncio
    async def test_wait_for_server_ready_success(self, mocker):
        """Test waiting for server to become ready (success case)."""
        manager = LocalDeployManager()

        mocker.patch.object(manager, "_is_server_ready", return_value=True)
        # Should return without raising exception
        await manager._wait_for_server_ready(timeout=1)

    @pytest.mark.asyncio
    async def test_wait_for_server_ready_timeout(self, mocker):
        """Test waiting for server to become ready (timeout case)."""
        manager = LocalDeployManager()

        mocker.patch.object(manager, "_is_server_ready", return_value=False)
        with pytest.raises(
            RuntimeError,
            match="Server did not become ready within timeout",
        ):
            await manager._wait_for_server_ready(timeout=0.1)

    def test_is_service_running_daemon_thread(self, mocker):
        """Test service running check for daemon thread mode."""
        manager = LocalDeployManager()
        manager.is_running = True
        manager._server = mocker.Mock()

        mocker.patch.object(manager, "_is_server_ready", return_value=True)
        result = manager.is_service_running()
        assert result is True

    def test_is_service_running_detached_process(self, mocker):
        """Test service running check for detached process mode."""
        manager = LocalDeployManager()
        manager.is_running = True
        manager._detached_process_pid = 12345

        mocker.patch.object(
            manager.process_manager,
            "is_process_running",
            return_value=True,
        )
        result = manager.is_service_running()
        assert result is True

    def test_is_service_running_not_running(self):
        """Test service running check when not running."""
        manager = LocalDeployManager()
        manager.is_running = False

        result = manager.is_service_running()
        assert result is False

    def test_get_deployment_info_daemon_thread(self, mocker):
        """Test getting deployment info for daemon thread mode."""
        manager = LocalDeployManager()
        manager.deploy_id = "daemon_127.0.0.1_8000"
        manager.is_running = True
        # Set up a mock server to make is_service_running() return True
        manager._server = mocker.Mock()

        # Mock _is_server_ready to return True
        mocker.patch.object(manager, "_is_server_ready", return_value=True)
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

    @pytest.mark.asyncio
    async def test_detached_process_service_not_ready(self, mocker):
        """Test detached process deployment when service doesn't become
        ready."""
        mock_package_project = mocker.patch(
            "agentscope_runtime.engine.deployers.local_deployer.package_project",  # noqa E501
        )
        mock_agent = mocker.Mock()
        mock_runner = mocker.Mock()
        mock_runner._agent = mock_agent

        mock_package_project.return_value = (self.temp_dir, True)

        # Create a mock main.py file
        main_py_path = os.path.join(self.temp_dir, "main.py")
        with open(main_py_path, "w", encoding="utf-8") as f:
            f.write("# Mock main.py\nprint('Hello')")

        manager = LocalDeployManager()

        mock_start = mocker.patch.object(
            manager.process_manager,
            "start_detached_process",
            new_callable=mocker.AsyncMock,
        )
        mock_wait = mocker.patch.object(
            manager.process_manager,
            "wait_for_port",
            new_callable=mocker.AsyncMock,
        )
        mock_start.return_value = 12345
        mock_wait.return_value = False  # Service not ready

        with pytest.raises(
            RuntimeError,
            match="Service did not start within timeout",
        ):
            await manager.deploy(
                runner=mock_runner,
                mode=DeploymentMode.DETACHED_PROCESS,
            )
