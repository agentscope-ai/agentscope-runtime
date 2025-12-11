# -*- coding: utf-8 -*-
# pylint:disable=protected-access, unused-argument, too-many-branches

import asyncio
import logging
import os
import socket
import threading
from datetime import datetime
from typing import Callable, Optional, Type, Any, Dict, Union, List

import uvicorn

from agentscope_runtime.engine.deployers.state import Deployment
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
        port: int = 8090,
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
        # New parameters for project-based deployment
        project_dir: Optional[str] = None,
        entrypoint: Optional[str] = None,
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
            project_dir: Project directory (for DETACHED_PROCESS mode)
            entrypoint: Entrypoint specification (for DETACHED_PROCESS mode)
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
                    project_dir=project_dir,
                    entrypoint=entrypoint,
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
        agent_source: Optional[str] = None,
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

        url = f"http://{self.host}:{self.port}"

        self._logger.info(
            f"FastAPI service started at {url}",
        )

        deployment = Deployment(
            id=self.deploy_id,
            platform="local",
            url=url,
            status="running",
            created_at=datetime.now().isoformat(),
            agent_source=agent_source,
            config={
                "mode": DeploymentMode.DAEMON_THREAD,
                "host": self.host,
                "port": self.port,
                "broker_url": broker_url,
                "backend_url": backend_url,
                "enable_embedded_worker": enable_embedded_worker,
            },
        )
        self.state_manager.save(deployment)

        return {
            "deploy_id": self.deploy_id,
            "url": url,
        }

    async def _deploy_detached_process(
        self,
        runner: Optional[Any] = None,
        protocol_adapters: Optional[list[ProtocolAdapter]] = None,
        project_dir: Optional[str] = None,
        entrypoint: Optional[str] = None,
        agent_source: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, str]:
        """Deploy in detached process mode."""
        self._logger.info(
            "Deploying FastAPI service in detached process mode...",
        )

        # Clean up old log files (older than 24 hours)
        ProcessManager.cleanup_old_logs(max_age_hours=24)

        # Original behavior: require app or runner or entrypoint
        if runner is None and self._app is None and entrypoint is None:
            raise ValueError(
                "Detached process mode requires an app, runner, "
                "project_dir, or entrypoint",
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
            entrypoint=entrypoint,
            **kwargs,
        )

        if not project_dir:
            raise RuntimeError("Failed to parse project directory")

        try:
            entry_script = get_bundle_entry_script(project_dir)
            script_path = os.path.join(project_dir, entry_script)
            env = kwargs.get("environment", {}) or {}
            env.update(
                {
                    "HOST": self.host,
                    "PORT": str(self.port),
                },
            )
            # Start detached process using the packaged project
            pid = await self.process_manager.start_detached_process(
                script_path=script_path,
                host=self.host,
                port=self.port,
                env=env,
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
                # Check if process is still running
                is_running = self.process_manager.is_process_running(pid)

                # Get process logs
                logs = self.process_manager.get_process_logs(max_lines=50)

                # Log the detailed error for debugging
                self._logger.error(
                    f"Service did not start within timeout. "
                    f"Process (PID: {pid}) status: "
                    f"{'running' if is_running else 'terminated'}. "
                    f"Host: {self.host}, Port: {self.port}.\n\n"
                    f"Process logs:\n{logs}",
                )

                # Raise a simple error message
                raise RuntimeError(
                    "Service failed to start. Check logs above for details.",
                )

            self.is_running = True

            url = f"http://{self.host}:{self.port}"

            self._logger.info(
                f"FastAPI service started in detached process (PID: {pid})",
            )

            deployment = Deployment(
                id=self.deploy_id,
                platform="local",
                url=url,
                status="running",
                created_at=datetime.now().isoformat(),
                agent_source=agent_source,
                config={
                    "mode": DeploymentMode.DETACHED_PROCESS,
                    "host": self.host,
                    "port": self.port,
                    "pid": pid,
                    "pid_file": self._detached_pid_file,
                    "project_dir": project_dir,
                },
            )
            self.state_manager.save(deployment)

            return {
                "deploy_id": self.deploy_id,
                "url": url,
            }

        except Exception as e:
            raise e

    @staticmethod
    async def create_detached_project(
        app=None,
        runner: Optional[Any] = None,
        entrypoint: Optional[str] = None,
        endpoint_path: str = "/process",
        requirements: Optional[Union[str, List[str]]] = None,
        extra_packages: Optional[List[str]] = None,
        protocol_adapters: Optional[list[ProtocolAdapter]] = None,
        custom_endpoints: Optional[List[Dict]] = None,
        broker_url: Optional[str] = None,
        backend_url: Optional[str] = None,
        enable_embedded_worker: bool = False,
        platform: str = "local",
        **kwargs,
    ) -> str:
        project_dir, _ = build_detached_app(
            app=app,
            runner=runner,
            requirements=requirements,
            extra_packages=extra_packages,
            platform=platform,
            entrypoint=entrypoint,
            **kwargs,
        )

        return project_dir

    async def stop(
        self,
        deploy_id: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """Stop the FastAPI service.

        Args:
            deploy_id: Deployment identifier
            **kwargs: Additional parameters

        Returns:
            Dict with success status, message, and details
        """
        # If URL not provided, try to get it from state manager
        try:
            deployment = self.state_manager.get(deploy_id)
            if deployment:
                url = deployment.url
                self._logger.debug(f"Fetched URL from state: {url}")
        except Exception as e:
            self._logger.debug(f"Could not fetch URL from state: {e}")

        if not deployment:
            return {
                "success": False,
                "message": "Deploy id not found",
                "details": {
                    "deploy_id": deploy_id,
                    "error": "Deploy id not found",
                },
            }

        # Only attempt HTTP shutdown for detached process mode
        # In daemon thread mode, HTTP shutdown would kill the entire process
        # (including pytest), so we skip it and use direct stop methods instead
        if (
            url
            and deployment.config["mode"] == DeploymentMode.DETACHED_PROCESS
        ):
            try:
                import requests

                response = requests.post(f"{url}/shutdown", timeout=5)
                if response.status_code == 200:
                    # Remove from state manager on successful shutdown
                    try:
                        self.state_manager.update_status(deploy_id, "stopped")
                    except KeyError:
                        self._logger.debug(
                            f"Deployment {deploy_id} not found "
                            f"in state (already removed)",
                        )
                    self.is_running = False
                    return {
                        "success": True,
                        "message": "Shutdown signal sent to detached process",
                        "details": {"url": url, "deploy_id": deploy_id},
                    }

            except requests.exceptions.RequestException as e:
                # If HTTP shutdown fails, continue with direct stop methods
                self._logger.debug(
                    f"HTTP shutdown failed, falling back to direct stop: {e}",
                )

        try:
            # when run in from main process instead of cli, make sure close
            if self._detached_process_pid:
                # Detached process mode
                await self._stop_detached_process()
            else:
                # Daemon thread mode
                await self._stop_daemon_thread()

            # Remove from state manager on successful stop
            try:
                self.state_manager.update_status(deploy_id, "stopped")
            except KeyError:
                self._logger.debug(
                    f"Deployment {deploy_id} not found in state (already "
                    f"removed)",
                )

            return {
                "success": True,
                "message": "Service stopped successfully",
                "details": {"deploy_id": deploy_id},
            }
        except Exception as e:
            self._logger.error(f"Failed to stop service: {e}")
            return {
                "success": False,
                "message": f"Failed to stop service: {e}",
                "details": {"deploy_id": deploy_id, "error": str(e)},
            }

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

        # Cleanup log file (keep file for debugging)
        self.process_manager.cleanup_log_file(keep_file=True)

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
