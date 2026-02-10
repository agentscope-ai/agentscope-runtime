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
from agentscope.session import RedisSession

from agentscope_runtime.engine.app import AgentApp

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


async def deploy_app_to_sandbox():
    """Deploy AgentApp as a Sandbox custom resource (agents.kruise.io)"""

    from agentscope_runtime.engine.deployers.sandbox_deployer import (
        SandboxDeployManager,
        RegistryConfig,
        K8sConfig,
    )

    # 1. Configure Registry
    registry_config = RegistryConfig(
        registry_url=os.environ.get("REGISTRY_URL", "your-registry-url"),
        namespace="agentscope-runtime",
    )

    # 2. Configure K8s connection
    k8s_config = K8sConfig(
        k8s_namespace="agentscope-runtime",
        kubeconfig_path=None,
    )

    port = 8080

    # 3. Create SandboxDeployManager
    deployer = SandboxDeployManager(
        kube_config=k8s_config,
        registry_config=registry_config,
    )

    # 4. Runtime configuration
    runtime_config = {
        # Resource limits
        "resources": {
            "requests": {"cpu": "200m", "memory": "512Mi"},
            "limits": {"cpu": "1000m", "memory": "2Gi"},
        },
        # Image pull policy
        "image_pull_policy": "IfNotPresent",
    }

    # 5. Sandbox deployment configuration
    sandbox_config = {
        # Basic configuration
        "port": str(port),
        "image_tag": "linux-amd64-2",
        "image_name": "agent_app",
        "annotations": {},
        "labels": {},
        # Dependencies configuration
        "requirements": [
            "agentscope",
            "fastapi",
            "uvicorn",
            "fakeredis",
        ],
        # "extra_packages": [
        #     os.path.join(
        #         os.path.dirname(__file__),
        #         "others",
        #         "other_project.py",
        #     ),
        # ],
        "base_image": "python:3.10-slim-bookworm",
        # Environment variables
        "environment": {
            "PYTHONPATH": "/app",
            "LOG_LEVEL": "INFO",
            "DASHSCOPE_API_KEY": os.environ.get("DASHSCOPE_API_KEY"),
        },
        # K8s runtime configuration
        "runtime_config": runtime_config,
        # Deployment settings
        "deploy_timeout": 300,
        "health_check": True,
        "platform": "linux/amd64",
        "push_to_registry": True,
    }

    try:
        print("🚀 Starting AgentApp deployment as Sandbox CR...")

        # 6. Execute deployment
        result = await agent_app.deploy(
            deployer,
            **sandbox_config,
        )

        print("✅ Sandbox deployment successful!")
        print(f"📍 Deploy ID: {result['deploy_id']}")
        print(f"🌐 Service URL: {result['url']}")
        print(f"📦 Resource name: {result['resource_name']}")

        # 7. Check deployment status
        print("\n📊 Checking Sandbox status...")
        status = deployer.get_status()
        print(f"Status: {status}")

        return result, deployer

    except Exception as e:
        print(f"❌ Sandbox deployment failed: {e}")
        raise


async def deployed_service_run(service_url: str):
    """Test the deployed service"""
    import aiohttp

    test_request = {
        "input": [
            {
                "role": "user",
                "content": [{"type": "text", "text": "Hello, how are you?"}],
            },
        ],
        "session_id": "123",
    }

    try:
        async with aiohttp.ClientSession() as session:
            # Test sync endpoint
            async with session.post(
                f"{service_url}/sync",
                json=test_request,
                headers={"Content-Type": "application/json"},
            ) as response:
                if response.status == 200:
                    result = await response.text()
                    print(f"✅ Sync endpoint test successful: {result}")
                else:
                    print(f"❌ Sync endpoint test failed: {response.status}")

            # Test async endpoint
            async with session.post(
                f"{service_url}/async",
                json=test_request,
                headers={"Content-Type": "application/json"},
            ) as response:
                if response.status == 200:
                    result = await response.text()
                    print(f"✅ Async endpoint test successful: {result}")
                else:
                    print(f"❌ Async endpoint test failed: {response.status}")

    except Exception as e:
        print(f"❌ Service test exception: {e}")


async def main():
    """Main function"""
    try:
        # Deploy
        result, deployer = await deploy_app_to_sandbox()
        service_url = result["url"]

        # Test service
        print("\n🧪 Testing the deployed service...")
        await deployed_service_run(service_url)

        # Keep running, you can test manually
        print(
            f"""
        Service deployment completed, you can test with the following commands:

        # Health check
        curl {service_url}/health

        # Test sync endpoint
        curl -X POST {service_url}/sync \\
          -H "Content-Type: application/json" \\
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
        curl -X POST {service_url}/async \\
          -H "Content-Type: application/json" \\
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
        curl -X POST {service_url}/stream_async \\
          -H "Content-Type: application/json" \\
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
        print("kubectl get sandbox -n agentscope-runtime")
        print("kubectl get svc -n agentscope-runtime")
        print("kubectl get pod -n agentscope-runtime")
        print(
            f"kubectl logs -l app={result['resource_name']} "
            "-n agentscope-runtime",
        )

        # Wait for user confirmation before cleanup
        input("\nPress Enter to cleanup sandbox deployment...")

        # Cleanup deployment
        print("🧹 Cleaning up sandbox deployment...")
        cleanup_result = await deployer.stop(result["deploy_id"])
        if cleanup_result.get("success"):
            print("✅ Cleanup completed")
        else:
            print(
                f"❌ Cleanup failed: {cleanup_result.get('message')}, "
                "please check manually",
            )

    except Exception as e:
        print(f"❌ Error occurred during execution: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    # Run sandbox deployment
    asyncio.run(main())
