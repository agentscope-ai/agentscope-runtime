# -*- coding: utf-8 -*-
# pylint:disable=protected-access, unused-argument

import asyncio
import logging
import os
import socket
import threading
from typing import Callable, Optional, Type, Any, Dict, Union, List

import uvicorn

from .adapter.protocol_adapter import ProtocolAdapter
from .base import DeployManager
from .utils.deployment_modes import DeploymentMode
from .utils.detached_app import (
    build_detached_app,
    get_bundle_entry_script,
)
from .utils.service_utils import (
    FastAPIAppFactory,
    ProcessManager,
)


class LocalDeployManager(DeployManager):
    """Unified LocalDeployManager supporting multiple deployment modes."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8000,
        shutdown_timeout: int = 30,
        startup_timeout: int = 30,
        logger: Optional[logging.Logger] = None,
    ):
        """Initialize LocalDeployManager.

        Args:
            host: Host to bind to
            port: Port to bind to
            shutdown_timeout: Timeout for graceful shutdown
            logger: Logger instance
        """
        super().__init__()
        self.host = host
        self.port = port
        self._shutdown_timeout = shutdown_timeout
        self._startup_timeout = startup_timeout
        self._logger = logger or logging.getLogger(__name__)

        # State management
        self.is_running = False

        # Daemon thread mode attributes
        self._server: Optional[uvicorn.Server] = None
        self._server_thread: Optional[threading.Thread] = None
        self._server_task: Optional[asyncio.Task] = None

        # Detached process mode attributes
        self._detached_process_pid: Optional[int] = None
        self._detached_pid_file: Optional[str] = None
        self.process_manager = ProcessManager(
            shutdown_timeout=shutdown_timeout,
        )

    async def deploy(
        self,
        app=None,
        runner=None,
        endpoint_path: str = "/process",
        request_model: Optional[Type] = None,
        response_type: str = "sse",
        stream: bool = True,
        before_start: Optional[Callable] = None,
        after_finish: Optional[Callable] = None,
        mode: DeploymentMode = DeploymentMode.DAEMON_THREAD,
        custom_endpoints: Optional[List[Dict]] = None,
        protocol_adapters: Optional[list[ProtocolAdapter]] = None,
        broker_url: Optional[str] = None,
        backend_url: Optional[str] = None,
        enable_embedded_worker: bool = False,
        **kwargs: Any,
    ) -> Dict[str, str]:
        """Deploy using unified FastAPI architecture.

        Args:
            app: Agent app to be deployed
            runner: Runner instance (for DAEMON_THREAD mode)
            endpoint_path: API endpoint path
            request_model: Pydantic model for request validation
            response_type: Response type - "json", "sse", or "text"
            stream: Enable streaming responses
            before_start: Callback function called before server starts
            after_finish: Callback function called after server finishes
            mode: Deployment mode
            custom_endpoints: Custom endpoints from agent app
            protocol_adapters: Protocol adapters
            broker_url: Celery broker URL for background task processing
            backend_url: Celery backend URL for result storage
            enable_embedded_worker: Whether to run Celery worker
                embedded in the app
            **kwargs: Additional keyword arguments

        Returns:
            Dict containing deploy_id and url

        Raises:
            RuntimeError: If deployment fails
        """
        if self.is_running:
            raise RuntimeError("Service is already running")

        self._app = app
        if self._app is not None:
            runner = self._app._runner
            endpoint_path = self._app.endpoint_path
            response_type = self._app.response_type
            stream = self._app.stream
            request_model = self._app.request_model
            before_start = self._app.before_start
            after_finish = self._app.after_finish
            backend_url = self._app.backend_url
            broker_url = self._app.broker_url
            custom_endpoints = self._app.custom_endpoints
            protocol_adapters = self._app.protocol_adapters
        try:
            if mode == DeploymentMode.DAEMON_THREAD:
                return await self._deploy_daemon_thread(
                    runner=runner,
                    endpoint_path=endpoint_path,
                    request_model=request_model,
                    response_type=response_type,
                    stream=stream,
                    before_start=before_start,
                    after_finish=after_finish,
                    custom_endpoints=custom_endpoints,
                    protocol_adapters=protocol_adapters,
                    broker_url=broker_url,
                    backend_url=backend_url,
                    enable_embedded_worker=enable_embedded_worker,
                    **kwargs,
                )
            elif mode == DeploymentMode.DETACHED_PROCESS:
                return await self._deploy_detached_process(
                    runner=runner,
                    endpoint_path=endpoint_path,
                    request_model=request_model,
                    response_type=response_type,
                    stream=stream,
                    before_start=before_start,
                    after_finish=after_finish,
                    custom_endpoints=custom_endpoints,
                    protocol_adapters=protocol_adapters,
                    **kwargs,
                )
            else:
                raise ValueError(
                    f"Unsupported deployment mode for LocalDeployManager: "
                    f"{mode}",
                )

        except Exception as e:
            self._logger.error(f"Deployment failed: {e}")
            raise RuntimeError(f"Failed to deploy service: {e}") from e

    async def _deploy_daemon_thread(
        self,
        runner: Optional[Any] = None,
        protocol_adapters: Optional[list[ProtocolAdapter]] = None,
        broker_url: Optional[str] = None,
        backend_url: Optional[str] = None,
        enable_embedded_worker: bool = False,
        **kwargs,
    ) -> Dict[str, str]:
        """Deploy in daemon thread mode."""
        self._logger.info("Deploying FastAPI service in daemon thread mode...")

        # Create FastAPI app using factory with Celery support
        app = FastAPIAppFactory.create_app(
            runner=runner,
            mode=DeploymentMode.DAEMON_THREAD,
            protocol_adapters=protocol_adapters,
            broker_url=broker_url,
            backend_url=backend_url,
            enable_embedded_worker=enable_embedded_worker,
            **kwargs,
        )

        # Create uvicorn server
        config = uvicorn.Config(
            app=app,
            host=self.host,
            port=self.port,
            loop="asyncio",
            log_level="info",
        )
        self._server = uvicorn.Server(config)

        # Start server in daemon thread
        def run_server():
            asyncio.run(self._server.serve())

        self._server_thread = threading.Thread(target=run_server, daemon=True)
        self._server_thread.start()

        # Wait for server to start
        await self._wait_for_server_ready(self._startup_timeout)

        self.is_running = True
        self.deploy_id = f"daemon_{self.host}_{self.port}"

        self._logger.info(
            f"FastAPI service started at http://{self.host}:{self.port}",
        )

        return {
            "deploy_id": self.deploy_id,
            "url": f"http://{self.host}:{self.port}",
        }

    async def _deploy_detached_process(
        self,
        runner: Optional[Any] = None,
        protocol_adapters: Optional[list[ProtocolAdapter]] = None,
        **kwargs,
    ) -> Dict[str, str]:
        """Deploy in detached process mode."""
        self._logger.info(
            "Deploying FastAPI service in detached process mode...",
        )

        if runner is None and self._app is None:
            raise ValueError(
                "Detached process mode requires an app or runner",
            )

        if "agent" in kwargs:
            kwargs.pop("agent")
        if "app" in kwargs:
            kwargs.pop("app")

        # Create package project for detached deployment
        project_dir = await self.create_detached_project(
            app=self._app,
            runner=runner,
            protocol_adapters=protocol_adapters,
            **kwargs,
        )

        try:
            entry_script = get_bundle_entry_script(project_dir)
            script_path = os.path.join(project_dir, entry_script)

            # Start detached process using the packaged project
            pid = await self.process_manager.start_detached_process(
                script_path=script_path,
                host=self.host,
                port=self.port,
            )

            self._detached_process_pid = pid
            self._detached_pid_file = f"/tmp/agentscope_runtime_{pid}.pid"

            # Create PID file
            self.process_manager.create_pid_file(pid, self._detached_pid_file)

            # Wait for service to become available
            service_ready = await self.process_manager.wait_for_port(
                self.host,
                self.port,
                timeout=30,
            )

            if not service_ready:
                raise RuntimeError("Service did not start within timeout")

            self.is_running = True
            self.deploy_id = f"detached_{pid}"

            self._logger.info(
                f"FastAPI service started in detached process (PID: {pid})",
            )

            return {
                "deploy_id": self.deploy_id,
                "url": f"http://{self.host}:{self.port}",
            }

        except Exception as e:
            # Cleanup on failure
            if os.path.exists(project_dir):
                try:
                    import shutil

                    shutil.rmtree(project_dir)
                except OSError:
                    pass
            raise e

    @staticmethod
    async def create_detached_project(
        app=None,
        runner: Optional[Any] = None,
        endpoint_path: str = "/process",
        requirements: Optional[Union[str, List[str]]] = None,
        extra_packages: Optional[List[str]] = None,
        protocol_adapters: Optional[list[ProtocolAdapter]] = None,
        custom_endpoints: Optional[List[Dict]] = None,
        broker_url: Optional[str] = None,
        backend_url: Optional[str] = None,
        enable_embedded_worker: bool = False,
        **kwargs,
    ) -> str:
        project_dir, _ = build_detached_app(
            app=app,
            runner=runner,
            requirements=requirements,
            extra_packages=extra_packages,
            **kwargs,
        )

        return project_dir

    async def stop(self) -> None:
        """Stop the FastAPI service (unified method for all modes)."""
        if not self.is_running:
            self._logger.warning("Service is not running")
            return

        try:
            if self._detached_process_pid:
                # Detached process mode
                await self._stop_detached_process()
            else:
                # Daemon thread mode
                await self._stop_daemon_thread()

        except Exception as e:
            self._logger.error(f"Failed to stop service: {e}")
            raise RuntimeError(f"Failed to stop FastAPI service: {e}") from e

    async def _stop_daemon_thread(self):
        """Stop daemon thread mode service."""
        self._logger.info("Stopping FastAPI daemon thread service...")

        # Stop the server gracefully
        if self._server:
            self._server.should_exit = True

        # Wait for the server thread to finish
        if self._server_thread and self._server_thread.is_alive():
            self._server_thread.join(timeout=self._shutdown_timeout)
            if self._server_thread.is_alive():
                self._logger.warning(
                    "Server thread did not terminate, potential resource leak",
                )

        await self._cleanup_daemon_thread()
        self.is_running = False
        self._logger.info("FastAPI daemon thread service stopped successfully")

    async def _stop_detached_process(self):
        """Stop detached process mode service."""
        self._logger.info("Stopping FastAPI detached process service...")

        if self._detached_process_pid:
            await self.process_manager.stop_process_gracefully(
                self._detached_process_pid,
            )

        await self._cleanup_detached_process()
        self.is_running = False
        self._logger.info(
            "FastAPI detached process service stopped successfully",
        )

    async def _cleanup_daemon_thread(self):
        """Clean up daemon thread resources."""
        self._server = None
        self._server_task = None
        self._server_thread = None

    async def _cleanup_detached_process(self):
        """Clean up detached process resources."""
        # Cleanup PID file
        if self._detached_pid_file:
            self.process_manager.cleanup_pid_file(self._detached_pid_file)

        # Reset state
        self._detached_process_pid = None
        self._detached_pid_file = None

    def _is_server_ready(self) -> bool:
        """Check if the server is ready to accept connections."""
        try:
            # Normalize host for connection check
            # When service binds to 0.0.0.0, we need to connect to 127.0.0.1
            check_host = self._normalize_host_for_check(self.host)
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.1)
                result = s.connect_ex((check_host, self.port))
                return result == 0
        except Exception:
            return False

    @staticmethod
    def _normalize_host_for_check(host: str) -> str:
        """Normalize host for connection check.

        When a service binds to 0.0.0.0 (all interfaces), it cannot be
        directly connected to. We need to connect to 127.0.0.1 instead
        to check if the service is running locally.

        Args:
            host: The host the service binds to

        Returns:
            The host to use for connection check
        """
        if host in ("0.0.0.0", "::"):
            return "127.0.0.1"
        return host

    async def _wait_for_server_ready(self, timeout: int = 30):
        """Wait for server to become ready."""
        end_time = asyncio.get_event_loop().time() + timeout

        while asyncio.get_event_loop().time() < end_time:
            if self._is_server_ready():
                return

            await asyncio.sleep(0.1)

        raise RuntimeError("Server did not become ready within timeout")

    def is_service_running(self) -> bool:
        """Check if service is running."""
        if not self.is_running:
            return False

        if self._detached_process_pid:
            # Check detached process
            return self.process_manager.is_process_running(
                self._detached_process_pid,
            )
        else:
            # Check daemon thread
            return self._server is not None and self._is_server_ready()

    def get_deployment_info(self) -> Dict[str, Any]:
        """Get deployment information."""
        return {
            "deploy_id": self.deploy_id,
            "host": self.host,
            "port": self.port,
            "is_running": self.is_service_running(),
            "mode": "detached_process"
            if self._detached_process_pid
            else "daemon_thread",
            "pid": self._detached_process_pid,
            "url": f"http://{self.host}:{self.port}"
            if self.is_running
            else None,
        }

    @property
    def service_url(self) -> Optional[str]:
        """Get the current service URL if running."""
        if self.is_running and self.port:
            return f"http://{self.host}:{self.port}"
        return None
