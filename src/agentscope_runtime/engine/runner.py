# -*- coding: utf-8 -*-
import uuid
from typing import Optional, List, AsyncGenerator, Any
from contextlib import AsyncExitStack

from openai.types.chat import ChatCompletion

from .deployers.adapter.protocol_adapter import ProtocolAdapter
from .agents import Agent
from .schemas.context import Context
from .deployers import (
    DeployManager,
    LocalDeployManager,
)
from .schemas.agent_schemas import (
    Event,
    AgentRequest,
    RunStatus,
    AgentResponse,
)
from .services.context_manager import ContextManager
from .services.environment_manager import EnvironmentManager
from .tracing import TraceType
from .tracing.wrapper import trace


class Runner:
    def __init__(
        self,
        agent: Agent,
        environment_manager: Optional[EnvironmentManager] = None,
        context_manager: Optional[ContextManager] = None,
    ) -> None:
        """
        Initializes a runner as core function.
        Args:
            agent: The agent to run.
            environment_manager: The environment manager
            context_manager: The context manager
        """
        self._agent = agent
        self._environment_manager = environment_manager
        self._context_manager = context_manager
        self._deploy_managers = {}
        self._exit_stack = AsyncExitStack()

    async def __aenter__(self) -> "Runner":
        """
        Initializes the runner and ensures context/environment managers
        are fully entered so that attributes like compose_session are
        available.
        """
        if self._environment_manager:
            # enter_async_context returns the "real" object
            self._environment_manager = (
                await self._exit_stack.enter_async_context(
                    self._environment_manager,
                )
            )

        if self._context_manager:
            self._context_manager = await self._exit_stack.enter_async_context(
                self._context_manager,
            )

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        try:
            await self._exit_stack.aclose()
        except Exception:
            pass

    async def deploy(
        self,
        deploy_manager: DeployManager = LocalDeployManager(),
        endpoint_path: str = "/process",
        stream: bool = True,
        protocol_adapters: Optional[list[ProtocolAdapter]] = None,
    ):
        """
        Deploys the agent as a service.

        Args:
            protocol_adapters: protocol adapters
            deploy_manager: Deployment manager to handle service deployment
            endpoint_path: API endpoint path for the processing function
            stream: If start a streaming service
        Returns:
            URL of the deployed service

        Raises:
            RuntimeError: If deployment fails
        """
        if stream:
            deploy_func = self.stream_query
        else:
            deploy_func = self.query
        deploy_result = await deploy_manager.deploy(
            deploy_func,
            endpoint_path=endpoint_path,
            protocol_adapters=protocol_adapters,
        )
        self._deploy_managers[deploy_manager.deploy_id] = deploy_result
        return deploy_result

    @trace(TraceType.AGENT_STEP)
    async def stream_query(  # pylint:disable=unused-argument
        self,
        request: AgentRequest,
        user_id: Optional[str] = None,
        tools: Optional[List] = None,
        **kwargs: Any,
    ) -> AsyncGenerator[Event, None]:
        """
        Streams the agent.
        """
        response = AgentResponse()
        yield response

        response.in_progress()
        yield response

        user_id = user_id or str(uuid.uuid4())
        session_id = request.session_id or str(uuid.uuid4())
        request_input = request.input
        session = await self._context_manager.compose_session(
            user_id=user_id,
            session_id=session_id,
        )

        context = Context(
            user_id=session.user_id,
            session=session,
            request=request,
            current_messages=request_input,
            context_manager=self._context_manager,
            environment_manager=self._environment_manager,
            agent=self._agent,
        )

        # TODO: Update activate tools into the context (not schema only)
        tools = tools or getattr(self._agent, "tools", None)
        if tools:
            # Lazy import
            from ..sandbox.tools.utils import setup_tools

            activated_tools, schemas = setup_tools(
                tools=tools,
                environment_manager=context.environment_manager,
                session_id=session.id,
                user_id=session.user_id,
                include_schemas=True,
            )

            # update the context
            context.activate_tools = activated_tools

            # convert schema to a function call tool lists
            # TODO: use pydantic model
            if hasattr(context.request, "tools") and context.request.tools:
                context.request.tools.extend(schemas)

        # update message in session
        await context.context_manager.compose_context(
            session=context.session,
            request_input=request_input,
        )

        sequence_number = 0
        async for event in context.agent.run_async(context):
            if (
                event.status == RunStatus.Completed
                and event.object == "message"
            ):
                response.add_new_message(event)
            event.sequence_number = sequence_number
            yield event
            sequence_number += 1

        await context.context_manager.append(
            session=context.session,
            event_output=response.output,
        )
        response.sequence_number = sequence_number
        yield response.completed()

    @trace(TraceType.AGENT_STEP)
    async def query(  # pylint:disable=unused-argument
        self,
        message: List[dict],
        session_id: Optional[str] = None,
        **kwargs: Any,
    ) -> ChatCompletion:
        """
        Streams the agent.
        """
        return self._agent.query(message, session_id)

    # TODO: should be sync method?
    async def stop(
        self,
        deploy_id: str,
    ) -> None:
        """
        Stops the agent service.

        Args:
            deploy_id: Optional deploy ID (not used for service shutdown)

        Raises:
            RuntimeError: If stopping fails
        """
        if hasattr(self, "_deploy_manager") and self._deploy_manager:
            await self._deploy_manager[deploy_id].stop()
        else:
            # No deploy manager found, nothing to stop
            pass
