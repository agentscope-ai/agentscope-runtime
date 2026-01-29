# -*- coding: utf-8 -*-
import asyncio
import os
import time

from agentscope.agent import ReActAgent
from agentscope.model import DashScopeChatModel
from agentscope.formatter import DashScopeChatFormatter
from agentscope.tool import Toolkit, execute_python_code
from agentscope.pipeline import stream_printing_messages
from agentscope.memory import InMemoryMemory
from agentscope.session import RedisSession


from agentscope_runtime.engine.app import AgentApp
from agentscope_runtime.engine.deployers.local_deployer import (
    LocalDeployManager,
)
from agentscope_runtime.engine.schemas.agent_schemas import AgentRequest

agent_app = AgentApp(
    app_name="Friday",
    app_description="A helpful assistant",
)


@agent_app.init
async def init_func(self):
    import fakeredis

    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    # NOTE: This FakeRedis instance is for development/testing only.
    # In production, replace it with your own Redis client/connection
    # (e.g., aioredis.Redis)
    self.session = RedisSession(connection_pool=fake_redis.connection_pool)


@agent_app.query(framework="agentscope")
async def query_func(
    self,
    msgs,
    request: AgentRequest = None,
    **kwargs,
):
    assert kwargs is not None, "kwargs is Required for query_func"
    session_id = request.session_id
    user_id = request.user_id

    toolkit = Toolkit()
    toolkit.register_tool_function(execute_python_code)

    agent = ReActAgent(
        name="Friday",
        model=DashScopeChatModel(
            "qwen-turbo",
            api_key=os.getenv("DASHSCOPE_API_KEY"),
            enable_thinking=True,
            stream=True,
        ),
        sys_prompt="You're a helpful assistant named Friday.",
        toolkit=toolkit,
        memory=InMemoryMemory(),
        formatter=DashScopeChatFormatter(),
    )

    await self.session.load_session_state(
        session_id=session_id,
        user_id=user_id,
        agent=agent,
    )

    async for msg, last in stream_printing_messages(
        agents=[agent],
        coroutine_task=agent(msgs),
    ):
        yield msg, last

    await self.session.save_session_state(
        session_id=session_id,
        user_id=user_id,
        agent=agent,
    )


@agent_app.endpoint("/sync")
def sync_handler(request: AgentRequest):
    yield {"status": "ok", "payload": request}


@agent_app.endpoint("/async")
async def async_handler(request: AgentRequest):
    yield {"status": "ok", "payload": request}


@agent_app.endpoint("/stream_async")
async def stream_async_handler(request: AgentRequest):
    for i in range(5):
        yield f"async chunk {i}, with request payload {request}\n"


@agent_app.endpoint("/stream_sync")
def stream_sync_handler(request: AgentRequest):
    for i in range(5):
        yield f"sync chunk {i}, with request payload {request}\n"


@agent_app.task("/task", queue="celery1")
def task_handler(request: AgentRequest):
    time.sleep(30)
    yield {"status": "ok", "payload": request}


@agent_app.task("/atask")
async def atask_handler(request: AgentRequest):
    await asyncio.sleep(15)
    yield {"status": "ok", "payload": request}


# agent_app.run()


async def main():
    await agent_app.deploy(LocalDeployManager(port=8080))


if __name__ == "__main__":
    asyncio.run(main())
    input("Press Enter to stop the server...")
