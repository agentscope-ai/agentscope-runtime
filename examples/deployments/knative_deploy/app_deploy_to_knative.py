# -*- coding: utf-8 -*-
import asyncio
import time
import os

from agentscope.agent import ReActAgent
from agentscope.model import DashScopeChatModel
from agentscope.formatter import DashScopeChatFormatter
from agentscope.tool import Toolkit, execute_python_code
from agentscope.pipeline import stream_printing_messages
from agentscope.memory import InMemoryMemory

from agentscope_runtime.engine.app import AgentApp
from agentscope_runtime.engine.deployers.knative_deployer import (
    KnativeDeployManager,
    RegistryConfig,
    K8sConfig,
)
from agentscope_runtime.engine.schemas.agent_schemas import AgentRequest
from agentscope_runtime.engine.services.agent_state import (
    InMemoryStateService,
)

agent_app = AgentApp(
    app_name="Friday",
    app_description="A helpful assistant",
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
    assert kwargs is not None, "kwargs is Required for query_func"
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


async def deploy_app_to_knative():
    """Deploy Knative Service to Knative"""

    # 1. Configure Registry
    registry_config = RegistryConfig(
        registry_url=(
            "crpi-p44cuw4wgxu8xn0b.cn-hangzhou.personal.cr.aliyuncs.com"
        ),
        namespace="agentscope-runtime",
    )

    # 2. Configure K8s connection
    k8s_config = K8sConfig(
        k8s_namespace="agentscope-runtime",
        kubeconfig_path=None,
    )
    # 3. Configure Knative gateway ip or domain
    gateway = "121.xx.xxx.xx"
    port = 8080

    # 4. Create KnativeDeployManager
    deployer = KnativeDeployManager(
        kube_config=k8s_config,
        registry_config=registry_config,
    )

    # 5. Runtime configuration
    runtime_config = {
        # Resource limits
        "resources": {
            "requests": {"cpu": "200m", "memory": "512Mi"},
            "limits": {"cpu": "1000m", "memory": "2Gi"},
        },
        # Image pull policy
        "image_pull_policy": "IfNotPresent",
    }

    # 6. Knative Service configuration
    kservice_config = {
        # Basic configuration
        "port": str(port),
        "image_tag": "linux-amd64-1",
        "image_name": "agent_app",
        "annotations": {},
        "labels": {
            "app": "agent-ksvc",
        },
        # Dependencies configuration
        "requirements": [
            "agentscope",
            "fastapi",
            "uvicorn",
        ],
        "extra_packages": [
            os.path.join(
                os.path.dirname(__file__),
                "others",
                "other_project.py",
            ),
        ],
        "base_image": "python:3.10-slim-bookworm",
        # Environment variables
        "environment": {
            "PYTHONPATH": "/app",
            "LOG_LEVEL": "INFO",
            "DASHSCOPE_API_KEY": os.environ.get("DASHSCOPE_API_KEY"),
        },
        # K8s runtime configuration
        "runtime_config": runtime_config,
        # Knative timeout
        "deploy_timeout": 300,
        "health_check": True,
        "platform": "linux/amd64",
        "push_to_registry": True,
    }

    try:
        print("🚀 Starting AgentApp knative service to Knative...")

        # 7. Execute Knative
        result = await agent_app.deploy(
            deployer,
            **kservice_config,
        )

        print(f"✅ {result['resource_name']} KService successful!")
        print(f"📍 Deploy ID: {result['deploy_id']}")
        print(f"🌐 KService Url: {result['url']}")
        print(f"📦 Gateway: {gateway}")
        result["gateway"] = gateway

        # 8. Check KService status
        print("\n📊 Checking KService status...")
        status = deployer.get_status()
        print(f"Status: {status}")

        return result, deployer

    except Exception as e:
        print(f"❌ Knative failed: {e}")
        raise


async def main():
    """Main function"""
    try:
        # Deploy
        result, deployer = await deploy_app_to_knative()
        gateway = result["gateway"]
        kservice_domain = result["url"].removeprefix("http://")

        # Keep running, you can test manually
        print(
            f"""
        Service deployment completed, you can test with the following commands:

        # Health check
        curl -H "Host: {kservice_domain}" http://{gateway}/health

        # Test sync endpoint
        curl -X POST http://{gateway}/sync \\
          -H "Content-Type: application/json" \\
          -H "Host: {kservice_domain}" \\
          -d '{{
                "input": [
                {{
                  "role": "user",
                  "content": [
                    {{
                      "type": "text",
                      "text": "Hello, how are you?"
                    }}
                  ]
                }}
              ],
              "session_id": "123"
            }}'

        # Test async endpoint
        curl -X POST http://{gateway}/async \\
          -H "Content-Type: application/json" \\
          -H "Host: {kservice_domain}" \\
          -d '{{
                "input": [
                {{
                  "role": "user",
                  "content": [
                    {{
                      "type": "text",
                      "text": "Hello, how are you?"
                    }}
                  ]
                }}
              ],
              "session_id": "123"
            }}'

        # Test streaming endpoint
        curl -X POST http://{gateway}/stream_async \\
          -H "Content-Type: application/json" \\
          -H "Host: {kservice_domain}" \\
          -H "Accept: text/event-stream" \\
          --no-buffer \\
          -d '{{
                "input": [
                {{
                  "role": "user",
                  "content": [
                    {{
                      "type": "text",
                      "text": "Hello, how are you?"
                    }}
                  ]
                }}
              ],
              "session_id": "123"
            }}'
        """,
        )

        print("\n📝 Or use kubectl to check:")
        print("kubectl get ksvc -n agentscope-runtime")
        print("kubectl logs -l app=agent-ksvc -n agentscope-runtime")

        # Wait for user confirmation before cleanup
        input("\nPress Enter to cleanup kservice...")

        # Cleanup kservice
        print("🧹 Cleaning up kservice...")
        cleanup_result = await deployer.stop()
        if cleanup_result:
            print("✅ Cleanup completed")
        else:
            print("❌ Cleanup failed, please check manually")

    except Exception as e:
        print(f"❌ Error occurred during execution: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    # Run kservice
    asyncio.run(main())
