# -*- coding: utf-8 -*-
import asyncio
import time
import uuid
import json
import logging

from contextlib import asynccontextmanager
from typing import Optional, Dict, Any, Callable, Tuple, Union

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .base_app import BaseApp
from ..agents.base_agent import Agent
from ..deployers.adapter.a2a import A2AFastAPIDefaultAdapter
from ..runner import Runner
from ..services.context_manager import ContextManager
from ..services.environment_manager import EnvironmentManager
from ..schemas.agent_schemas import AgentRequest, AgentResponse, Error
from ...version import __version__

logger = logging.getLogger(__name__)


class AgentApp(BaseApp):
    """
    The AgentApp class represents an application that runs as an agent.
    """

    def __init__(
        self,
        *,
        agent: Optional[Agent] = None,
        environment_manager: Optional[EnvironmentManager] = None,
        context_manager: Optional[ContextManager] = None,
        endpoint_path: str = "/process",
        response_type: str = "sse",
        stream: bool = True,
        request_model: Optional[type[BaseModel]] = AgentRequest,
        before_start: Optional[Callable] = None,
        after_finish: Optional[Callable] = None,
        broker_url: Optional[str] = None,
        backend_url: Optional[str] = None,
        **kwargs,
    ):
        """
        Initialize the AgentApp.

        Args:
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.
        """

        self.endpoint_path = endpoint_path
        self.response_type = response_type
        self.stream = stream
        self.request_model = request_model
        self.before_start = before_start
        self.after_finish = after_finish

        self._agent = agent
        self._runner = None

        if self._agent:
            self._runner = Runner(
                agent=self._agent,
                environment_manager=environment_manager,
                context_manager=context_manager,
            )

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

        kwargs = {
            "title": "Agent Service",
            "version": __version__,
            "description": "Production-ready Agent Service API",
            "lifespan": lifespan,
            **kwargs,
        }

        if self._runner:
            if self.stream:
                self.func = self._runner.stream_query
            else:
                self.func = self._runner.query

        super().__init__(
            broker_url=broker_url,
            backend_url=backend_url,
            **kwargs,
        )

        self._add_middleware()
        self._add_health_endpoints()
        self._add_main_endpoint()

        # Support a2a protocol
        self.a2a_protocol = A2AFastAPIDefaultAdapter(agent=self._agent)
        self.a2a_protocol.add_endpoint(app=self, func=self.func)

    def run(
        self,
        host="0.0.0.0",
        port=8090,
        embed_task_processor=False,
        **kwargs,
    ):
        try:
            loop = asyncio.get_event_loop()
            if self._runner is not None:
                loop.run_until_complete(self._runner.__aenter__())

            logger.info("[AgentApp] Runner initialized.")

            super().run(
                host=host,
                port=port,
                embed_task_processor=embed_task_processor,
            )

        except Exception as e:
            logger.error(f"[AgentApp] Error while running: {e}")

        finally:
            try:
                try:
                    loop = asyncio.get_event_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                if self._runner is not None:
                    loop.run_until_complete(
                        self._runner.__aexit__(None, None, None),
                    )
                    logger.info("[AgentApp] Runner cleaned up.")
            except Exception as e:
                logger.error(f"[AgentApp] Error while cleaning up runner: {e}")

    async def deploy(self, deployer, **kwargs):
        return await deployer.deploy(self, **kwargs)

    def _add_middleware(self) -> None:
        """Add middleware"""

        @self.middleware("http")
        async def log_requests(request: Request, call_next):
            start_time = time.time()

            logger.info(f"Request: {request.method} {request.url}")
            response = await call_next(
                request,
            )
            process_time = time.time() - start_time
            logger.info(
                f'{request.client.host} - "{request.method} {request.url}" '
                f"{response.status_code} - {process_time:.3f}s",
            )

            return response

        @self.middleware("http")
        async def custom_middleware(
            request: Request,
            call_next: Callable,
        ) -> Response:
            """Custom middleware for request processing."""
            response: Response = await call_next(request)
            return response

        self.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    def _add_health_endpoints(self) -> None:
        """Add health check endpoints"""

        @self.get("/health")
        async def health_check():
            return {
                "status": "healthy",
                "timestamp": time.time(),
                "service": "agent-service",
            }

        @self.get("/readiness")
        async def readiness() -> str:
            """Check if the application is ready to serve requests."""
            if getattr(self.state, "is_ready", True):
                return "success"
            raise HTTPException(
                status_code=500,
                detail="Application is not ready",
            )

        @self.get("/liveness")
        async def liveness() -> str:
            """Check if the application is alive and healthy."""
            if getattr(self.state, "is_healthy", True):
                return "success"
            raise HTTPException(
                status_code=500,
                detail="Application is not healthy",
            )

        @self.get("/")
        async def root():
            return {"message": "Agent Service is running"}

    def _add_main_endpoint(self) -> None:
        """Add the main processing endpoint"""

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

        @self.post(self.endpoint_path)
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
                logger.error(f"Request processing failed: {e}")
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
