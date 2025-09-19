# -*- coding: utf-8 -*-
# pylint:disable=pointless-string-statement

import os
import shutil
import tempfile

# Mock classes will be provided by pytest-mock plugin

import pytest
from fastapi import FastAPI

from agentscope_runtime.engine.deployers.utils.deployment_modes import (
    DeploymentMode,
)
from agentscope_runtime.engine.deployers.utils.service_utils import (
    FastAPIAppFactory,
    FastAPITemplateManager,
    ProcessManager,
    ServicesConfig,
)


class TestFastAPIAppFactory:
    """Test cases for FastAPIAppFactory class."""

    def test_create_app_basic(self):
        """Test basic FastAPI app creation."""
        app = FastAPIAppFactory.create_app()

        assert isinstance(app, FastAPI)
        assert app.state.deployment_mode == DeploymentMode.DAEMON_THREAD
        assert app.state.endpoint_path == "/process"
        assert app.state.stream_enabled is True
        assert app.state.response_type == "sse"

    def test_create_app_with_runner(self, mocker):
        """Test FastAPI app creation with runner."""
        mock_runner = mocker.Mock()
        app = FastAPIAppFactory.create_app(
            runner=mock_runner,
            endpoint_path="/api/process",
            response_type="json",
            stream=False,
        )

        assert app.state.external_runner == mock_runner
        assert app.state.endpoint_path == "/api/process"
        assert app.state.response_type == "json"
        assert app.state.stream_enabled is False

    def test_create_app_with_services_config(self):
        """Test FastAPI app creation with services config."""
        services_config = ServicesConfig()
        app = FastAPIAppFactory.create_app(services_config=services_config)
        assert app.state.services_config == services_config

    def test_create_app_with_protocol_adapters(self, mocker):
        """Test FastAPI app creation with protocol adapters."""
        protocol_adapters = [mocker.Mock(), mocker.Mock()]
        app = FastAPIAppFactory.create_app(protocol_adapters=protocol_adapters)
        assert app.state.protocol_adapters == protocol_adapters

    def test_create_app_deployment_modes(self):
        """Test FastAPI app creation with different deployment modes."""
        # Test DAEMON_THREAD mode
        app_daemon = FastAPIAppFactory.create_app(
            mode=DeploymentMode.DAEMON_THREAD,
        )
        assert app_daemon.state.deployment_mode == DeploymentMode.DAEMON_THREAD

        # Test DETACHED_PROCESS mode
        app_detached = FastAPIAppFactory.create_app(
            mode=DeploymentMode.DETACHED_PROCESS,
        )
        assert (
            app_detached.state.deployment_mode
            == DeploymentMode.DETACHED_PROCESS
        )

        # Test STANDALONE mode
        app_standalone = FastAPIAppFactory.create_app(
            mode=DeploymentMode.STANDALONE,
        )
        assert (
            app_standalone.state.deployment_mode == DeploymentMode.STANDALONE
        )


class TestFastAPITemplateManager:
    """Test cases for FastAPITemplateManager class."""

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """Set up and tear down test environment."""
        self.temp_dir = tempfile.mkdtemp()
        yield
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_template_manager_creation(self):
        """Test FastAPITemplateManager creation."""
        manager = FastAPITemplateManager()
        assert isinstance(manager, FastAPITemplateManager)

    def test_render_standalone_template(self, mocker):
        mock_render = mocker.patch.object(
            FastAPITemplateManager,
            "render_standalone_template",
        )
        """Test rendering standalone template."""
        mock_render.return_value = (
            "# Generated FastAPI main.py\nfrom fastapi import FastAPI\n\n"
            "app = FastAPI()\n"
        )

        manager = FastAPITemplateManager()
        result = manager.render_standalone_template(
            agent_name="test_agent",
            endpoint_path="/process",
            deployment_mode="standalone",
        )

        assert isinstance(result, str)
        assert "test_agent" in result or "FastAPI" in result
        mock_render.assert_called_once()

    def test_render_template_from_string(self):
        """Test rendering template from string."""
        manager = FastAPITemplateManager()
        template_string = "Agent: {{agent_name}}, Endpoint: {{endpoint_path}}"

        result = manager.render_template_from_string(
            template_string,
            agent_name="my_agent",
            endpoint_path="/api",
        )

        assert result == "Agent: my_agent, Endpoint: /api"

    def test_render_template_with_protocol_adapters(self, mocker):
        mock_render = mocker.patch.object(
            FastAPITemplateManager,
            "render_standalone_template",
        )
        """Test rendering template with protocol adapters."""
        mock_render.return_value = (
            "# Generated code with adapters\nadapters = [HttpAdapter(), "
            "WsAdapter()]\ntest_agent = Agent()"
        )

        manager = FastAPITemplateManager()
        protocol_adapters_str = "adapters = [HttpAdapter(), WsAdapter()]"

        result = manager.render_standalone_template(
            agent_name="test_agent",
            protocol_adapters=protocol_adapters_str,
        )

        assert "test_agent" in result or "adapters" in result
        mock_render.assert_called_once()


