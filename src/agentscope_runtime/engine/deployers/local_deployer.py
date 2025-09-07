# -*- coding: utf-8 -*-
import asyncio
import json
import logging
import socket
import threading
import time
import uuid
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any, Callable, Type, Tuple, Union

import uvicorn
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .base import DeployManager
from .adapter.protocol_adapter import ProtocolAdapter
from ..schemas.agent_schemas import AgentRequest, AgentResponse, Error


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

    def _create_fastapi_app(self) -> FastAPI:
        """Create and configure FastAPI application with lifespan
        management."""

        @asynccontextmanager
        async def lifespan(app: FastAPI) -> Any:
            """Manage the application lifespan."""
            if hasattr(self, "before_start") and self.before_start:
                if asyncio.iscoroutinefunction(self.before_start):
                    await self.before_start(app, **getattr(self, "kwargs", {}))
                else:
                    self.before_start(app, **getattr(self, "kwargs", {}))
            yield
            if hasattr(self, "after_finish") and self.after_finish:
                if asyncio.iscoroutinefunction(self.after_finish):
                    await self.after_finish(app, **getattr(self, "kwargs", {}))
                else:
                    self.after_finish(app, **getattr(self, "kwargs", {}))

        app = FastAPI(
            title="Agent Service",
            version="1.0.0",
            description="Production-ready Agent Service API",
            lifespan=lifespan,
        )

        self._add_middleware(app)
        self._add_health_endpoints(app)

        if hasattr(self, "func") and self.func:
            self._add_main_endpoint(app)

        return app

    def _add_middleware(self, app: FastAPI) -> None:
        """Add middleware to the FastAPI application."""

        @app.middleware("http")
        async def log_requests(request: Request, call_next):
            start_time = time.time()

            self.app_logger.info(f"Request: {request.method} {request.url}")
            response = await call_next(
                request,
            )
            process_time = time.time() - start_time
            self.access_logger.info(
                f'{request.client.host} - "{request.method} {request.url}" '
                f"{response.status_code} - {process_time:.3f}s",
            )

            return response

        @app.middleware("http")
        async def custom_middleware(
            request: Request,
            call_next: Callable,
        ) -> Response:
            """Custom middleware for request processing."""
            response: Response = await call_next(request)
            return response

        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    def _add_health_endpoints(self, app: FastAPI) -> None:
        """Add health check endpoints to the FastAPI application."""

        @app.get("/health")
        async def health_check():
            return {
                "status": "healthy",
                "timestamp": time.time(),
                "service": "agent-service",
            }

        @app.get("/readiness")
        async def readiness() -> str:
            """Check if the application is ready to serve requests."""
            if getattr(app.state, "is_ready", True):
                return "success"
            raise HTTPException(
                status_code=500,
                detail="Application is not ready",
            )

        @app.get("/liveness")
        async def liveness() -> str:
            """Check if the application is alive and healthy."""
            if getattr(app.state, "is_healthy", True):
                return "success"
            raise HTTPException(
                status_code=500,
                detail="Application is not healthy",
            )

        @app.get("/")
        async def root():
            return {"message": "Agent Service is running"}

    def _add_main_endpoint(self, app: FastAPI) -> None:
        """Add the main processing endpoint to the FastAPI application."""

        async def _get_request_info(request: Request) -> Tuple[Dict, Any, str]:
            """Extract request information from the HTTP request."""
            body = await request.body()
            request_body = json.loads(body.decode("utf-8")) if body else {}

            user_id = request_body.get("user_id", "")

            if hasattr(self, "request_model") and self.request_model:
                try:
                    request_body_obj = self.request_model.model_validate(
                        request_body,
                    )
                except Exception as e:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Invalid request format: {e}",
                    ) from e
            else:
                request_body_obj = request_body

            query_params = dict(request.query_params)
            return query_params, request_body_obj, user_id

        def _get_request_id(request_body_obj: Any) -> str:
            """Extract or generate a request ID from the request body."""
            if hasattr(request_body_obj, "header") and hasattr(
                request_body_obj.header,
                "request_id",
            ):
                request_id = request_body_obj.header.request_id
            elif (
                isinstance(
                    request_body_obj,
                    dict,
                )
                and "request_id" in request_body_obj
            ):
                request_id = request_body_obj["request_id"]
            else:
                request_id = str(uuid.uuid4())
            return request_id

        @app.post(self.endpoint_path)
        async def main_endpoint(request: Request):
            """Main endpoint handler for processing requests."""
            try:
                (
                    _,  # query_params
                    request_body_obj,
                    user_id,
                ) = await _get_request_info(
                    request=request,
                )
                request_id = _get_request_id(request_body_obj)
                if (
                    hasattr(
                        self,
                        "response_type",
                    )
                    and self.response_type == "sse"
                ):
                    return self._handle_sse_response(
                        user_id=user_id,
                        request_body_obj=request_body_obj,
                        request_id=request_id,
                    )
                else:
                    return await self._handle_standard_response(
                        user_id=user_id,
                        request_body_obj=request_body_obj,
                        request_id=request_id,
                    )

            except Exception as e:
                self._logger.error(f"Request processing failed: {e}")
                raise HTTPException(status_code=500, detail=str(e)) from e

    def _handle_sse_response(
        self,
        user_id: str,
        request_body_obj: Any,
        request_id: str,
    ) -> StreamingResponse:
        """Handle Server-Sent Events response."""

        async def stream_generator():
            """Generate streaming response data."""
            try:
                if asyncio.iscoroutinefunction(self.func):
                    async for output in self.func(
                        user_id=user_id,
                        request=request_body_obj,
                        request_id=request_id,
                    ):
                        _data = self._create_success_result(
                            output=output,
                        )
                        yield f"data: {_data}\n\n"
                else:
                    # For sync functions, we need to handle differently
                    result = self.func(
                        user_id=user_id,
                        request=request_body_obj,
                        request_id=request_id,
                    )
                    if hasattr(result, "__aiter__"):
                        async for output in result:
                            _data = self._create_success_result(
                                output=output,
                            )
                            yield f"data: {_data}\n\n"
                    else:
                        _data = self._create_success_result(
                            output=result,
                        )
                        yield f"data: {_data}\n\n"
            except Exception as e:
                _data = self._create_error_response(
                    request_id=request_id,
                    error=e,
                )
                yield f"data: {_data}\n\n"

        return StreamingResponse(
            stream_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            },
        )

    async def _handle_standard_response(
        self,
        user_id: str,
        request_body_obj: Any,
        request_id: str,
    ):
        """Handle standard JSON response."""
        try:
            if asyncio.iscoroutinefunction(self.func):
                result = await self.func(
                    user_id=user_id,
                    request=request_body_obj,
                    request_id=request_id,
                )
            else:
                result = self.func(
                    user_id=user_id,
                    request=request_body_obj,
                    request_id=request_id,
                )

            return self._create_success_result(
                output=result,
            )
        except Exception as e:
            return self._create_error_response(request_id=request_id, error=e)

    def _create_success_result(
        self,
        output: Union[BaseModel, Dict, str],
    ) -> str:
        """Create a success response."""
        if isinstance(output, BaseModel):
            return output.model_dump_json()
        elif isinstance(output, dict):
            return json.dumps(output)
        else:
            return output

    def _create_error_response(
        self,
        request_id: str,
        error: Exception,
    ) -> str:
        """Create an error response."""
        response = AgentResponse(id=request_id)
        response.failed(Error(code=str(error), message=str(error)))
        return response.model_dump_json()

    def deploy_sync(
        self,
        func: Callable,
        endpoint_path: str = "/process",
        request_model: Optional[Type] = AgentRequest,
        response_type: str = "sse",
        before_start: Optional[Callable] = None,
        after_finish: Optional[Callable] = None,
        **kwargs: Any,
    ) -> Dict[str, str]:
        """
        Deploy the agent as a FastAPI service (synchronous version).

        Args:
            func: Custom processing function
            endpoint_path: API endpoint path for the processing function
            request_model: Pydantic model for request validation
            response_type: Response type - "json", "sse", or "text"
            before_start: Callback function called before server starts
            after_finish: Callback function called after server finishes
            **kwargs: Additional keyword arguments passed to callbacks

        Returns:
            Dict[str, str]: Dictionary containing deploy_id and url of the
            deployed service

        Raises:
            RuntimeError: If deployment fails
        """
        return asyncio.run(
            self._deploy_async(
                func=func,
                endpoint_path=endpoint_path,
                request_model=request_model,
                response_type=response_type,
                before_start=before_start,
                after_finish=after_finish,
                **kwargs,
            ),
        )

    async def deploy(
        self,
        runner: "Runner" = None,
        endpoint_path: str = "/process",
        stream: bool = True,
        request_model: Optional[Type] = AgentRequest,
        response_type: str = "sse",
        before_start: Optional[Callable] = None,
        after_finish: Optional[Callable] = None,
        protocol_adapters: Optional[list[ProtocolAdapter]] = None,
        # Backward compatibility parameters
        func: Optional[Callable] = None,
        **kwargs: Any,
    ) -> Dict[str, str]:
        """
        Deploy the agent as a FastAPI service (asynchronous version).

        Args:
            runner: Complete Runner object (new approach)
            endpoint_path: API endpoint path for the processing function
            stream: Enable streaming response (used when runner is provided)
            request_model: Pydantic model for request validation
            response_type: Response type - "json", "sse", or "text"
            before_start: Callback function called before server starts
            after_finish: Callback function called after server finishes
            protocol_adapters: protocol adapters
            # Backward compatibility
            func: Custom processing function (deprecated, use runner instead)
            **kwargs: Additional keyword arguments passed to callbacks

        Returns:
            Dict[str, str]: Dictionary containing deploy_id and url of the
            deployed service

        Raises:
            RuntimeError: If deployment fails
        """
        # Handle backward compatibility
        if runner is not None and func is not None:
            raise ValueError("Cannot specify both runner and func parameters")
        elif runner is not None:
            # New pattern: use runner with appropriate method based on stream setting
            if stream:
                actual_func = runner.stream_query
                actual_response_type = "sse"
            else:
                actual_func = runner.query
                actual_response_type = "json"
        elif func is not None:
            # Legacy pattern: use provided func
            actual_func = func
            actual_response_type = response_type
        else:
            raise ValueError(
                "Either runner or func parameter must be provided",
            )

        return await self._deploy_async(
            func=actual_func,
            endpoint_path=endpoint_path,
            request_model=request_model,
            response_type=actual_response_type,
            before_start=before_start,
            after_finish=after_finish,
            protocol_adapters=protocol_adapters,
            **kwargs,
        )

    async def _deploy_async(
        self,
        func: Callable,
        endpoint_path: str = "/process",
        request_model: Optional[Type] = None,
        response_type: str = "sse",
        before_start: Optional[Callable] = None,
        after_finish: Optional[Callable] = None,
        protocol_adapters: Optional[list[ProtocolAdapter]] = None,
        **kwargs: Any,
    ) -> Dict[str, str]:
        if self._is_running:
            raise RuntimeError("Service is already running")

        try:
            self._logger.info("Starting FastAPI service deployment...")

            # Store callable configuration
            self.func = func
            self.endpoint_path = endpoint_path
            self.request_model = request_model
            self.response_type = response_type
            self.before_start = before_start
            self.after_finish = after_finish
            self.kwargs = kwargs

            # Create FastAPI app
            self._app = self._create_fastapi_app()

            # Support extension protocol
            if protocol_adapters:
                for protocol_adapter in protocol_adapters:
                    protocol_adapter.add_endpoint(app=self._app, func=func)

            # Configure uvicorn server
            config = uvicorn.Config(
                self._app,
                host=self.host,
                port=self.port,
                log_level="info",
                access_log=False,
                timeout_keep_alive=30,
            )

            self._server = uvicorn.Server(config)
            # Run the server in a separate thread
            self._server_thread = threading.Thread(target=self._server.run)
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
