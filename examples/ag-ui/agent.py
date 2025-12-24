# -*- coding: utf-8 -*-
import os
from typing import List, Optional

from agentscope.agent import ReActAgent
from agentscope.formatter import DashScopeChatFormatter
from agentscope.message import TextBlock
from agentscope.model import OpenAIChatModel
from agentscope.pipeline import stream_printing_messages
from agentscope.tool import ToolResponse, Toolkit, execute_python_code

from agentscope_runtime.adapters.agentscope.memory import (
    AgentScopeSessionHistoryMemory,
)
from agentscope_runtime.engine import AgentApp
from agentscope_runtime.engine.deployers.adapter.agui import AGUIAdaptorConfig
from agentscope_runtime.engine.runner import Runner
from agentscope_runtime.engine.schemas.agent_schemas import (
    AgentRequest,
    Message,
)
from agentscope_runtime.engine.services.agent_state import InMemoryStateService
from agentscope_runtime.engine.services.session_history import (
    InMemorySessionHistoryService,
    SessionHistoryService,
)

agent_app = AgentApp(
    app_name="Friday",
    app_description="A helpful assistant",
    agui_config=AGUIAdaptorConfig(
        route_path="/agentic_chat/",
    ),
)


# Prepare a custom tool function
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
    runner.session_service = InMemorySessionHistoryService()

    await runner.state_service.start()
    await runner.session_service.start()


@agent_app.shutdown
async def shutdown_func(runner: Runner):
    await runner.state_service.stop()
    await runner.session_service.stop()


async def get_unseen_messages(
    session_service: SessionHistoryService,
    messages: List[Message],
    user_id: str,
    session_id: str,
) -> list[Message]:
    """
    By Default, AG-UI Client will send all messages to the agent.
    This function is used to get the unseen messages from the session.

    Args:
        session_service (SessionHistoryService): Session history service
        messages (List[Message]): List of messages
        user_id (str): User ID
        session_id (str): Session ID

    Returns:
        list[Message]: List of unseen messages

    """
    session = await session_service.get_session(
        user_id=user_id,
        session_id=session_id,
    )

    seen_message_ids = [message.id for message in session.messages]
    return [
        message for message in messages if message.id not in seen_message_ids
    ]


def create_stateful_agent(
    session_service: SessionHistoryService,
    session_id: str,
    user_id: str,
    state: Optional[dict] = None,
) -> ReActAgent:
    """
    Create a stateful agent with the given session service, session id, user
    id, and state.

    Args:
        session_service (SessionHistoryService): Session history service
        session_id (str): Session ID
        user_id (str): User ID
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
        memory=AgentScopeSessionHistoryMemory(
            service=session_service,
            session_id=session_id,
            user_id=user_id,
        ),
        formatter=DashScopeChatFormatter(),
    )
    agent.set_console_output_enabled(enabled=False)

    if state:
        agent.load_state_dict(state)

    return agent


@agent_app.query(framework="agentscope")
async def query_func(
    runner,
    msgs,
    request: AgentRequest = None,
    **kwargs,  # pylint: disable=unused-argument
):
    session_id = request.session_id
    user_id = request.user_id

    unseen_messages = await get_unseen_messages(
        session_service=runner.session_service,
        session_id=session_id,
        user_id=user_id,
        messages=msgs,
    )

    # If state is provided in the request via AG-UI, use it directly.
    state = getattr(request, "state", None)
    if not state:
        state = await runner.state_service.export_state(
            session_id=session_id,
            user_id=user_id,
        )
    agent = create_stateful_agent(
        runner.session_service,
        session_id,
        user_id,
        state=state,
    )

    async for msg, last in stream_printing_messages(
        agents=[agent],
        coroutine_task=agent(unseen_messages),
    ):
        yield msg, last

    state = agent.state_dict()

    await runner.state_service.save_state(
        user_id=user_id,
        session_id=session_id,
        state=state,
    )
