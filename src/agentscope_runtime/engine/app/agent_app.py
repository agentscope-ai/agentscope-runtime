# -*- coding: utf-8 -*-
import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Optional, Any, Callable, List

from fastapi import FastAPI
from pydantic import BaseModel

from .base_app import BaseApp
from ..agents.base_agent import Agent
from ..deployers.adapter.a2a import A2AFastAPIDefaultAdapter
from ..deployers.adapter.responses.response_api_protocol_adapter import (
    ResponseAPIDefaultAdapter,
)
from ..runner import Runner
from ..schemas.agent_schemas import AgentRequest
from ..services.context_manager import ContextManager
from ..services.environment_manager import EnvironmentManager
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
        self.custom_endpoints = []  # Store custom endpoints

        a2a_protocol = A2AFastAPIDefaultAdapter(agent=self._agent)
        response_protocol = ResponseAPIDefaultAdapter()
        self.protocol_adapters = [a2a_protocol, response_protocol]

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

        # Store custom endpoints and tasks for deployment
        # but don't add them to FastAPI here - let FastAPIAppFactory handle it

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
                **kwargs,
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
        """Deploy the agent app with custom endpoints support"""
        # Pass custom endpoints and tasks to the deployer

        deploy_kwargs = {
            **kwargs,
            "custom_endpoints": self.custom_endpoints,
            "agent": self._agent,
            "runner": self._runner,
            "endpoint_path": self.endpoint_path,
            "stream": self.stream,
            "protocol_adapters": self.protocol_adapters,
        }
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
