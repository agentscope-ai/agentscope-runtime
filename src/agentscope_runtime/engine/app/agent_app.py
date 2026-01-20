# -*- coding: utf-8 -*-
# flake8: noqa: E501
import logging
import os
import types
import platform
import subprocess
import shlex
from typing import Optional, Callable, List

import uvicorn
from pydantic import BaseModel

from .base_app import BaseApp
from ..deployers import DeployManager
from ..deployers.adapter.a2a import (
    A2AFastAPIDefaultAdapter,
    AgentCardWithRuntimeConfig,
    extract_a2a_config,
)
from ..deployers.adapter.responses.response_api_protocol_adapter import (
    ResponseAPIDefaultAdapter,
)
from ..deployers.adapter.agui import AGUIDefaultAdapter, AGUIAdaptorConfig
from ..deployers.utils.deployment_modes import DeploymentMode
from ..deployers.utils.service_utils.fastapi_factory import FastAPIAppFactory
from ..runner import Runner
from ..schemas.agent_schemas import AgentRequest
from ...version import __version__

logger = logging.getLogger(__name__)
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8080"))


class AgentApp(BaseApp):
    """
    The AgentApp class represents an application that runs as an agent.
    """

    def __init__(
        self,
        *,
        app_name: str = "",
        app_description: str = "",
        endpoint_path: str = "/process",
        response_type: str = "sse",
        stream: bool = True,
        request_model: Optional[type[BaseModel]] = AgentRequest,
        before_start: Optional[Callable] = None,
        after_finish: Optional[Callable] = None,
        broker_url: Optional[str] = None,
        backend_url: Optional[str] = None,
        runner: Optional[Runner] = None,
        enable_embedded_worker: bool = False,
        a2a_config: Optional["AgentCardWithRuntimeConfig"] = None,
        agui_config: Optional[AGUIAdaptorConfig] = None,
        **kwargs,
    ):
        """
        Initialize the AgentApp.

        Args:
            app_name: Name of the agent application
            app_description: Description of the agent application
            endpoint_path: API endpoint path for processing requests
            response_type: Type of response (default: "sse")
            stream: Whether to enable streaming responses
            request_model: Request model class
            before_start: Callback function to execute before starting
            after_finish: Callback function to execute after finishing
            broker_url: URL for message broker
            backend_url: URL for backend service
            runner: Optional runner instance
            enable_embedded_worker: Whether to enable embedded worker
            a2a_config: Optional A2A runtime configuration.
                Must be an ``AgentCardWithRuntimeConfig`` instance, which
                contains ``agent_card`` (AgentCard object or dict) and runtime
                settings (host, port, registry, task_timeout, etc.).

                Example::

                    from a2a.types import AgentCapabilities
                    from agentscope_runtime.engine.deployers.adapter.a2a import (
                        AgentCardWithRuntimeConfig,
                    )

                    config = AgentCardWithRuntimeConfig(
                        agent_card={
                            "name": "MyAgent",
                            "version": "1.0.0",
                            "description": "My agent",
                            "url": "http://localhost:8080",
                            "capabilities": AgentCapabilities(),
                            "default_input_modes": ["text"],
                            "default_output_modes": ["text"],
                            "skills": [],
                        },
                        registry=[nacos_registry],
                        task_timeout=120,
                    )
            agui_config: Config for AGUI adaptor.
            **kwargs: Additional keyword arguments passed to FastAPI app
        """

        self.endpoint_path = endpoint_path
        self.response_type = response_type
        self.stream = stream
        self.request_model = request_model
        self.before_start = before_start
        self.after_finish = after_finish
        self.broker_url = broker_url
        self.backend_url = backend_url
        self.enable_embedded_worker = enable_embedded_worker

        self._runner = runner
        self.custom_endpoints = []  # Store custom endpoints

        # Custom Handlers
        self._query_handler: Optional[Callable] = None
        self._init_handler: Optional[Callable] = None
        self._shutdown_handler: Optional[Callable] = None
        self._framework_type: Optional[str] = None

        # Prepare A2A protocol adapter configuration
        a2a_config = extract_a2a_config(a2a_config=a2a_config)

        a2a_protocol = A2AFastAPIDefaultAdapter(
            agent_name=app_name,
            agent_description=app_description,
            a2a_config=a2a_config,
        )

        response_protocol = ResponseAPIDefaultAdapter()
        agui_protocol = AGUIDefaultAdapter(config=agui_config)
        self.protocol_adapters = [
            a2a_protocol,
            response_protocol,
            agui_protocol,
        ]

        self._app_kwargs = {
            "title": "Agent Service",
            "version": __version__,
            "description": "Production-ready Agent Service API",
            **kwargs,
        }

        super().__init__(
            broker_url=broker_url,
            backend_url=backend_url,
        )

        # Store custom endpoints for deployment
        # FastAPIAppFactory will handle adding them to FastAPI

    def init(self, func):
        """Register init hook (support async and sync functions)."""
        self._init_handler = func
        return func

    def query(self, framework: Optional[str] = "agentscope"):
        """
        Register run hook and optionally specify agent framework.
        Allowed framework values: 'agentscope', 'autogen', 'agno', 'langgraph'.
        """

        allowed_frameworks = {"agentscope", "autogen", "agno", "langgraph"}
        if framework not in allowed_frameworks:
            raise ValueError(f"framework must be one of {allowed_frameworks}")

        def decorator(func):
            self._query_handler = func
            self._framework_type = framework
            return func

        return decorator

    def shutdown(self, func):
        """Register shutdown hook (support async and sync functions)."""
        self._shutdown_handler = func
        return func

    def _build_runner(self):
        if self._runner is None:
            self._runner = Runner()

        if self._framework_type is not None:
            self._runner.framework_type = self._framework_type

        if self._query_handler is not None:
            self._runner.query_handler = types.MethodType(
                self._query_handler,
                self._runner,
            )

        if self._init_handler is not None:
            self._runner.init_handler = types.MethodType(
                self._init_handler,
                self._runner,
            )

        if self._shutdown_handler is not None:
            self._runner.shutdown_handler = types.MethodType(
                self._shutdown_handler,
                self._runner,
            )

    def run(
        self,
        host=HOST,
        port=PORT,
        web_ui=False,
        **kwargs,
    ):
        """
        Launch the AgentApp HTTP API server.

        This method starts a FastAPI server for the agent service.
        Optionally, it can also launch a browser-based Web UI for
        interacting with the agent.

        Note:
        If `web_ui=True` and this is the **first time** launching the Web UI,
        additional time may be required to initialize. This happens because the
        underlying Node.js command (`npx @agentscope-ai/chat
        agentscope-runtime-webui`) might install dependencies and set up
        the runtime environment.

        Args:
            host (str): Host address to bind to. Default "0.0.0.0".
            port (int): Port number to serve the application on. Default 8080.
            web_ui (bool): If True, launches the Agentscope Web UI in a
                separate process, pointing it to the API endpoint. This
                allows interactive use via browser. Default False.
            **kwargs: Additional keyword arguments passed to FastAPIAppFactory
                when creating the FastAPI application.

        Example:
            >>> app = AgentApp(app_name="MyAgent")
            >>> app.chat(host="127.0.0.1", port=8080, web_ui=True)
        """
        # Build runner
        self._build_runner()

        try:
            logger.info(
                "Starting AgentApp with FastAPIAppFactory...",
            )
            fastapi_app = self.get_fastapi_app(**kwargs)

            logger.info(f"Starting server on {host}:{port}")

            if web_ui:
                webui_url = f"http://{host}:{port}{self.endpoint_path}"
                cmd = (
                    f"npx @agentscope-ai/chat agentscope-runtime-webui "
                    f"--url {webui_url}"
                )
                logger.info(f"WebUI started at {webui_url}")
                logger.info(
                    "Note: First WebUI launch may take extra time "
                    "as dependencies are installed.",
                )

                cmd_kwarg = {}
                if platform.system() == "Windows":
                    cmd_kwarg.update({"shell": True})
                else:
                    cmd = shlex.split(cmd)
                with subprocess.Popen(cmd, **cmd_kwarg):
                    uvicorn.run(
                        fastapi_app,
                        host=host,
                        port=port,
                        log_level="info",
                        access_log=True,
                    )
            else:
                uvicorn.run(
                    fastapi_app,
                    host=host,
                    port=port,
                    log_level="info",
                    access_log=True,
                )

        except KeyboardInterrupt:
            logger.info(
                "KeyboardInterrupt received, shutting down...",
            )

    def get_fastapi_app(self, **kwargs):
        """Get the FastAPI application"""

        self._build_runner()
        mode = kwargs.pop("mode", DeploymentMode.DAEMON_THREAD)

        return FastAPIAppFactory.create_app(
            runner=self._runner,
            endpoint_path=self.endpoint_path,
            request_model=self.request_model,
            response_type=self.response_type,
            stream=self.stream,
            before_start=self.before_start,
            after_finish=self.after_finish,
            mode=mode,
            protocol_adapters=self.protocol_adapters,
            custom_endpoints=self.custom_endpoints,
            broker_url=self.broker_url,
            backend_url=self.backend_url,
            enable_embedded_worker=self.enable_embedded_worker,
            app_kwargs=self._app_kwargs,
            **kwargs,
        )

    async def deploy(self, deployer: DeployManager, **kwargs):
        """Deploy the agent app with custom endpoints support"""
        # Pass custom endpoints and tasks to the deployer
        # Build runner
        self._build_runner()

        deploy_kwargs = {
            "app": self,
            "custom_endpoints": self.custom_endpoints,
            "runner": self._runner,
            "endpoint_path": self.endpoint_path,
            "stream": self.stream,
            "protocol_adapters": self.protocol_adapters,
        }
        deploy_kwargs.update(kwargs)
        return await deployer.deploy(**deploy_kwargs)

    def endpoint(self, path: str, methods: Optional[List[str]] = None):
        """Decorator to register custom endpoints"""

        if methods is None:
            methods = ["POST"]

        def decorator(func: Callable):
            endpoint_info = {
                "path": path,
                "handler": func,
                "methods": methods,
                "module": getattr(func, "__module__", None),
                "function_name": getattr(func, "__name__", None),
            }
            self.custom_endpoints.append(endpoint_info)
            return func

        return decorator

    def task(self, path: str, queue: str = "default"):
        """Decorator to register custom task endpoints"""

        def decorator(func: Callable):
            # Store task configuration for FastAPIAppFactory to handle
            task_info = {
                "path": path,
                "handler": func,  # Store original function
                "methods": ["POST"],
                "module": getattr(func, "__module__", None),
                "function_name": getattr(func, "__name__", None),
                "queue": queue,
                "task_type": True,  # Mark as task endpoint
                "original_func": func,
            }
            self.custom_endpoints.append(
                task_info,
            )  # Add to endpoints for deployment

            return func

        return decorator
