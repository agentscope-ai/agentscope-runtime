# -*- coding: utf-8 -*-
# pylint:disable=wrong-import-position, wrong-import-order
import asyncio
import os

from agentscope.agent import ReActAgent
from agentscope.model import DashScopeChatModel

from agentscope_runtime.engine.agents.agentscope_agent import AgentScopeAgent
from agentscope_runtime.engine.runner import Runner
from agentscope_runtime.engine.schemas.agent_schemas import (
    MessageType,
    RunStatus,
    AgentRequest,
)
from agentscope_runtime.engine.services.context_manager import (
    ContextManager,
)
from agentscope_runtime.sandbox.tools.function_tool import function_tool
from others.other_project import version


@function_tool()
def weather_search(query: str) -> str:
    if "sf" in query.lower() or "san francisco" in query.lower():
        result = "It's 60 degrees and foggy."
    else:
        result = "It's 90 degrees and sunny."

    return result


agent = AgentScopeAgent(
    name="Friday",
    model=DashScopeChatModel(
        "qwen-turbo",
        api_key=os.getenv("DASHSCOPE_API_KEY"),
    ),
    agent_config={
        "sys_prompt": "You're a helpful assistant named Friday.",
    },
    agent_builder=ReActAgent,
    tools=[
        weather_search,
    ],
)
print(f"AgentScope Runtime with dependencies version: {version}")


async def run():
    # Create a request
    request = AgentRequest(
        input=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "杭州天气如何？",
                    },
                ],
            },
        ],
    )

    runner = Runner(
        agent=agent,
        context_manager=ContextManager(),
        # context_manager=None       # Optional
    )
    async for message in runner.stream_query(request=request):
        # Check if this is a completed message
        if (
            message.object == "message"
            and MessageType.MESSAGE == message.type
            and RunStatus.Completed == message.status
        ):
            all_result = message.content[0].text
        print(message)

    print(f"📝 Agent response: {all_result}")


if __name__ == "__main__":
    asyncio.run(run())
