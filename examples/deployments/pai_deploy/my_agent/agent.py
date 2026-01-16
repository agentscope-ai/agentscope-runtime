# -*- coding: utf-8 -*-
import os
from typing import AsyncIterator, List, Optional

from agentscope.agent import ReActAgent
from agentscope.formatter import DashScopeChatFormatter
from agentscope.message import TextBlock, Msg
from agentscope.model import OpenAIChatModel
from agentscope.pipeline import stream_printing_messages
from agentscope.tool import ToolResponse, Toolkit, execute_python_code

from agentscope_runtime.engine import AgentApp
from agentscope_runtime.engine.runner import Runner
from agentscope_runtime.engine.schemas.agent_schemas import (
    AgentRequest,
)
from agentscope_runtime.engine.services.agent_state import InMemoryStateService

agent_app = AgentApp(
    app_name="SimpleAgent",
    app_description="A helpful assistant",
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
    runner.state_service = InMemoryStateService()
    await runner.state_service.start()


@agent_app.shutdown
async def shutdown_func(runner: Runner):
    await runner.state_service.stop()


def create_stateful_agent(
    state: Optional[dict] = None,
) -> ReActAgent:
    """
    Create a stateful agent with the given session service, session id, user
    id, and state.

    Args:
        state (Optional[dict]): State to load into the agent

    Returns:
        tuple[dict, Toolkit]: Tuple containing the state and toolkit

    """

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

    if state:
        agent.load_state_dict(state)

    return agent


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

    state = await runner.state_service.export_state(
        session_id=session_id,
        user_id=user_id,
    )
    agent = create_stateful_agent(
        state=state,
    )

    async for msg, last in stream_printing_messages(
        agents=[agent],
        coroutine_task=agent(msgs),
    ):
        yield msg, last

    state = agent.state_dict()

    await runner.state_service.save_state(
        user_id=user_id,
        session_id=session_id,
        state=state,
    )
