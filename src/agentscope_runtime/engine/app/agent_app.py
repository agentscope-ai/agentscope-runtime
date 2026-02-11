# -*- coding: utf-8 -*-
import asyncio
import inspect
import json
import logging
import os
import platform
import shlex
import subprocess
import types
from contextlib import asynccontextmanager, AsyncExitStack
from typing import Any, Callable, Dict, List, Optional, Type

import uvicorn
from a2a.types import A2ARequest
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.params import Depends as DependsClass
from fastapi.responses import StreamingResponse
from starlette.types import Lifespan
from pydantic import BaseModel

from agentscope_runtime.common.utils.deprecation import deprecated
from agentscope_runtime.engine.deployers.adapter.protocol_adapter import (
    ProtocolAdapter,
)
from agentscope_runtime.engine.schemas.response_api import ResponseAPI
from ...version import __version__
from ..deployers import DeployManager
from ..deployers.adapter.a2a import (
    A2AFastAPIDefaultAdapter,
    AgentCardWithRuntimeConfig,
    extract_a2a_config,
)
from ..deployers.adapter.agui import AGUIDefaultAdapter, AGUIAdaptorConfig
from ..deployers.adapter.responses.response_api_protocol_adapter import (
    ResponseAPIDefaultAdapter,
)
from ..deployers.utils.deployment_modes import DeploymentMode
from ..deployers.utils.service_utils.interrupt import (
    BaseInterruptBackend,
    InterruptMixin,
    RedisInterruptBackend,
    LocalInterruptBackend,
)
from ..deployers.utils.service_utils.routing import (
    UnifiedRoutingMixin,
)
from ..runner import Runner
from ..schemas.agent_schemas import AgentRequest

logger = logging.getLogger(__name__)

HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8080"))


