# -*- coding: utf-8 -*-
# pylint:disable=wrong-import-position, wrong-import-order, unused-argument
import asyncio
import os

from agentscope.agent import ReActAgent
from agentscope.formatter import DashScopeChatFormatter
from agentscope.model import DashScopeChatModel
from agentscope.pipeline import stream_printing_messages
from agentscope.tool import Toolkit
from agentscope.memory import InMemoryMemory

from agentscope_runtime.engine.app import AgentApp
from agentscope_runtime.engine.schemas.agent_schemas import AgentRequest
from agentscope_runtime.engine.services.agent_state import (
    InMemoryStateService,
)
from others.other_project import version


def weather_search(query: str) -> str:
    """Search for weather information based on location query.

    Args:
        query: Location query string

    Returns:
        Weather information string
    """
    if "sf" in query.lower() or "san francisco" in query.lower():
        result = "It's 60 degrees and foggy."
    else:
        result = "It's 90 degrees and sunny."

    return result


# Create AgentApp
agent_app = AgentApp(
    app_name="Friday",
    app_description="A helpful assistant with weather tool",
)


@agent_app.init
async def init_func(self):
    self.state_service = InMemoryStateService()
    await self.state_service.start()


@agent_app.shutdown
async def shutdown_func(self):
    await self.state_service.stop()


@agent_app.query(framework="agentscope")
async def query_func(
    self,
    msgs,
    request: AgentRequest = None,
    **kwargs,
):
    session_id = request.session_id
    user_id = request.user_id

    state = await self.state_service.export_state(
        session_id=session_id,
        user_id=user_id,
    )

    toolkit = Toolkit()
    toolkit.register_tool_function(weather_search)

    agent = ReActAgent(
        name="Friday",
        model=DashScopeChatModel(
            "qwen-turbo",
            api_key=os.getenv("DASHSCOPE_API_KEY"),
            stream=True,
        ),
        sys_prompt="You're a helpful assistant named Friday.",
        toolkit=toolkit,
        memory=InMemoryMemory(),
        formatter=DashScopeChatFormatter(),
    )

    if state:
        agent.load_state_dict(state)

    async for msg, last in stream_printing_messages(
        agents=[agent],
        coroutine_task=agent(msgs),
    ):
        yield msg, last

    state = agent.state_dict()

    await self.state_service.save_state(
        user_id=user_id,
        session_id=session_id,
        state=state,
    )


print(f"AgentScope Runtime with dependencies version: {version}")


async def run():
    # This function demonstrates how the app would be used
    # In actual tests, the agent_app can be deployed directly
    from agentscope_runtime.engine.deployers.local_deployer import (
        LocalDeployManager,
    )

    deploy_manager = LocalDeployManager(host="localhost", port=8090)
    deployment_info = await agent_app.deploy(deploy_manager)
    print(f"Deployed at: {deployment_info['url']}")


if __name__ == "__main__":
    asyncio.run(run())
