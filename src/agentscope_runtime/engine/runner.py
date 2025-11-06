# -*- coding: utf-8 -*-
import uuid
from contextlib import AsyncExitStack
from typing import Optional, List, AsyncGenerator, Any, Union, Dict

from agentscope_runtime.engine.deployers.utils.service_utils import (
    ServicesConfig,
)
from .agents import Agent
from .deployers import (
    DeployManager,
    LocalDeployManager,
)
from .deployers.adapter.protocol_adapter import ProtocolAdapter
from .schemas.agent_schemas import (
    Event,
    AgentRequest,
    RunStatus,
    AgentResponse,
    SequenceNumberGenerator,
)
from .schemas.context import Context
from .services.context_manager import ContextManager
from .services.environment_manager import EnvironmentManager
from .tracing import TraceType
from .tracing.wrapper import trace
from .tracing.message_util import (
    merge_agent_response,
    get_agent_response_finish_reason,
)


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
        self._context_manager = (
            context_manager or ContextManager()
        )  # Add default context manager
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
        requirements: Optional[Union[str, List[str]]] = None,
        extra_packages: Optional[List[str]] = None,
        base_image: str = "python:3.9-slim",
        environment: Optional[Dict[str, str]] = None,
        runtime_config: Optional[Dict] = None,
        services_config: Optional[Union[ServicesConfig, dict]] = None,
        **kwargs,
    ):
        """
        Deploys the agent as a service.

        Args:
            deploy_manager: Deployment manager to handle service deployment
            endpoint_path: API endpoint path for the processing function
            stream: If start a streaming service
            protocol_adapters: protocol adapters
            requirements: PyPI dependencies
            extra_packages: User code directory/file path
            base_image: Docker base image (for containerized deployment)
            environment: Environment variables dict
            runtime_config: Runtime configuration dict
            services_config: Services configuration dict
            **kwargs: Additional arguments passed to deployment manager
        Returns:
            URL of the deployed service

        Raises:
            RuntimeError: If deployment fails
        """
        deploy_result = await deploy_manager.deploy(
            runner=self,
            endpoint_path=endpoint_path,
            stream=stream,
            protocol_adapters=protocol_adapters,
            requirements=requirements,
            extra_packages=extra_packages,
            base_image=base_image,
            environment=environment,
            runtime_config=runtime_config,
            services_config=services_config,
            **kwargs,
        )

        # TODO: add redis or other persistant method
        self._deploy_managers[deploy_manager.deploy_id] = deploy_result
        return deploy_result

    @trace(
        TraceType.AGENT_STEP,
        trace_name="agent_step",
        merge_output_func=merge_agent_response,
        get_finish_reason_func=get_agent_response_finish_reason,
    )
    async def stream_query(  # pylint:disable=unused-argument
        self,
        request: Union[AgentRequest, dict],
        user_id: Optional[str] = None,
        tools: Optional[List] = None,
        **kwargs: Any,
    ) -> AsyncGenerator[Event, None]:
        """
        Streams the agent.
        """
        if isinstance(request, dict):
            request = AgentRequest(**request)

        seq_gen = SequenceNumberGenerator()

        # Initial response
        response = AgentResponse()
        yield seq_gen.yield_with_sequence(response)

        # Set to in-progress status
        response.in_progress()
        yield seq_gen.yield_with_sequence(response)

        if user_id is None:
            if getattr(request, "user_id", None):
                user_id = request.user_id
            else:
                user_id = ""  # Default user id

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

        async for event in context.agent.run_async(context):
            if (
                event.status == RunStatus.Completed
                and event.object == "message"
            ):
                response.add_new_message(event)
            yield seq_gen.yield_with_sequence(event)

        await context.context_manager.append(
            session=context.session,
            event_output=response.output,
        )
        yield seq_gen.yield_with_sequence(response.completed())

    #  TODO: will be added before 2025/11/30
    # @trace(TraceType.AGENT_STEP)
    # async def query(  # pylint:disable=unused-argument
    #     self,
    #     message: List[dict],
    #     session_id: Optional[str] = None,
    #     **kwargs: Any,
    # ) -> ChatCompletion:
    #     """
    #     Streams the agent.
    #     """
    #     return self._agent.query(message, session_id)

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
