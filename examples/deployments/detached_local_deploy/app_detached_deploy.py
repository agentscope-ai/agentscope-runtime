# -*- coding: utf-8 -*-
# pylint:disable=wrong-import-order

import asyncio
import time

from agentscope_runtime.engine.deployers.local_deployer import (
    LocalDeployManager,
    DeploymentMode,
)
from agentscope_runtime.engine.schemas.agent_schemas import AgentRequest
from app_agent import agent_app


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
