# -*- coding: utf-8 -*-
# pylint: disable=not-callable
import asyncio
import logging
import inspect
import traceback
import uuid
from contextlib import AsyncExitStack
from typing import (
    Optional,
    List,
    AsyncGenerator,
    Any,
    Union,
    Dict,
    AsyncIterator,
)

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
    Error,
)
from .tracing import TraceType
from .tracing.wrapper import trace
from .tracing.message_util import (
    merge_agent_response,
    get_agent_response_finish_reason,
)
from .constant import ALLOWED_FRAMEWORK_TYPES


logger = logging.getLogger(__name__)


class Runner:
    def __init__(self) -> None:
        """
        Initializes a runner as core instance.
        """
        self.framework_type = None

        self._deploy_managers = {}
        self._health = False
        self._exit_stack = AsyncExitStack()

    async def query_handler(self, *args, **kwargs):
        """
        Handle agent query.
        """
        raise NotImplementedError("query_handler not implemented")

    async def init_handler(self, *args, **kwargs):
        """
        Init handler.
        """

    async def shutdown_handler(self, *args, **kwargs):
        """
        Shutdown handler.
        """

    async def start(self):
        init_fn = getattr(self, "init_handler", None)
        if callable(init_fn):
            if inspect.iscoroutinefunction(init_fn):
                await init_fn()
            else:
                init_fn()
        else:
            logger.warning("[Runner] init_handler is not callable")
        self._health = True
        return self

    async def stop(self):
        shutdown_fn = getattr(self, "shutdown_handler", None)
        try:
            if callable(shutdown_fn):
                if inspect.iscoroutinefunction(shutdown_fn):
                    await shutdown_fn()
                else:
                    shutdown_fn()
        except Exception as e:
            logger.warning(f"[Runner] Exception in shutdown handler: {e}")
        try:
            await self._exit_stack.aclose()
        except Exception:
            pass

        self._health = False

    async def __aenter__(self) -> "Runner":
        """
        Initializes the runner
        """
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.stop()

        if hasattr(self, "_deploy_manager") and self._deploy_manager:
            for deploy_id in self._deploy_manager:
                await self._deploy_manager[deploy_id].stop()
        else:
            # No deploy manager found, nothing to stop
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
            **kwargs,
        )

        # TODO: add redis or other persistent method
        self._deploy_managers[deploy_manager.deploy_id] = deploy_result
        return deploy_result

    async def _call_handler_streaming(self, handler, *args, **kwargs):
        """
        Call handler and yield results in streaming fashion, async or sync.
        """
        result = handler(*args, **kwargs)

        if inspect.isasyncgenfunction(handler):
            async for item in result:
                yield item

        elif inspect.isgenerator(result):
            for item in result:
                yield item

        elif asyncio.iscoroutine(result):
            res = await result
            yield res

        else:
            yield result

    @trace(
        TraceType.AGENT_STEP,
        trace_name="agent_step",
        merge_output_func=merge_agent_response,
        get_finish_reason_func=get_agent_response_finish_reason,
    )
    async def stream_query(  # pylint:disable=unused-argument
        self,
        request: Union[AgentRequest, dict],
        **kwargs: Any,
    ) -> AsyncGenerator[Event, None]:
        """
        Streams the agent.
        """
        if self.framework_type not in ALLOWED_FRAMEWORK_TYPES:
            raise RuntimeError(
                f"Framework type '{self.framework_type}' is invalid or not "
                f"set. Please set `self.framework_type` to one of:"
                f" {', '.join(ALLOWED_FRAMEWORK_TYPES)}.",
            )

        if not self._health:
            raise RuntimeError(
                "Runner has not been started. "
                "Please call 'await runner.start()' or use 'async with "
                "Runner()' before calling 'stream_query'.",
            )

        if isinstance(request, dict):
            request = AgentRequest(**request)

        # Assign session ID
        request.session_id = request.session_id or str(uuid.uuid4())

        # Assign user ID
        request.user_id = request.user_id or request.session_id

        seq_gen = SequenceNumberGenerator()

        # Initial response
        response = AgentResponse(id=request.id)
        response.session_id = request.session_id
        yield seq_gen.yield_with_sequence(response)

        # Set to in-progress status
        response.in_progress()
        yield seq_gen.yield_with_sequence(response)

        query_kwargs = {
            "request": request,
        }

        if self.framework_type == "text":
            from ..adapters.text.stream import adapt_text_stream

            stream_adapter = adapt_text_stream
        elif self.framework_type == "agentscope":
            from ..adapters.agentscope.stream import (
                adapt_agentscope_message_stream,
            )
            from ..adapters.agentscope.message import message_to_agentscope_msg

            stream_adapter = adapt_agentscope_message_stream
            kwargs.update(
                {"msgs": message_to_agentscope_msg(request.input)},
            )
        # TODO: support other frameworks
        else:

            def identity_stream_adapter(
                source_stream: AsyncIterator[Any],
            ) -> AsyncIterator[Any]:
                return source_stream

            stream_adapter = identity_stream_adapter

        try:
            async for event in stream_adapter(
                source_stream=self._call_handler_streaming(
                    self.query_handler,
                    **query_kwargs,
                    **kwargs,
                ),
            ):
                if (
                    event.status == RunStatus.Completed
                    and event.object == "message"
                ):
                    response.add_new_message(event)
                yield seq_gen.yield_with_sequence(event)
        except Exception as e:
            # TODO: fix code
            error = Error(
                code="500",
                message=f"Error happens in `query_handler`: {e}",
            )
            logger.error(f"{error.model_dump()}: {traceback.format_exc()}")
            yield seq_gen.yield_with_sequence(response.failed(error))
            return

        # Obtain token usage
        try:
            if response.output:
                response.usage = response.output[-1].usage
        except IndexError:
            # Avoid empty message
            pass

        yield seq_gen.yield_with_sequence(response.completed())
