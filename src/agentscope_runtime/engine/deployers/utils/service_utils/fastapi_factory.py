# -*- coding: utf-8 -*-
# pylint:disable=too-many-branches, unused-argument


import asyncio
import json
from contextlib import asynccontextmanager
from typing import Optional, Callable, Type, Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse

from .service_config import ServicesConfig, DEFAULT_SERVICES_CONFIG
from .service_factory import ServiceFactory
from ..deployment_modes import DeploymentMode
from ...adapter.protocol_adapter import ProtocolAdapter


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
        services_config: Optional[ServicesConfig] = None,
        protocol_adapters: Optional[list[ProtocolAdapter]] = None,
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
            services_config: Services configuration
            protocol_adapters: Protocol adapters
            **kwargs: Additional keyword arguments

        Returns:
            FastAPI application instance
        """
        # Use default services config if not provided
        if services_config is None:
            services_config = DEFAULT_SERVICES_CONFIG

        # Create lifespan manager
        @asynccontextmanager
        async def lifespan(app: FastAPI):
            """Application lifespan manager."""
            # Startup
            try:
                await FastAPIAppFactory._handle_startup(
                    app,
                    mode,
                    services_config,
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
        app = FastAPI(lifespan=lifespan)

        # Store configuration in app state
        app.state.deployment_mode = mode
        app.state.services_config = services_config
        app.state.stream_enabled = stream
        app.state.response_type = response_type
        app.state.custom_func = func
        app.state.external_runner = runner
        app.state.endpoint_path = endpoint_path
        app.state.protocol_adapters = protocol_adapters  # Store for later use

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
        services_config: ServicesConfig,
        external_runner: Optional[Any],
        before_start: Optional[Callable],
        **kwargs,
    ):
        """Handle application startup."""
        # Mode-specific initialization
        if mode == DeploymentMode.DAEMON_THREAD:
            # Use external runner
            app.state.runner = external_runner
            app.state.runner_managed_externally = True

        elif mode in [
            DeploymentMode.DETACHED_PROCESS,
            DeploymentMode.STANDALONE,
        ]:
            # Create internal runner
            app.state.runner = await FastAPIAppFactory._create_internal_runner(
                services_config,
            )
            app.state.runner_managed_externally = False

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
        if (
            hasattr(app.state, "runner")
            and not app.state.runner_managed_externally
        ):
            runner = app.state.runner
            if runner and hasattr(runner, "context_manager"):
                try:
                    await runner.context_manager.__aexit__(None, None, None)
                except Exception as e:
                    print(f"Warning: Error during runner cleanup: {e}")

    @staticmethod
    async def _create_internal_runner(services_config: ServicesConfig):
        """Create internal runner with configured services."""
        from agentscope_runtime.engine import Runner
        from agentscope_runtime.engine.services.context_manager import (
            ContextManager,
        )

        # Create services
        services = ServiceFactory.create_services_from_config(services_config)

        # Create context manager
        context_manager = ContextManager(
            session_history_service=services["session_history"],
            memory_service=services["memory"],
        )

        # Initialize context manager
        await context_manager.__aenter__()

        # Create runner (agent will be set later)
        runner = Runner(
            agent=None,  # Will be set by the specific deployment
            context_manager=context_manager,
        )

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

        # Main processing endpoint
        # if stream_enabled:
        # Streaming endpoint
        @app.post(endpoint_path)
        async def stream_endpoint(request: dict):
            """Streaming endpoint."""
            return StreamingResponse(
                FastAPIAppFactory._create_stream_generator(app, request),
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
                    "stream": f"{endpoint_path}/stream"
                    if stream_enabled
                    else None,
                    "health": "/health",
                },
            }

        # Mode-specific endpoints
        if mode == DeploymentMode.DETACHED_PROCESS:
            FastAPIAppFactory._add_process_control_endpoints(app)
        elif mode == DeploymentMode.STANDALONE:
            FastAPIAppFactory._add_configuration_endpoints(app)

    @staticmethod
    def _add_process_control_endpoints(app: FastAPI):
        """Add process control endpoints for detached mode."""

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
    def _add_configuration_endpoints(app: FastAPI):
        """Add configuration endpoints for standalone mode."""

        @app.get("/config")
        async def get_configuration():
            """Get current service configuration."""
            return {
                "services_config": app.state.services_config.model_dump(),
                "deployment_mode": app.state.deployment_mode.value,
                "stream_enabled": app.state.stream_enabled,
            }

        @app.get("/config/services")
        async def get_services_status():
            """Get services status."""
            status = {}
            if hasattr(app.state, "runner") and app.state.runner:
                runner = app.state.runner
                if hasattr(runner, "context_manager"):
                    cm = runner.context_manager
                    status["memory_service"] = (
                        "connected" if cm.memory_service else "disconnected"
                    )
                    status["session_history_service"] = (
                        "connected"
                        if cm.session_history_service
                        else "disconnected"
                    )

            return {"services": status}

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
