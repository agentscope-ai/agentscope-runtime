# -*- coding: utf-8 -*-
import asyncio
import logging
import socket
import threading
import time
from typing import Optional, Dict, Any

from .base import DeployManager


class LocalDeployManager(DeployManager):
    def __init__(self, host: str = "localhost", port: int = 8090):
        super().__init__()
        self.host = host
        self.port = port
        self._server = None
        self._server_task = None
        self._server_thread = None  # Add thread for server
        self._is_running = False
        self._logger = logging.getLogger(__name__)
        self._app = None
        self._startup_timeout = 30  # seconds
        self._shutdown_timeout = 10  # seconds
        self._setup_logging()

    def _setup_logging(self):
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )

        app_logger = logging.getLogger("app")
        app_logger.setLevel(logging.INFO)

        file_handler = logging.handlers.RotatingFileHandler(
            "app.log",
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
        )
        file_handler.setFormatter(formatter)
        app_logger.addHandler(file_handler)
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        app_logger.addHandler(console_handler)

        access_logger = logging.getLogger("access")
        access_logger.setLevel(logging.INFO)
        access_file_handler = logging.handlers.RotatingFileHandler(
            "access.log",
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
        )
        access_file_handler.setFormatter(
            logging.Formatter("%(asctime)s - %(message)s"),
        )
        access_logger.addHandler(access_file_handler)

        self.app_logger = app_logger
        self.access_logger = access_logger

    def deploy_sync(
        self,
        app,
        **kwargs: Any,
    ) -> Dict[str, str]:
        """
        Deploy the agent as a FastAPI service (synchronous version).

        Args:
            app: Agent app

        Returns:
            Dict[str, str]: Dictionary containing deploy_id and url of the
            deployed service

        Raises:
            RuntimeError: If deployment fails
        """
        return asyncio.run(
            self._deploy_async(
                app=app,
                **kwargs,
            ),
        )

    async def deploy(
        self,
        app,
        **kwargs: Any,
    ) -> Dict[str, str]:
        """
        Deploy the agent as a FastAPI service (asynchronous version).

        Args:
            app: Agent app

        Returns:
            Dict[str, str]: Dictionary containing deploy_id and url of the
            deployed service

        Raises:
            RuntimeError: If deployment fails
        """
        return await self._deploy_async(
            app=app,
            **kwargs,
        )

    async def _deploy_async(
        self,
        app,
        **kwargs: Any,
    ) -> Dict[str, str]:
        if self._is_running:
            raise RuntimeError("Service is already running")

        try:
            self._logger.info("Starting FastAPI service deployment...")

            self.kwargs = kwargs

            # Create FastAPI app
            self._app = app

            # TODO: support protocol_adapter
            # # Support extension protocol
            # if protocol_adapters:
            #     for protocol_adapter in protocol_adapters:
            #         protocol_adapter.add_endpoint(app=self._app, func=func)

            # Configure uvicorn server
            config = {
                "host": self.host,
                "port": self.port,
                "log_level": "info",
                "access_log": False,
                "timeout_keep_alive": 30,
                "embed_task_processor": True,
            }

            def run_with_event_loop(app_instance, **run_kwargs):
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                app_instance.run(**run_kwargs)

            # Run the server in a separate thread
            self._server_thread = threading.Thread(
                target=run_with_event_loop,
                args=(self._app,),
                kwargs=config,
            )
            self._server = self._app.server

            self._server_thread.daemon = (
                True  # Ensure thread doesn't block exit
            )
            self._server_thread.start()

            # Wait for server to start with timeout
            start_time = time.time()
            while not self._is_server_ready():
                if time.time() - start_time > self._startup_timeout:
                    # Clean up the thread if server fails to start
                    if self._server:
                        self._server.should_exit = True
                    self._server_thread.join(timeout=self._shutdown_timeout)
                    raise RuntimeError(
                        f"Server startup timeout after "
                        f"{self._startup_timeout} seconds",
                    )
                await asyncio.sleep(0.1)

            self._is_running = True
            url = f"http://{self.host}:{self.port}"
            self._logger.info(
                f"FastAPI service deployed successfully at {url}",
            )
            return {
                "deploy_id": self.deploy_id,
                "url": url,
            }

        except Exception as e:
            self._logger.error(f"Deployment failed: {e}")
            await self._cleanup_server()
            raise RuntimeError(f"Failed to deploy FastAPI service: {e}") from e

    def _is_server_ready(self) -> bool:
        """Check if the server is ready to accept connections."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.1)
                result = s.connect_ex((self.host, self.port))
                return result == 0
        except Exception:
            return False

    async def stop(self) -> None:
        """
        Stop the FastAPI service.

        Raises:
            RuntimeError: If stopping fails
        """
        if not self._is_running:
            self._logger.warning("Service is not running")
            return

        try:
            self._logger.info("Stopping FastAPI service...")

            # Stop the server gracefully
            if self._server:
                self._server.should_exit = True

            # Wait for the server thread to finish
            if self._server_thread and self._server_thread.is_alive():
                self._server_thread.join(timeout=self._shutdown_timeout)
                if self._server_thread.is_alive():
                    self._logger.warning(
                        "Server thread did not terminate, "
                        "potential resource leak",
                    )

            await self._cleanup_server()
            self._is_running = False
            self._logger.info("FastAPI service stopped successfully")

        except Exception as e:
            self._logger.error(f"Failed to stop service: {e}")
            raise RuntimeError(f"Failed to stop FastAPI service: {e}") from e

    async def _cleanup_server(self):
        """Clean up server resources."""
        self._server = None
        self._server_task = None
        self._server_thread = None
        self._app = None

    @property
    def is_running(self) -> bool:
        """Check if the service is currently running."""
        return self._is_running

    @property
    def service_url(self) -> Optional[str]:
        """Get the current service URL if running."""
        if self._is_running and self.port:
            return f"http://{self.host}:{self.port}"
        return None
