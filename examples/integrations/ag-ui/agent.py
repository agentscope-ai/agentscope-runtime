# -*- coding: utf-8 -*-
import os
from typing import AsyncIterator, List, Optional

from agentscope.agent import ReActAgent
from agentscope.formatter import DashScopeChatFormatter
from agentscope.message import TextBlock, Msg
from agentscope.model import OpenAIChatModel
from agentscope.pipeline import stream_printing_messages
from agentscope.tool import ToolResponse, Toolkit, execute_python_code
from agentscope.session import RedisSession

from agentscope_runtime.engine import AgentApp
from agentscope_runtime.engine.deployers.adapter.agui import AGUIAdaptorConfig
from agentscope_runtime.engine.runner import Runner
from agentscope_runtime.engine.schemas.agent_schemas import (
    AgentRequest,
    Message,
)

agent_app = AgentApp(
    agui_config=AGUIAdaptorConfig(
        route_path="/ag-ui",
    ),
)


async def get_weather(location: str) -> ToolResponse:
    """Get the weather for a location.

    Args:
        location (str): The location to get the weather for.

    """
    return ToolResponse(
        content=[
            TextBlock(
                type="text",
                text=f"The weather in {location} is sunny with a temperature "
                "of 25°C.",
            ),
        ],
    )


@agent_app.init
async def init_func(runner: Runner):
    import fakeredis

    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    # NOTE: This FakeRedis instance is for development/testing only.
    # In production, replace it with your own Redis client/connection
    # (e.g., aioredis.Redis)
    runner.session = RedisSession(connection_pool=fake_redis.connection_pool)


async def get_unseen_messages(
    input_messages: List[Message],
    memory_msgs: Optional[list[Msg]] = None,
) -> list[Message]:
    """
    By Default, AG-UI Client will send all messages to the agent.
    This function is used to get the unseen messages from the input message.

    Args:
        memory_msgs: list[Msg]: List of memory messages
        input_messages: List[Message]: List of input messages

    Returns:
        list[Message]: List of unseen messages

    """
    memory_msgs = memory_msgs or []
    seen_message_ids = [message.id for message in memory_msgs] + [
        message.metadata.get("original_id")
        for message in memory_msgs
        if message.metadata is not None
        and message.metadata.get("original_id") is not None
    ]

    return [
        message
        for message in input_messages
        if message.id not in seen_message_ids
    ]


@agent_app.query(framework="agentscope")
async def query_func(
    runner: Runner,
    msgs: List[Msg],
    request: AgentRequest = None,
    **kwargs,  # pylint: disable=unused-argument
) -> AsyncIterator[tuple[Msg, bool]]:
    """
    Main entry point for agent execution.

    Args:
        runner: Runner instance
        msgs: List of messages to process
        request: AgentRequest instance
        **kwargs: Additional keyword arguments

    Returns:
        Iterator[tuple[Msg, bool]]: Iterator of messages and last flag
    """

    session_id = request.session_id
    user_id = request.user_id

    toolkit = Toolkit()
    toolkit.register_tool_function(execute_python_code)
    toolkit.register_tool_function(get_weather)

    agent = ReActAgent(
        name="Example Agent for AG-UI",
        model=OpenAIChatModel(
            "qwen-max",
            api_key=os.getenv("DASHSCOPE_API_KEY", "your-dashscope-api-key"),
            client_args={
                "base_url": (
                    "https://dashscope.aliyuncs.com/compatible-mode/v1"
                ),
            },
        ),
        sys_prompt="You're a helpful assistant named Friday.",
        toolkit=toolkit,
        formatter=DashScopeChatFormatter(),
    )
    agent.set_console_output_enabled(enabled=False)

    await runner.session.load_session_state(
        session_id=session_id,
        user_id=user_id,
        agent=agent,
    )

    async for msg, last in stream_printing_messages(
        agents=[agent],
        coroutine_task=agent(msgs),
    ):
        yield msg, last

    await runner.session.save_session_state(
        session_id=session_id,
        user_id=user_id,
        agent=agent,
    )
