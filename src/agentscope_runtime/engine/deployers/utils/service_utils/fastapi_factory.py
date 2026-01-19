# -*- coding: utf-8 -*-
# pylint:disable=too-many-branches, unused-argument, too-many-return-statements
# pylint:disable=protected-access

import asyncio
import functools
import inspect
import json
import logging
from contextlib import asynccontextmanager
from dataclasses import asdict, is_dataclass
from typing import Optional, Callable, Type, Any, List, Dict

from a2a.types import A2ARequest
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel

from agentscope_runtime.engine.schemas.agent_schemas import AgentRequest
from agentscope_runtime.engine.schemas.response_api import ResponseAPI
from ..deployment_modes import DeploymentMode
from ...adapter.a2a.a2a_protocol_adapter import A2AFastAPIDefaultAdapter
from ...adapter.protocol_adapter import ProtocolAdapter
from ...adapter.responses.response_api_protocol_adapter import (
    ResponseAPIDefaultAdapter,
)

logger = logging.getLogger(__name__)


class _WrappedFastAPI(FastAPI):
    """FastAPI subclass that can dynamically augment OpenAPI schemas."""

    _REF_TEMPLATE = "#/components/schemas/{model}"

    def openapi(self) -> dict[str, Any]:
        """Generate OpenAPI schema with protocol-specific components."""
        openapi_schema = super().openapi()
        protocol_adapters = (
            getattr(self.state, "protocol_adapters", None) or []
        )

        if protocol_adapters:
            if any(
                isinstance(adapter, A2AFastAPIDefaultAdapter)
                for adapter in protocol_adapters
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
                for adapter in protocol_adapters
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


async def error_stream(e):
    yield (
        f"data: "
        f"{json.dumps({'error': f'Request parsing error: {str(e)}'})}\n\n"
    )


class FastAPIAppFactory:
    """Factory for creating FastAPI applications with unified architecture."""

    @staticmethod
    def create_app(
        func: Optional[Callable] = None,
        runner: Optional[Any] = None,
        endpoint_path: str = "/process",
        request_model: Optional[Type] = None,
        response_type: str = "sse",
        stream: bool = True,
        before_start: Optional[Callable] = None,
        after_finish: Optional[Callable] = None,
        mode: DeploymentMode = DeploymentMode.DAEMON_THREAD,
        protocol_adapters: Optional[list[ProtocolAdapter]] = None,
        custom_endpoints: Optional[
            List[Dict]
        ] = None,  # New parameter for custom endpoints
        # Celery parameters
        broker_url: Optional[str] = None,
        backend_url: Optional[str] = None,
        enable_embedded_worker: bool = False,
        app_kwargs: Optional[Dict] = None,
        **kwargs: Any,
    ) -> FastAPI:
        """Create a FastAPI application with unified architecture.

        Args:
            func: Custom processing function
            runner: Runner instance (for DAEMON_THREAD mode)
            endpoint_path: API endpoint path for the processing function
            request_model: Pydantic model for request validation
            response_type: Response type - "json", "sse", or "text"
            stream: Enable streaming responses
            before_start: Callback function called before server starts
            after_finish: Callback function called after server finishes
            mode: Deployment mode
            protocol_adapters: Protocol adapters
            custom_endpoints: List of custom endpoint configurations
            broker_url: Celery broker URL
            backend_url: Celery backend URL
            enable_embedded_worker: Whether to run embedded Celery worker
            app_kwargs: Additional keyword arguments for the FastAPI app
            **kwargs: Additional keyword arguments

        Returns:
            FastAPI application instance
        """

        # Initialize Celery mixin if broker and backend URLs are provided
        celery_mixin = None
        if broker_url and backend_url:
            try:
                from ....app.celery_mixin import CeleryMixin

                celery_mixin = CeleryMixin(
                    broker_url=broker_url,
                    backend_url=backend_url,
                )
            except ImportError:
                # CeleryMixin not available, will use fallback task processing
                celery_mixin = None

        # Create lifespan manager
        @asynccontextmanager
        async def lifespan(app: FastAPI):
            """Application lifespan manager."""
            # Startup
            try:
                await FastAPIAppFactory._handle_startup(
                    app,
                    mode,
                    runner,
                    before_start,
                    **kwargs,
                )
                yield
            finally:
                # Shutdown
                await FastAPIAppFactory._handle_shutdown(
                    app,
                    after_finish,
                    **kwargs,
                )

        # Create FastAPI app
        app = _WrappedFastAPI(lifespan=lifespan, **(app_kwargs or {}))

        # Store configuration in app state
        app.state.deployment_mode = mode
        app.state.stream_enabled = stream
        app.state.custom_func = func
        app.state.runner = runner
        app.state.response_type = response_type
        app.state.endpoint_path = endpoint_path
        app.state.protocol_adapters = protocol_adapters  # Store for later use
        app.state.custom_endpoints = (
            custom_endpoints or []
        )  # Store custom endpoints

        # Store Celery configuration
        app.state.celery_mixin = celery_mixin
        app.state.broker_url = broker_url
        app.state.backend_url = backend_url
        app.state.enable_embedded_worker = enable_embedded_worker

        # Add middleware
        FastAPIAppFactory._add_middleware(app, mode)

        # Add routes
        FastAPIAppFactory._add_routes(
            app,
            endpoint_path,
            request_model,
            stream,
            mode,
        )

        # Note: protocol_adapters will be added in _handle_startup
        # after runner is available

        return app

    @staticmethod
    async def _handle_startup(
        app: FastAPI,
        mode: DeploymentMode,
        external_runner: Optional[Any],
        before_start: Optional[Callable],
        **kwargs,
    ):
        """Handle application startup."""
        try:
            # aexit any possible running instances before set up
            # runner
            await app.state.runner.__aexit__(None, None, None)
            await app.state.runner.__aenter__()
        except Exception as e:
            logger.error(
                f"Warning: Error during runner setup: {e}",
            )

        # Call custom startup callback
        if before_start:
            if asyncio.iscoroutinefunction(before_start):
                await before_start(app, **kwargs)
            else:
                before_start(app, **kwargs)

        # Add protocol adapter endpoints after runner is available
        if (
            hasattr(app.state, "protocol_adapters")
            and app.state.protocol_adapters
        ):
            # Determine the effective function to use
            if hasattr(app.state, "custom_func") and app.state.custom_func:
                effective_func = app.state.custom_func
            elif hasattr(app.state, "runner") and app.state.runner:
                # Use stream_query if streaming is enabled, otherwise query
                if (
                    hasattr(app.state, "stream_enabled")
                    and app.state.stream_enabled
                ):
                    effective_func = app.state.runner.stream_query
                else:
                    effective_func = app.state.runner.query
            else:
                effective_func = None

            if effective_func:
                for protocol_adapter in app.state.protocol_adapters:
                    protocol_adapter.add_endpoint(app=app, func=effective_func)

        # Add custom endpoints after runner is available
        if (
            hasattr(app.state, "custom_endpoints")
            and app.state.custom_endpoints
        ):
            FastAPIAppFactory._add_custom_endpoints(app)

        # Start embedded Celery worker if enabled
        if (
            hasattr(app.state, "enable_embedded_worker")
            and app.state.enable_embedded_worker
            and hasattr(app.state, "celery_mixin")
            and app.state.celery_mixin
        ):
            # Start Celery worker in background thread
            import threading

            def start_celery_worker():
                try:
                    celery_mixin = app.state.celery_mixin

                    for ep in app.state.custom_endpoints:
                        if ep.get("task_type"):
                            func = ep["handler"]
                            queue = ep.get("queue", "celery")
                            if not hasattr(func, "celery_task"):
                                func.celery_task = (
                                    celery_mixin.register_celery_task(
                                        func,
                                        queue,
                                    )
                                )

                    # Get registered queues or use default
                    queues = (
                        list(celery_mixin.get_registered_queues())
                        if celery_mixin.get_registered_queues()
                        else ["celery"]
                    )
                    celery_mixin.run_task_processor(
                        loglevel="INFO",
                        concurrency=1,
                        queues=queues,
                    )
                except Exception as e:
                    logger.error(f"Failed to start Celery worker: {e}")

            worker_thread = threading.Thread(
                target=start_celery_worker,
                daemon=True,
            )
            worker_thread.start()

    @staticmethod
    async def _handle_shutdown(
        app: FastAPI,
        after_finish: Optional[Callable],
        **kwargs,
    ):
        """Handle application shutdown."""
        # Call custom shutdown callback
        if after_finish:
            if asyncio.iscoroutinefunction(after_finish):
                await after_finish(app, **kwargs)
            else:
                after_finish(app, **kwargs)

        # Cleanup internal runner
        runner = app.state.runner
        if runner:
            try:
                # Clean up runner
                await runner.__aexit__(None, None, None)
            except Exception as e:
                logger.error(f"Warning: Error during runner cleanup: {e}")

    @staticmethod
    async def _create_internal_runner():
        """Create internal runner with configured services."""
        from agentscope_runtime.engine import Runner

        # Create runner (agent will be set later)
        runner = Runner(
            # agent=None,  # Will be set by the specific deployment
            # context_manager=context_manager,
        )

        # Initialize runner
        await runner.__aenter__()

        return runner

    @staticmethod
    def _add_middleware(app: FastAPI, mode: DeploymentMode):
        """Add middleware based on deployment mode."""
        # Common middleware
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        # Mode-specific middleware
        if mode == DeploymentMode.DETACHED_PROCESS:
            # Add process management middleware
            @app.middleware("http")
            async def process_middleware(request: Request, call_next):
                # Add process-specific headers
                response = await call_next(request)
                response.headers["X-Process-Mode"] = "detached"
                return response

        elif mode == DeploymentMode.STANDALONE:
            # Add configuration middleware
            @app.middleware("http")
            async def config_middleware(request: Request, call_next):
                # Add configuration headers
                response = await call_next(request)
                response.headers["X-Deployment-Mode"] = "standalone"
                return response

    @staticmethod
    def _add_routes(
        app: FastAPI,
        endpoint_path: str,
        request_model: Optional[Type],
        stream_enabled: bool,
        mode: DeploymentMode,
    ):
        """Add routes to the FastAPI application."""

        # Health check endpoint
        @app.get("/health")
        async def health_check():
            """Health check endpoint."""
            status = {"status": "healthy", "mode": mode.value}

            # Add service health checks
            if hasattr(app.state, "runner") and app.state.runner:
                status["runner"] = "ready"
            else:
                status["runner"] = "not_ready"

            return status

        # Agent API endpoint
        @app.post(
            endpoint_path,
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
                    "description": "Agent API Request Format."
                    "See https://runtime.agentscope.io/en/protocol.html for "
                    "more details.",
                },
            },
            tags=["agent-api"],
        )
        async def agent_api(request: dict):
            """
            Agent API endpoint, see
            <https://runtime.agentscope.io/en/protocol.html> for more details.
            """
            return StreamingResponse(
                FastAPIAppFactory._create_stream_generator(
                    app,
                    request=request,
                ),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                },
            )

        # # Standard endpoint
        # @app.post(endpoint_path)
        # async def process_endpoint(request: dict):
        #     """Main processing endpoint."""
        #     return await FastAPIAppFactory._handle_request(
        #         app,
        #         request,
        #         stream_enabled,
        #     )

        # Root endpoint
        @app.get("/")
        async def root():
            """Root endpoint."""
            return {
                "service": "AgentScope Runtime",
                "mode": mode.value,
                "endpoints": {
                    "process": endpoint_path,
                    "stream": (
                        f"{endpoint_path}/stream" if stream_enabled else None
                    ),
                    "health": "/health",
                },
            }

        # Mode-specific endpoints
        FastAPIAppFactory._add_process_control_endpoints(app)

    @staticmethod
    def _add_process_control_endpoints(app: FastAPI):
        """Add process control endpoints for detached mode."""

        @app.post("/shutdown")
        async def shutdown_process_simple():
            """Gracefully shutdown the process (simple endpoint)."""
            # Import here to avoid circular imports
            import os
            import signal

            # Schedule shutdown after response
            async def delayed_shutdown():
                await asyncio.sleep(0.5)
                os.kill(os.getpid(), signal.SIGTERM)

            asyncio.create_task(delayed_shutdown())
            return {"status": "shutting down"}

        @app.post("/admin/shutdown")
        async def shutdown_process():
            """Gracefully shutdown the process."""
            # Import here to avoid circular imports
            import os
            import signal

            # Schedule shutdown after response
            async def delayed_shutdown():
                await asyncio.sleep(1)
                os.kill(os.getpid(), signal.SIGTERM)

            asyncio.create_task(delayed_shutdown())
            return {"message": "Shutdown initiated"}

        @app.get("/admin/status")
        async def get_process_status():
            """Get process status information."""
            import os
            import psutil

            process = psutil.Process(os.getpid())
            return {
                "pid": os.getpid(),
                "status": process.status(),
                "memory_usage": process.memory_info().rss,
                "cpu_percent": process.cpu_percent(),
                "uptime": process.create_time(),
            }

    @staticmethod
    async def _handle_request(
        app: FastAPI,
        request: dict,
        stream_enabled: bool,
    ):
        """Handle a standard request."""
        try:
            # Get runner instance
            runner = FastAPIAppFactory._get_runner_instance(app)
            if not runner:
                return JSONResponse(
                    status_code=503,
                    content={
                        "error": "Service not ready",
                        "message": "Runner not initialized",
                    },
                )

            # Handle custom function vs runner
            if app.state.custom_func:
                # Use custom function
                result = await FastAPIAppFactory._call_custom_function(
                    app.state.custom_func,
                    request,
                )
                return {"response": result}
            else:
                # Use runner
                if stream_enabled:
                    # Collect streaming response
                    result = await FastAPIAppFactory._collect_stream_response(
                        runner,
                        request,
                    )
                    return {"response": result}
                else:
                    # Direct query
                    result = await runner.query(request)
                    return {"response": result}

        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={"error": "Internal server error", "message": str(e)},
            )

    @staticmethod
    async def _create_stream_generator(app: FastAPI, request: dict):
        """Create streaming response generator."""
        try:
            runner = FastAPIAppFactory._get_runner_instance(app)
            if not runner:
                yield (
                    f"data: {json.dumps({'error': 'Runner not initialized'})}"
                    f"\n\n"
                )
                return

            if app.state.custom_func:
                # Handle custom function (convert to stream)
                result = await FastAPIAppFactory._call_custom_function(
                    app.state.custom_func,
                    request,
                )
                yield f"data: {json.dumps({'text': str(result)})}\n\n"
            else:
                # Use runner streaming
                async for chunk in runner.stream_query(request):
                    if hasattr(chunk, "model_dump_json"):
                        yield f"data: {chunk.model_dump_json()}\n\n"
                    elif hasattr(chunk, "json"):
                        yield f"data: {chunk.json()}\n\n"
                    else:
                        yield f"data: {json.dumps({'text': str(chunk)})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    @staticmethod
    async def _collect_stream_response(runner, request: dict) -> str:
        """Collect streaming response into a single string."""
        response_parts = []
        async for chunk in runner.stream_query(request):
            if hasattr(chunk, "text"):
                response_parts.append(chunk.text)
            else:
                response_parts.append(str(chunk))
        return "".join(response_parts)

    @staticmethod
    async def _call_custom_function(func: Callable, request: dict):
        """Call custom function with proper parameters."""
        if asyncio.iscoroutinefunction(func):
            return await func(
                user_id="default",
                request=request,
                request_id="generated",
            )
        else:
            return func(
                user_id="default",
                request=request,
                request_id="generated",
            )

    @staticmethod
    def _get_runner_instance(app: FastAPI):
        """Get runner instance from app state."""
        if hasattr(app.state, "runner"):
            return app.state.runner
        return None

    @staticmethod
    def _create_handler_wrapper(handler: Callable):
        """Create a wrapper for a handler that preserves function signature.

        This wrapper maintains the handler's signature to enable FastAPI's
        automatic parameter parsing and dependency injection. For async
        handlers, it returns an async wrapper; for sync handlers,
        it returns a sync wrapper.

        Args:
            handler: The handler function to wrap

        Returns:
            A wrapped handler that preserves the original function signature
        """

        is_awaitable = inspect.iscoroutinefunction(handler)
        if is_awaitable:

            @functools.wraps(handler)
            async def wrapped_handler(*args, **kwargs):
                return await handler(*args, **kwargs)

            wrapped_handler.__signature__ = inspect.signature(handler)
            return wrapped_handler
        else:

            @functools.wraps(handler)
            def wrapped_handler(*args, **kwargs):
                return handler(*args, **kwargs)

            wrapped_handler.__signature__ = inspect.signature(handler)
            return wrapped_handler

    @staticmethod
    def _to_sse_event(item: Any) -> str:
        """Normalize streaming items into JSON-serializable structures."""

        def _serialize(value: Any, depth: int = 0):
            if depth > 20:
                return f"<too-deep-level-{depth}-{str(value)}>"

            if isinstance(value, (list, tuple, set)):
                return [_serialize(i, depth=depth + 1) for i in value]
            elif isinstance(value, dict):
                return {
                    k: _serialize(v, depth=depth + 1) for k, v in value.items()
                }
            elif isinstance(value, (str, int, float, bool, type(None))):
                return value
            elif isinstance(value, BaseModel):
                return value.model_dump()
            elif is_dataclass(value):
                return asdict(value)

            for attr in ("to_map", "to_dict"):
                method = getattr(value, attr, None)
                if callable(method):
                    return method()
            return str(value)

        serialized = _serialize(item, depth=0)

        return f"data: {json.dumps(serialized, ensure_ascii=False)}\n\n"

    @staticmethod
    def _create_streaming_parameter_wrapper(
        handler: Callable,
    ):
        """Create a wrapper for streaming handlers that handles parameter
        parsing."""
        is_async_gen = inspect.isasyncgenfunction(handler)

        # NOTE:
        # -----
        # FastAPI >= 0.123.5 uses Dependant.is_coroutine_callable, which in
        # turn unwraps callables via inspect.unwrap() and then inspects the
        # unwrapped target to decide whether it is a coroutine function /
        # generator / async generator.
        #
        # If we decorate an async-generator handler with
        # functools.wraps(handler), FastAPI will unwrap back to the original
        # async-generator function and *misclassify* the endpoint as
        # non-coroutine. It will then call our async wrapper *without awaiting
        # it*, and later try to JSON-encode the resulting coroutine object,
        # causing errors like:
        # TypeError("'coroutine' object is not iterable")
        #
        # To avoid that, we deliberately do NOT use functools.wraps() here.
        # Instead, we manually copy the key metadata (name, qualname, doc,
        # module, and signature) from the original handler, but we do NOT set
        # __wrapped__. This ensures:
        #   * FastAPI sees the wrapper itself as the callable (an async def),
        #     so Dependant.is_coroutine_callable is True, and it is properly
        #     awaited.
        #   * FastAPI still sees the correct signature for parameter parsing.

        if is_async_gen:

            async def wrapped_handler(*args, **kwargs):
                async def generate():
                    try:
                        async for chunk in handler(*args, **kwargs):
                            yield FastAPIAppFactory._to_sse_event(
                                chunk,
                            )
                    except Exception as e:
                        logger.error(
                            f"Error in streaming handler: {e}",
                            exc_info=True,
                        )
                        err_event = {
                            "error": str(e),
                            "error_type": e.__class__.__name__,
                            "message": "Error in streaming generator",
                        }
                        yield FastAPIAppFactory._to_sse_event(err_event)

                return StreamingResponse(
                    generate(),
                    media_type="text/event-stream",
                )

        else:

            def wrapped_handler(*args, **kwargs):
                def generate():
                    try:
                        for chunk in handler(*args, **kwargs):
                            yield FastAPIAppFactory._to_sse_event(chunk)
                    except Exception as e:
                        logger.error(
                            f"Error in streaming handler: {e}",
                            exc_info=True,
                        )
                        err_event = {
                            "error": str(e),
                            "error_type": e.__class__.__name__,
                            "message": "Error in streaming generator",
                        }
                        yield FastAPIAppFactory._to_sse_event(err_event)

                return StreamingResponse(
                    generate(),
                    media_type="text/event-stream",
                )

        # Manually propagate essential metadata without creating a __wrapped__
        # chain that would confuse FastAPI's unwrap logic.
        wrapped_handler.__name__ = getattr(
            handler,
            "__name__",
            wrapped_handler.__name__,
        )
        wrapped_handler.__qualname__ = getattr(
            handler,
            "__qualname__",
            wrapped_handler.__qualname__,
        )
        wrapped_handler.__doc__ = getattr(
            handler,
            "__doc__",
            wrapped_handler.__doc__,
        )
        wrapped_handler.__module__ = getattr(
            handler,
            "__module__",
            wrapped_handler.__module__,
        )
        wrapped_handler.__signature__ = inspect.signature(handler)

        # Make sure FastAPI doesn't see any stale __wrapped__ pointing back to
        # the original async-generator; if present, remove it.

        return wrapped_handler

    @staticmethod
    def _add_custom_endpoints(app: FastAPI):
        """Add all custom endpoints to the FastAPI application."""
        if (
            not hasattr(app.state, "custom_endpoints")
            or not app.state.custom_endpoints
        ):
            return

        for endpoint in app.state.custom_endpoints:
            FastAPIAppFactory._register_single_custom_endpoint(
                app,
                endpoint["path"],
                endpoint["handler"],
                endpoint["methods"],
                endpoint,  # Pass the full endpoint config
            )

    @staticmethod
    def _register_single_custom_endpoint(
        app: FastAPI,
        path: str,
        handler: Callable,
        methods: List[str],
        endpoint_config: Dict = None,
    ):
        """Register a single custom endpoint with proper async/sync
        handling."""

        tags = ["custom"]

        for method in methods:
            # Check if this is a task endpoint
            if endpoint_config and endpoint_config.get("task_type"):
                # Create task endpoint with proper execution logic
                task_handler = FastAPIAppFactory._create_task_handler(
                    app,
                    handler,
                    endpoint_config.get("queue", "default"),
                )
                app.add_api_route(
                    path,
                    task_handler,
                    methods=[method],
                    tags=tags,
                )

                # Add task status endpoint - align with BaseApp pattern
                status_path = f"{path}/{{task_id}}"
                status_handler = FastAPIAppFactory._create_task_status_handler(
                    app,
                )
                app.add_api_route(
                    status_path,
                    status_handler,
                    methods=["GET"],
                    tags=tags,
                )

            else:
                # Regular endpoint handling with automatic parameter parsing
                # Check in the correct order: async gen > sync gen > async &
                # sync

                if inspect.isasyncgenfunction(
                    handler,
                ) or inspect.isgeneratorfunction(handler):
                    wrapped_handler = (
                        FastAPIAppFactory._create_streaming_parameter_wrapper(
                            handler,
                        )
                    )
                    app.add_api_route(
                        path,
                        wrapped_handler,
                        methods=[method],
                        tags=tags,
                        response_model=None,
                    )
                else:
                    # Non-streaming endpoint -> wrapper that preserves
                    # handler signature
                    wrapped_handler = (
                        FastAPIAppFactory._create_handler_wrapper(handler)
                    )
                    app.add_api_route(
                        path,
                        wrapped_handler,
                        methods=[method],
                        response_model=None,
                        tags=tags,
                    )

    @staticmethod
    def _create_task_handler(app: FastAPI, task_func: Callable, queue: str):
        """Create a task handler that executes functions asynchronously."""

        async def task_endpoint(request: dict):
            try:
                import uuid

                # Generate task ID
                task_id = str(uuid.uuid4())

                # Check if Celery is available
                if (
                    hasattr(app.state, "celery_mixin")
                    and app.state.celery_mixin
                ):
                    # Use Celery for task processing
                    celery_mixin = app.state.celery_mixin

                    # Register the task function if not already registered
                    if not hasattr(task_func, "celery_task"):
                        celery_task = celery_mixin.register_celery_task(
                            task_func,
                            queue,
                        )
                        task_func.celery_task = celery_task

                    # Submit task to Celery
                    result = celery_mixin.submit_task(task_func, request)

                    return {
                        "task_id": result.id,
                        "status": "submitted",
                        "queue": queue,
                        "message": f"Task {result.id} submitted to Celery "
                        f"queue {queue}",
                    }

                else:
                    # Fallback to in-memory task processing
                    import time

                    # Initialize task storage if not exists
                    if not hasattr(app.state, "active_tasks"):
                        app.state.active_tasks = {}

                    # Create task info for tracking
                    task_info = {
                        "task_id": task_id,
                        "status": "submitted",
                        "queue": queue,
                        "submitted_at": time.time(),
                        "request": request,
                    }
                    app.state.active_tasks[task_id] = task_info

                    # Execute task asynchronously in background
                    asyncio.create_task(
                        FastAPIAppFactory._execute_background_task(
                            app,
                            task_id,
                            task_func,
                            request,
                            queue,
                        ),
                    )

                    return {
                        "task_id": task_id,
                        "status": "submitted",
                        "queue": queue,
                        "message": f"Task {task_id} submitted to queue "
                        f"{queue}",
                    }

            except Exception as e:
                return {
                    "error": str(e),
                    "type": "task",
                    "queue": queue,
                    "status": "failed",
                }

        return task_endpoint

    @staticmethod
    async def _execute_background_task(
        app: FastAPI,
        task_id: str,
        func: Callable,
        request: dict,
        queue: str,
    ):
        """Execute task in background and update status."""
        try:
            import time
            import concurrent.futures

            # Update status to running
            if (
                hasattr(app.state, "active_tasks")
                and task_id in app.state.active_tasks
            ):
                app.state.active_tasks[task_id].update(
                    {
                        "status": "running",
                        "started_at": time.time(),
                    },
                )

            # Execute the actual task function
            if asyncio.iscoroutinefunction(func):
                result = await func(request)
            else:
                # Run sync function in thread pool to avoid blocking
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    result = await asyncio.get_event_loop().run_in_executor(
                        executor,
                        func,
                        request,
                    )

            # Update status to completed
            if (
                hasattr(app.state, "active_tasks")
                and task_id in app.state.active_tasks
            ):
                app.state.active_tasks[task_id].update(
                    {
                        "status": "completed",
                        "result": result,
                        "completed_at": time.time(),
                    },
                )

        except Exception as e:
            # Update status to failed
            if (
                hasattr(app.state, "active_tasks")
                and task_id in app.state.active_tasks
            ):
                app.state.active_tasks[task_id].update(
                    {
                        "status": "failed",
                        "error": str(e),
                        "failed_at": time.time(),
                    },
                )

    @staticmethod
    def _create_task_status_handler(app: FastAPI):
        """Create a handler for checking task status."""

        async def task_status_handler(task_id: str):
            if not task_id:
                return {"error": "task_id required"}

            # Check if Celery is available
            if hasattr(app.state, "celery_mixin") and app.state.celery_mixin:
                # Use Celery for task status checking
                celery_mixin = app.state.celery_mixin
                return celery_mixin.get_task_status(task_id)

            else:
                # Fallback to in-memory task status checking
                if (
                    not hasattr(app.state, "active_tasks")
                    or task_id not in app.state.active_tasks
                ):
                    return {"error": f"Task {task_id} not found"}

                task_info = app.state.active_tasks[task_id]
                task_status = task_info.get("status", "unknown")

                # Align with BaseApp.get_task logic - map internal status to
                # external status format
                if task_status in ["submitted", "running"]:
                    return {"status": "pending", "result": None}
                elif task_status == "completed":
                    return {
                        "status": "finished",
                        "result": task_info.get("result"),
                    }
                elif task_status == "failed":
                    return {
                        "status": "error",
                        "result": task_info.get("error", "Unknown error"),
                    }
                else:
                    return {"status": task_status, "result": None}

        return task_status_handler