class TestProcessManager:
    """Test cases for ProcessManager class."""

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """Set up and tear down test environment."""
        self.temp_dir = tempfile.mkdtemp()
        yield
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_process_manager_creation(self):
        """Test ProcessManager creation."""
        manager = ProcessManager()
        assert isinstance(manager, ProcessManager)
        assert (
            manager.shutdown_timeout == 30
        )  # default timeout from actual implementation

        custom_manager = ProcessManager(shutdown_timeout=60)
        assert custom_manager.shutdown_timeout == 60

    @pytest.mark.asyncio
    async def test_start_detached_process(self, mocker):
        mock_popen = mocker.patch("subprocess.Popen")
        """Test starting a detached process."""
        # Create a test script
        script_path = os.path.join(self.temp_dir, "test_script.py")
        with open(script_path, "w", encoding="utf-8") as f:
            f.write("print('Hello World')")

        # Mock the subprocess
        mock_process = mocker.Mock()
        mock_process.pid = 12345
        mock_process.poll.return_value = None  # Process is still running
        mock_popen.return_value = mock_process

        manager = ProcessManager()
        pid = await manager.start_detached_process(
            script_path=script_path,
            host="127.0.0.1",
            port=8000,
        )

        assert pid == 12345
        mock_popen.assert_called_once()
        # Verify the command was called correctly
        call_args = mock_popen.call_args
        assert "python" in call_args[0][0]
        assert script_path in call_args[0][0]

    def test_create_pid_file(self):
        """Test creating PID file."""
        pid_file = os.path.join(self.temp_dir, "test.pid")
        manager = ProcessManager()

        manager.create_pid_file(12345, pid_file)

        assert os.path.exists(pid_file)
        with open(pid_file, "r", encoding="utf-8") as f:
            content = f.read().strip()
            assert content == "12345"

    def test_cleanup_pid_file(self):
        """Test cleaning up PID file."""
        pid_file = os.path.join(self.temp_dir, "test.pid")

        # Create PID file
        with open(pid_file, "w", encoding="utf-8") as f:
            f.write("12345")

        manager = ProcessManager()
        manager.cleanup_pid_file(pid_file)

        assert not os.path.exists(pid_file)

    def test_is_process_running(self, mocker):
        mock_pid_exists = mocker.patch("psutil.pid_exists")
        """Test checking if process is running."""
        mock_pid_exists.return_value = True

        manager = ProcessManager()
        result = manager.is_process_running(12345)

        assert result is True
        mock_pid_exists.assert_called_once_with(12345)

    @pytest.mark.asyncio
    async def test_wait_for_port(self, mocker):
        mock_socket = mocker.patch("socket.socket")
        """Test waiting for port to be available."""
        # Mock successful connection
        mock_sock = mocker.Mock()
        mock_sock.connect_ex.return_value = 0  # Success
        mock_socket.return_value.__enter__.return_value = mock_sock

        manager = ProcessManager()
        result = await manager.wait_for_port("127.0.0.1", 8000, timeout=1)

        assert result is True

    @pytest.mark.asyncio
    async def test_wait_for_port_timeout(self, mocker):
        mock_socket = mocker.patch("socket.socket")
        """Test waiting for port with timeout."""
        # Mock failed connection
        mock_sock = mocker.Mock()
        mock_sock.connect_ex.return_value = 1  # Connection refused
        mock_socket.return_value.__enter__.return_value = mock_sock

        manager = ProcessManager()
        result = await manager.wait_for_port("127.0.0.1", 8000, timeout=0.1)

        assert result is False

    @pytest.mark.asyncio
    async def test_stop_process_gracefully(self, mocker):
        mock_pid_exists = mocker.patch("psutil.pid_exists")
        mock_process_class = mocker.patch("psutil.Process")
        """Test stopping process gracefully."""
        mock_pid_exists.return_value = True
        mock_proc = mocker.Mock()
        mock_proc.terminate = mocker.Mock()
        mock_proc.wait = mocker.Mock()
        mock_process_class.return_value = mock_proc

        manager = ProcessManager()
        result = await manager.stop_process_gracefully(12345)

        assert result is True
        mock_proc.terminate.assert_called_once()
        mock_proc.wait.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_process_gracefully_force_kill(self, mocker):
        mock_pid_exists = mocker.patch("psutil.pid_exists")
        mock_process_class = mocker.patch("psutil.Process")
        """Test stopping process with force kill."""
        mock_pid_exists.return_value = True
        mock_proc = mocker.Mock()
        mock_proc.terminate = mocker.Mock()
        mock_proc.wait.side_effect = [
            __import__("psutil").TimeoutExpired(12345),  # First wait times out
            None,  # Second wait (after kill) succeeds
        ]
        mock_proc.kill = mocker.Mock()
        mock_process_class.return_value = mock_proc

        manager = ProcessManager(
            shutdown_timeout=0.1,
        )  # Short timeout for test
        result = await manager.stop_process_gracefully(12345)

        assert result is True
        mock_proc.terminate.assert_called_once()
        mock_proc.kill.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_nonexistent_process(self, mocker):
        mocker.patch("psutil.NoSuchProcess")
        """Test stopping nonexistent process."""
        with mocker.patch("psutil.pid_exists", return_value=False):
            manager = ProcessManager()
            result = await manager.stop_process_gracefully(99999)
            assert (
                result is True
            )  # Should return True for already terminated process
