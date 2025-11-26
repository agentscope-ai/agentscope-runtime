# -*- coding: utf-8 -*-
import asyncio
import time
import os

from agentscope.agent import ReActAgent
from agentscope.model import DashScopeChatModel
from agentscope.formatter import DashScopeChatFormatter
from agentscope.tool import Toolkit, execute_python_code
from agentscope.pipeline import stream_printing_messages


from agentscope_runtime.adapters.agentscope.memory import (
    AgentScopeSessionHistoryMemory,
)
from agentscope_runtime.engine.app import AgentApp
from agentscope_runtime.engine.deployers.local_deployer import (
    LocalDeployManager,
    DeploymentMode,
)
from agentscope_runtime.engine.schemas.agent_schemas import AgentRequest
from agentscope_runtime.engine.services.agent_state import (
    InMemoryStateService,
)
from agentscope_runtime.engine.services.session_history import (
    InMemorySessionHistoryService,
)

agent_app = AgentApp(
    app_name="Friday",
    app_description="A helpful assistant",
)


@agent_app.init
async def init_func(self):
    self.state_service = InMemoryStateService()
    self.session_service = InMemorySessionHistoryService()

    await self.state_service.start()
    await self.session_service.start()


@agent_app.shutdown
async def shutdown_func(self):
    await self.state_service.stop()
    await self.session_service.stop()


@agent_app.query(framework="agentscope")
async def query_func(
    self,
    msgs,
    request: AgentRequest = None,
):
    session_id = request.session_id
    user_id = request.user_id

    state = await self.state_service.export_state(
        session_id=session_id,
        user_id=user_id,
    )

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
        memory=AgentScopeSessionHistoryMemory(
            service=self.session_service,
            session_id=session_id,
            user_id=user_id,
        ),
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


@agent_app.endpoint("/sync")
def sync_handler(request: AgentRequest):
    return {"status": "ok", "payload": request}


@agent_app.endpoint("/async")
async def async_handler(request: AgentRequest):
    return {"status": "ok", "payload": request}


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
    return {"status": "ok", "payload": request}


@agent_app.task("/atask")
async def atask_handler(request: AgentRequest):
    await asyncio.sleep(15)
    return {"status": "ok", "payload": request}


async def main():
    """Deploy app in detached process mode"""
    print("🚀 Deploying AgentApp in detached process mode...")

    # Create deployment manager
    deploy_manager = LocalDeployManager(
        host="127.0.0.1",
        port=8080,
    )

    # Deploy in detached mode:q
    deployment_info = await agent_app.deploy(
        deploy_manager,
        mode=DeploymentMode.DETACHED_PROCESS,
    )

    print(f"✅ Deployment successful: {deployment_info['url']}")
    print(f"📍 Deployment ID: {deployment_info['deploy_id']}")

    print(
        f"""
🎯 Service started, you can test with the following commands:

# Health check
curl {deployment_info['url']}/health

# Test sync endpoint
curl -X POST {deployment_info['url']}/sync \\
  -H "Content-Type: application/json" \\
  -d '{{"input": [{{"role": "user", "content": [{{"type": "text", "text":
  "Hello"}}]}}], "session_id": "123"}}'

# Test async endpoint
curl -X POST {deployment_info['url']}/async \\
  -H "Content-Type: application/json" \\
  -d '{{"input": [{{"role": "user", "content": [{{"type": "text", "text":
  "Hello"}}]}}], "session_id": "123"}}'

# Test streaming endpoint (async)
curl -X POST {deployment_info['url']}/stream_async \\
  -H "Content-Type: application/json" \\
  -H "Accept: text/event-stream" \\
  --no-buffer \\
  -d '{{"input": [{{"role": "user", "content": [{{"type": "text", "text":
  "Hello"}}]}}], "session_id": "123"}}'

# Test streaming endpoint (sync)
curl -X POST {deployment_info['url']}/stream_sync \\
  -H "Content-Type: application/json" \\
  -H "Accept: text/event-stream" \\
  --no-buffer \\
  -d '{{"input": [{{"role": "user", "content": [{{"type": "text", "text":
  "Hello"}}]}}], "session_id": "123"}}'

# Test Celery task endpoint
curl -X POST {deployment_info['url']}/task \\
  -H "Content-Type: application/json" \\
  -d '{{"input": [{{"role": "user", "content": [{{"type": "text", "text":
  "Hello"}}]}}], "session_id": "123"}}'

# Stop service
curl -X POST {deployment_info['url']}/admin/shutdown

⚠️ Note: The service runs in a detached process and will continue running
until stopped.
""",
    )

    return deploy_manager, deployment_info


if __name__ == "__main__":
    asyncio.run(main())
