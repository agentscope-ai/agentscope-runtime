# -*- coding: utf-8 -*-
import os

from .agent_app import AgentApp
from agentscope_runtime.engine.agents.agentscope_agent import AgentScopeAgent
from agentscope_runtime.engine.deployers.local_deployer import (
    LocalDeployManager,
)

from agentscope.agent import ReActAgent
from agentscope.model import DashScopeChatModel
from agentscope.tool import Toolkit, view_text_file

toolkit = Toolkit()
# Register an unrelated tool
toolkit.register_tool_function(view_text_file)

agent = AgentScopeAgent(
    name="Friday",
    model=DashScopeChatModel(
        "qwen-max",
        api_key=os.getenv("DASHSCOPE_API_KEY"),
    ),
    agent_config={
        "sys_prompt": "You're a helpful assistant named Friday.",
        "toolkit": toolkit,
    },
    agent_builder=ReActAgent,
)

print("✅ AgentScope agent created successfully")


app = AgentApp(
    agent=agent,
    # broker_url="redis://localhost:6379/0",   # Redis database 0 for broker
    # backend_url="redis://localhost:6379/1",  # Redis database 1 for backend
)


@app.endpoint("/sync")
def sync_handler(request):
    return {"status": "ok"}


@app.endpoint("/async")
async def async_handler(request):
    return {"status": "ok"}


@app.endpoint("/stream_async")
async def stream_async_handler(request):
    for i in range(5):
        yield f"async chunk {i}\n"


@app.endpoint("/stream_sync")
def stream_sync_handler(request):
    for i in range(5):
        yield f"sync chunk {i}\n"


# @app.task("/task", queue="celery1")
# def task_handler(request):
#     time.sleep(15)
#     return {"status": "ok"}
#
# @app.task("/atask")
# async def atask_handler(request):
#     await asyncio.sleep(15)
#     return {"status": "ok"}

# app.run()


async def main():
    await app.deploy(LocalDeployManager())


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
    input("Press Enter to stop the server...")