class AgentApp(FastAPI, UnifiedRoutingMixin, InterruptMixin):
    """
    Agent application integrating FastAPI and Runner
    with support for distributed interrupts.
    """

    _REF_TEMPLATE = "#/components/schemas/{model}"

    def openapi(self) -> dict[str, Any]:
        """
        Generate OpenAPI schema with protocol-specific components.
        """
        openapi_schema = super().openapi()

        if self.protocol_adapters:
            if any(
                isinstance(adapter, A2AFastAPIDefaultAdapter)
                for adapter in self.protocol_adapters
            ):
                self._inject_schema(
                    openapi_schema,
                    "A2ARequest",
                    A2ARequest.model_json_schema(
                        ref_template=self._REF_TEMPLATE,
                    ),
                )
            if any(
                isinstance(adapter, ResponseAPIDefaultAdapter)
                for adapter in self.protocol_adapters
            ):
                self._inject_schema(
                    openapi_schema,
                    "ResponseAPI",
                    ResponseAPI.model_json_schema(
                        ref_template=self._REF_TEMPLATE,
                    ),
                )

        self._inject_schema(
            openapi_schema,
            "AgentRequest",
            AgentRequest.model_json_schema(
                ref_template=self._REF_TEMPLATE,
            ),
        )

        return openapi_schema

    @staticmethod
    def _inject_schema(
        openapi_schema: dict[str, Any],
        schema_name: str,
        schema_definition: dict[str, Any],
    ) -> None:
        """Insert schema definition (and nested defs) into OpenAPI."""
        components = openapi_schema.setdefault("components", {})
        component_schemas = components.setdefault("schemas", {})

        defs = schema_definition.pop("$defs", {})
        for def_name, def_schema in defs.items():
            component_schemas.setdefault(def_name, def_schema)

        component_schemas[schema_name] = schema_definition

    def __init__(
        self,
        *,
        app_name: str = "AgentScope Runtime API",
        app_description: str = "",
        endpoint_path: str = "/process",
        response_type: str = "sse",
        stream: bool = True,
        request_model: Optional[Type[BaseModel]] = AgentRequest,
        before_start: Optional[Callable] = None,
        after_finish: Optional[Callable] = None,
        broker_url: Optional[str] = None,
        backend_url: Optional[str] = None,
        runner: Optional[Runner] = None,
        enable_embedded_worker: bool = False,
        a2a_config: Optional["AgentCardWithRuntimeConfig"] = None,
        agui_config: Optional[AGUIAdaptorConfig] = None,
        interrupt_backend: Optional[BaseInterruptBackend] = None,
        interrupt_redis_url: Optional[str] = None,
        lifespan: Optional[Lifespan[Any]] = None,
        mode: DeploymentMode = DeploymentMode.DAEMON_THREAD,
        protocol_adapters: Optional[list[ProtocolAdapter]] = None,
        custom_endpoints: Optional[List[Dict]] = None,
        **kwargs: Any,
    ):
        self._user_lifespan = lifespan

        fastapi_kwargs = {
            "title": app_name,
            "description": app_description,
            "version": __version__,
            "lifespan": self._lifespan_manager,
            **kwargs,
        }

        FastAPI.__init__(self, **fastapi_kwargs)

        self.init_routing_manager(broker_url, backend_url)

        self.endpoint_path = endpoint_path
        self.response_type = response_type
        self.stream = stream
        self.request_model = request_model
        self.before_start = before_start
        self.after_finish = after_finish
        self.broker_url = broker_url
        self.backend_url = backend_url
        self.enable_embedded_worker = enable_embedded_worker

        self._query_handler: Optional[Callable] = None
        self._init_handler: Optional[Callable] = None
        self._shutdown_handler: Optional[Callable] = None
        self._framework_type: Optional[str] = None

        if runner:
            self._runner = runner
            self._add_endpoint_router()
        else:
            self._runner = Runner()

        self.deployment_mode = mode

        if protocol_adapters:
            self.protocol_adapters: List[Any] = protocol_adapters
        else:
            self.protocol_adapters = self._init_protocol_adapters(
                app_name,
                app_description,
                a2a_config,
                agui_config,
            )

        self._app_kwargs = {
            "title": "Agent Service",
            "version": __version__,
            "description": "Production-ready Agent Service API",
            **kwargs,
        }

        self._setup_interrupt_service(
            interrupt_backend,
            interrupt_redis_url,
        )

        self._setup_builtin_routes()

        if custom_endpoints:
            self.restore_custom_endpoints(custom_endpoints)

        self._add_middleware()

    def _setup_interrupt_service(
        self,
        backend: Optional[BaseInterruptBackend],
        redis_url: Optional[str],
    ) -> None:
        """Setup the interrupt service backend based on configuration."""
        if backend:
            logger.info(
                "Initializing interrupt service using an "
                "externally provided backend instance.",
            )
            self._init_interrupt_service(backend)
        elif redis_url:
            logger.info(
                "Initializing distributed interrupt service "
                "with Redis backend.",
            )
            self._init_interrupt_service(RedisInterruptBackend(redis_url))
        else:
            logger.info(
                "No distributed backend configuration detected. "
                "Falling back to LocalInterruptBackend for "
                "single-node execution.",
            )
            self._init_interrupt_service(LocalInterruptBackend())

    @asynccontextmanager
    async def _internal_framework_lifespan(self, app: FastAPI):
        """
        Lifecycle manager for internal runner and hooks.
        """
        # pylint: disable=too-many-branches
        self._build_runner()
        try:
            # aexit any possible running instances before set up
            # runner
            await self._runner.__aexit__(None, None, None)
            await self._runner.__aenter__()

            if self.before_start:
                if asyncio.iscoroutinefunction(self.before_start):
                    await self.before_start(app)
                else:
                    self.before_start(app)

            func = (
                self._runner.stream_query
                if self.stream
                else self._runner.query
            )
            for adapter in self.protocol_adapters:
                adapter.add_endpoint(app=self, func=func)

            if self.enable_embedded_worker and self.celery_app:
                self.start_embedded_celery_worker()

            yield

        finally:
            if self.after_finish:
                try:
                    if asyncio.iscoroutinefunction(self.after_finish):
                        await self.after_finish(app)
                    else:
                        self.after_finish(app)
                except Exception as e:
                    logger.error(f"Error in after_finish hook: {e}")
            if self._runner:
                try:
                    await self._runner.__aexit__(None, None, None)
                except Exception as e:
                    logger.error(f"Warning: Error during runner cleanup: {e}")
            if self._interrupt_backend:
                try:
                    await self.close_interrupt_service()
                except Exception as e:
                    logger.error(
                        "Warning: Error occurred while "
                        f"closing the interrupt service: {e}",
                    )

    @asynccontextmanager
    async def _lifespan_manager(self, app: FastAPI):
        """
        Main lifespan orchestrator combining internal and user logic.
        """
        try:
            async with AsyncExitStack() as stack:
                await stack.enter_async_context(
                    self._internal_framework_lifespan(app),
                )

                user_state = {}
                if self._user_lifespan:
                    user_state = await stack.enter_async_context(
                        self._user_lifespan(app),
                    )

                yield user_state

        except Exception as e:
            logger.error(f"Application runtime error: {e}")
            raise

    def _init_protocol_adapters(
        self,
        app_name,
        app_description,
        a2a_config,
        agui_config,
    ) -> List[Any]:
        """Initialize supported protocol adapters for the agent."""
        a2a_config = extract_a2a_config(a2a_config=a2a_config)
        return [
            A2AFastAPIDefaultAdapter(
                agent_name=app_name,
                agent_description=app_description,
                a2a_config=a2a_config,
            ),
            ResponseAPIDefaultAdapter(),
            AGUIDefaultAdapter(config=agui_config),
        ]

    def _add_middleware(self):
        """Add middleware based on deployment mode."""
        # Common middleware
        self.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        @self.middleware("http")
        async def dynamic_deployment_middleware(request: Request, call_next):
            response = await call_next(request)

            if self.deployment_mode == DeploymentMode.DETACHED_PROCESS:
                response.headers["X-Process-Mode"] = "detached"

            elif self.deployment_mode == DeploymentMode.STANDALONE:
                response.headers["X-Deployment-Mode"] = "standalone"

            return response

    def _setup_builtin_routes(self):
        """Register health check and information discovery routes."""

        @self.get("/health")
        @UnifiedRoutingMixin.internal_route
        async def health_check():
            """Health check endpoint."""
            status = {
                "status": "healthy",
                "mode": self.deployment_mode.value,
            }

            # Add service health checks
            if self._runner:
                status["runner"] = "ready"
            else:
                status["runner"] = "not_ready"

            return status

        @self.get("/")
        @UnifiedRoutingMixin.internal_route
        async def root():
            return {
                "service": "AgentScope Runtime",
                "mode": self.deployment_mode.value,
                "endpoints": {
                    "process": self.endpoint_path,
                    "stream": (
                        f"{self.endpoint_path}/stream" if self.stream else None
                    ),
                    "health": "/health",
                },
            }

        self._add_process_control_endpoints()

    def _add_process_control_endpoints(self):
        """Add process control endpoints for detached mode."""

        @self.post("/shutdown")
        @UnifiedRoutingMixin.internal_route
        async def shutdown_process_simple():
            """Gracefully shutdown the process (simple endpoint)."""
            import signal

            async def delayed_shutdown():
                await asyncio.sleep(0.5)
                os.kill(os.getpid(), signal.SIGTERM)

            asyncio.create_task(delayed_shutdown())
            return {"status": "shutting down"}

        @self.post("/admin/shutdown")
        @UnifiedRoutingMixin.internal_route
        async def shutdown_process():
            """Gracefully shutdown the process."""
            import signal

            # Schedule shutdown after response
            async def delayed_shutdown():
                await asyncio.sleep(1)
                os.kill(os.getpid(), signal.SIGTERM)

            asyncio.create_task(delayed_shutdown())
            return {"message": "Shutdown initiated"}

        @self.get("/admin/status")
        @UnifiedRoutingMixin.internal_route
        async def get_process_status():
            """Get process status information."""
            import psutil

            proc = psutil.Process(os.getpid())
            return {
                "pid": os.getpid(),
                "status": proc.status(),
                "memory_usage": proc.memory_info().rss,
                "cpu_percent": proc.cpu_percent(),
                "uptime": proc.create_time(),
            }

    async def _stream_generator(self, request: dict, **kwargs):
        """
        Dispatch stream generation based on interrupt backend status.
        """
        if not self._interrupt_backend:
            try:
                if not self._runner:
                    yield f"data: {json.dumps({'error': 'No runner'})}\n\n"
                    return

                async for chunk in self._common_stream_generator(
                    request,
                    **kwargs,
                ):
                    yield chunk

            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"

        else:
            async for chunk in self._stream_generator_with_interrupt(
                request,
                **kwargs,
            ):
                yield chunk

    async def _stream_generator_with_interrupt(
        self,
        request: dict,
        **kwargs,
    ):
        """
        Execute stream generation wrapped with interrupt management.
        """
        try:
            agent_req = AgentRequest(**request)
            async for chunk in self.run_and_stream(
                agent_req.user_id,
                agent_req.session_id,
                self._common_stream_generator,
                request,
                **kwargs,
            ):
                yield chunk
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    async def _common_stream_generator(self, request: dict, **kwargs):
        """Yield standard SSE formatted chunks from the runner."""
        if not self._runner:
            raise RuntimeError("Runner is not initialized.")

        async for chunk in self._runner.stream_query(request, **kwargs):
            if hasattr(chunk, "model_dump_json"):
                data = chunk.model_dump_json()
            elif hasattr(chunk, "json"):
                data = chunk.json()
            else:
                data = json.dumps({"text": str(chunk)})
            yield f"data: {data}\n\n"

    @deprecated(
        reason=(
            "Manual initialization is deprecated. "
            "Lifecycle management has been unified "
            "under FastAPI's 'lifespan' parameter. "
            "Please move your startup logic to "
            "a lifespan context manager."
        ),
        alternative="the 'lifespan' argument in AgentApp constructor",
        since="1.1.0",
        removed_in="1.2.0",
    )
    def init(self, func: Callable) -> Callable:
        """Register init hook (support async and sync functions)."""
        self._init_handler = func
        self._build_runner()
        return func

    def query(self, framework: Optional[str] = "agentscope"):
        """
        Register run hook and optionally specify agent framework.
        Allowed framework values: 'agentscope', 'autogen', 'agno', 'langgraph'.
        """
        allowed_frameworks = {"agentscope", "autogen", "agno", "langgraph"}
        if framework not in allowed_frameworks:
            raise ValueError(f"framework must be one of {allowed_frameworks}")

        def decorator(func: Callable):
            self._query_handler = func
            self._framework_type = framework

            self._build_runner()
            self._add_endpoint_router()

            return func

        return decorator

    @deprecated(
        reason=(
            "Manual shutdown is deprecated. "
            "Lifecycle management has been unified "
            "under FastAPI's 'lifespan' parameter. "
            "Please move your shutdown logic to "
            "a lifespan context manager."
        ),
        alternative="the 'lifespan' argument in AgentApp constructor",
        since="1.1.0",
        removed_in="1.2.0",
    )
    def shutdown(self, func: Callable) -> Callable:
        """Register shutdown hook (support async and sync functions)."""
        self._shutdown_handler = func
        self._build_runner()
        return func

    def _build_runner(self):
        """Bind decorated handlers to the internal Runner instance."""
        if self._runner is None:
            self._runner = Runner()

        if self._framework_type:
            self._runner.framework_type = self._framework_type

        handlers = [
            ("query_handler", self._query_handler),
            ("init_handler", self._init_handler),
            ("shutdown_handler", self._shutdown_handler),
        ]
        for attr, handler in handlers:
            if handler:
                setattr(
                    self._runner,
                    attr,
                    types.MethodType(handler, self._runner),
                )

    def _add_endpoint_router(self):
        """
        Dynamically construct and register the main inference endpoint.
        """
        if not self._runner:
            return

        self.router.routes = [
            route
            for route in self.router.routes
            if not (
                hasattr(route, "path") and route.path == self.endpoint_path
            )
        ]

        user_func = self._runner.query_handler

        async def agent_api(request: dict, **kwargs):
            return StreamingResponse(
                self._stream_generator(request, **kwargs),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                },
            )

        full_sig = inspect.signature(user_func)
        new_params = [
            inspect.Parameter(
                "request",
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                annotation=dict,
            ),
        ]

        for _, param in full_sig.parameters.items():
            if isinstance(param.default, DependsClass):
                new_params.append(param)

        agent_api.__signature__ = full_sig.replace(parameters=new_params)
        agent_api.__name__ = user_func.__name__
        agent_api.__doc__ = user_func.__doc__

        self.post(
            self.endpoint_path,
            openapi_extra={
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {
                                "$ref": "#/components/schemas/AgentRequest",
                            },
                        },
                    },
                    "required": True,
                    "description": "Agent API Request Format. "
                    "See https://runtime.agentscope.io/en/protocol.html for "
                    "more details.",
                },
            },
            tags=["agent-api"],
        )(agent_api)

    def _apply_runtime_configs(self, kwargs: dict):
        """
        Apply runtime configuration updates and synchronize internal services.
        """
        self.stream = kwargs.pop("stream", self.stream)
        self.protocol_adapters = kwargs.pop(
            "protocol_adapters",
            self.protocol_adapters,
        )
        self.enable_embedded_worker = kwargs.pop(
            "embed_task_processor",
            self.enable_embedded_worker,
        )
        self.deployment_mode = kwargs.pop("mode", self.deployment_mode)

        if "runner" in kwargs:
            self._runner = kwargs.pop("runner")
            self._add_endpoint_router()

        if "endpoint_path" in kwargs:
            self.router.routes = [
                route
                for route in self.router.routes
                if not (
                    hasattr(route, "path") and route.path == self.endpoint_path
                )
            ]
            self.endpoint_path = kwargs.pop("endpoint_path")
            self._add_endpoint_router()

        if "custom_endpoints" in kwargs:
            custom_endpoints = kwargs.pop("custom_endpoints")
            self.restore_custom_endpoints(custom_endpoints)

    def run(self, host=HOST, port=PORT, web_ui=False, **kwargs):
        """Launch the application server and optional Web UI."""

        self._apply_runtime_configs(kwargs)

        try:
            logger.info(
                "Starting AgentApp...",
            )
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
                        self,
                        host=host,
                        port=port,
                        log_level="info",
                        access_log=True,
                    )
            else:
                uvicorn.run(
                    self,
                    host=host,
                    port=port,
                    log_level="info",
                    access_log=True,
                )

        except KeyboardInterrupt:
            logger.info(
                "KeyboardInterrupt received, shutting down...",
            )

    async def deploy(self, deployer: DeployManager, **kwargs):
        """Deploy the agent app"""
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
