# -*- coding: utf-8 -*-
import asyncio
import os
import time

from agentscope.agent import ReActAgent
from agentscope.model import DashScopeChatModel
from agentscope.tool import Toolkit, view_text_file

from agentscope_runtime.engine.agents.agentscope_agent import AgentScopeAgent
from agentscope_runtime.engine.app import AgentApp
from agentscope_runtime.engine.deployers.local_deployer import (
    LocalDeployManager,
)
from agentscope_runtime.engine.schemas.agent_schemas import AgentRequest

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
def sync_handler(request: AgentRequest):
    return {"status": "ok", "payload": request}


@app.endpoint("/async")
async def async_handler(request: AgentRequest):
    return {"status": "ok", "payload": request}


@app.endpoint("/stream_async")
async def stream_async_handler(request: AgentRequest):
    for i in range(5):
        yield f"async chunk {i}, with request payload {request}\n"


@app.endpoint("/stream_sync")
def stream_sync_handler(request: AgentRequest):
    for i in range(5):
        yield f"sync chunk {i}, with request payload {request}\n"


@app.task("/task", queue="celery1")
def task_handler(request: AgentRequest):
    time.sleep(30)
    return {"status": "ok", "payload": request}


@app.task("/atask")
async def atask_handler(request: AgentRequest):
    await asyncio.sleep(15)
    return {"status": "ok", "payload": request}


# app.run()


async def main():
    await app.deploy(LocalDeployManager())


if __name__ == "__main__":
    asyncio.run(main())
    input("Press Enter to stop the server...")
