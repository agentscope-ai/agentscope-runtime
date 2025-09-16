# -*- coding: utf-8 -*-
"""Modified LocalDeployManager with unified FastAPI architecture."""

import asyncio
import threading
import socket
import tempfile
import os
from typing import Callable, Optional, Type, Any, Dict
import uvicorn
import logging

from .utils.fastapi_factory import FastAPIAppFactory
from .utils.deployment_modes import DeploymentMode, DeploymentConfig
from .utils.service_config import ServicesConfig
from .utils.process_manager import ProcessManager
from .utils.fastapi_templates import FastAPITemplateManager


class LocalDeployManager:
    """Unified LocalDeployManager supporting multiple deployment modes."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8000,
        shutdown_timeout: int = 120,
        logger: Optional[logging.Logger] = None,
    ):
        """Initialize LocalDeployManager.

        Args:
            host: Host to bind to
            port: Port to bind to
            shutdown_timeout: Timeout for graceful shutdown
            logger: Logger instance
        """
        self.host = host
        self.port = port
        self._shutdown_timeout = shutdown_timeout
        self._logger = logger or logging.getLogger(__name__)

        # State management
        self._is_running = False
        self._deploy_id: Optional[str] = None

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

        # Template manager
        self.template_manager = FastAPITemplateManager()

    async def _deploy_async(
        self,
        func: Optional[Callable] = None,
        runner: Optional[Any] = None,
        endpoint_path: str = "/process",
        request_model: Optional[Type] = None,
        response_type: str = "sse",
        stream: bool = True,
        before_start: Optional[Callable] = None,
        after_finish: Optional[Callable] = None,
        mode: DeploymentMode = DeploymentMode.DAEMON_THREAD,
        services_config: Optional[ServicesConfig] = None,
        **kwargs: Any,
    ) -> Dict[str, str]:
        """Deploy using unified FastAPI architecture.

        Args:
            func: Custom processing function
            runner: Runner instance (for DAEMON_THREAD mode)
            endpoint_path: API endpoint path
            request_model: Pydantic model for request validation
            response_type: Response type - "json", "sse", or "text"
            stream: Enable streaming responses
            before_start: Callback function called before server starts
            after_finish: Callback function called after server finishes
            mode: Deployment mode
            services_config: Services configuration
            **kwargs: Additional keyword arguments

        Returns:
            Dict containing deploy_id and url

        Raises:
            RuntimeError: If deployment fails
        """
        if self._is_running:
            raise RuntimeError("Service is already running")

        try:
            if mode == DeploymentMode.DAEMON_THREAD:
                return await self._deploy_daemon_thread(
                    func=func,
                    runner=runner,
                    endpoint_path=endpoint_path,
                    request_model=request_model,
                    response_type=response_type,
                    stream=stream,
                    before_start=before_start,
                    after_finish=after_finish,
                    services_config=services_config,
                    **kwargs,
                )
            elif mode == DeploymentMode.DETACHED_PROCESS:
                return await self._deploy_detached_process(
                    func=func,
                    runner=runner,
                    endpoint_path=endpoint_path,
                    request_model=request_model,
                    response_type=response_type,
                    stream=stream,
                    before_start=before_start,
                    after_finish=after_finish,
                    services_config=services_config,
                    **kwargs,
                )
            else:
                raise ValueError(
                    f"Unsupported deployment mode for LocalDeployManager: {mode}",
                )

        except Exception as e:
            self._logger.error(f"Deployment failed: {e}")
            raise RuntimeError(f"Failed to deploy service: {e}") from e

    async def _deploy_daemon_thread(
        self,
        func: Optional[Callable] = None,
        runner: Optional[Any] = None,
        **kwargs,
    ) -> Dict[str, str]:
        """Deploy in daemon thread mode."""
        self._logger.info("Deploying FastAPI service in daemon thread mode...")

        # Create FastAPI app using factory
        app = FastAPIAppFactory.create_app(
            func=func,
            runner=runner,
            mode=DeploymentMode.DAEMON_THREAD,
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
        await self._wait_for_server_ready()

        self._is_running = True
        self._deploy_id = f"daemon_{self.host}_{self.port}"

        self._logger.info(
            f"FastAPI service started at http://{self.host}:{self.port}",
        )

        return {
            "deploy_id": self._deploy_id,
            "url": f"http://{self.host}:{self.port}",
        }

    async def _deploy_detached_process(
        self,
        func: Optional[Callable] = None,
        runner: Optional[Any] = None,
        **kwargs,
    ) -> Dict[str, str]:
        """Deploy in detached process mode."""
        self._logger.info(
            "Deploying FastAPI service in detached process mode...",
        )

        # Create detached script
        script_path = await self._create_detached_script(
            func=func,
            runner=runner,
            **kwargs,
        )

        try:
            # Start detached process
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

            self._is_running = True
            self._deploy_id = f"detached_{pid}"

            self._logger.info(
                f"FastAPI service started in detached process (PID: {pid})",
            )

            return {
                "deploy_id": self._deploy_id,
                "url": f"http://{self.host}:{self.port}",
            }

        except Exception as e:
            # Cleanup on failure
            if script_path and os.path.exists(script_path):
                try:
                    os.remove(script_path)
                except OSError:
                    pass
            raise e

    async def _create_detached_script(
        self,
        func: Optional[Callable] = None,
        runner: Optional[Any] = None,
        endpoint_path: str = "/process",
        response_type: str = "sse",
        stream: bool = True,
        services_config: Optional[ServicesConfig] = None,
        **kwargs,
    ) -> str:
        """Create detached startup script."""
        # Generate script content using template
        runner_code = ""
        func_code = ""
        services_config_code = ""

        if runner:
            runner_code = self.template_manager.create_runner_setup_code(
                "runner",
            )

        if func:
            func_code = self.template_manager.create_func_setup_code("func")

        if services_config:
            services_config_code = (
                self.template_manager.create_services_config_code(
                    services_config.model_dump(),
                )
            )

        script_content = self.template_manager.render_detached_script_template(
            endpoint_path=endpoint_path,
            host=self.host,
            port=self.port,
            stream_enabled=stream,
            response_type=response_type,
            runner_code=runner_code,
            func_code=func_code,
            services_config=services_config_code,
        )

        # Write script to temporary file
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".py",
            prefix="agentscope_detached_",
            delete=False,
        ) as f:
            f.write(script_content)
            script_path = f.name

        return script_path

    async def stop(self) -> None:
        """Stop the FastAPI service (unified method for all modes)."""
        if not self._is_running:
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
        self._is_running = False
        self._logger.info("FastAPI daemon thread service stopped successfully")

    async def _stop_detached_process(self):
        """Stop detached process mode service."""
        self._logger.info("Stopping FastAPI detached process service...")

        if self._detached_process_pid:
            await self.process_manager.stop_process_gracefully(
                self._detached_process_pid,
            )

        await self._cleanup_detached_process()
        self._is_running = False
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

    def deploy_sync(
        self,
        func: Optional[Callable] = None,
        runner: Optional[Any] = None,
        mode: DeploymentMode = DeploymentMode.DAEMON_THREAD,
        **kwargs: Any,
    ) -> Dict[str, str]:
        """Synchronous version of deploy method."""
        return asyncio.run(
            self._deploy_async(
                func=func,
                runner=runner,
                mode=mode,
                **kwargs,
            ),
        )

    async def deploy_detached(
        self,
        func: Optional[Callable] = None,
        runner: Optional[Any] = None,
        **kwargs: Any,
    ) -> Dict[str, str]:
        """Deploy in detached process mode (convenience method)."""
        return await self._deploy_async(
            func=func,
            runner=runner,
            mode=DeploymentMode.DETACHED_PROCESS,
            **kwargs,
        )

    def _is_server_ready(self) -> bool:
        """Check if the server is ready to accept connections."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.1)
                result = s.connect_ex((self.host, self.port))
                return result == 0
        except Exception:
            return False

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
        if not self._is_running:
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
            "deploy_id": self._deploy_id,
            "host": self.host,
            "port": self.port,
            "is_running": self.is_service_running(),
            "mode": "detached_process"
            if self._detached_process_pid
            else "daemon_thread",
            "pid": self._detached_process_pid,
            "url": f"http://{self.host}:{self.port}"
            if self._is_running
            else None,
        }
