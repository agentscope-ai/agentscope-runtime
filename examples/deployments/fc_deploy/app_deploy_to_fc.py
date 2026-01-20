# -*- coding: utf-8 -*-

import asyncio
import logging
import os
import time

from agentscope.agent import ReActAgent
from agentscope.formatter import DashScopeChatFormatter
from agentscope.model import DashScopeChatModel
from agentscope.pipeline import stream_printing_messages
from agentscope.tool import Toolkit, execute_python_code
from agentscope.memory import InMemoryMemory

from agentscope_runtime.engine.app import AgentApp
from agentscope_runtime.engine.deployers.fc_deployer import (
    FCDeployManager,
    OSSConfig,
    FCConfig,
)
from agentscope_runtime.engine.schemas.agent_schemas import AgentRequest
from agentscope_runtime.engine.services.agent_state import (
    InMemoryStateService,
)

logging.basicConfig(
    level=logging.DEBUG,  # 或 logging.INFO
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
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


# Define endpoints
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


async def deploy_app_to_fc():
    """Deploy AgentApp to Alibaba Cloud Function Compute (FC)"""

    # 1. Configure OSS
    oss_config = OSSConfig(
        # OSS AK/SK optional; fallback to Alibaba Cloud AK/SK
        access_key_id=os.environ.get(
            "OSS_ACCESS_KEY_ID",
            os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_ID"),
        ),
        access_key_secret=os.environ.get(
            "OSS_ACCESS_KEY_SECRET",
            os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_SECRET"),
        ),
        region=os.environ.get("OSS_REGION", "cn-hangzhou"),
        bucket_name=os.environ.get("OSS_BUCKET_NAME", "tmp-fc-deploy"),
    )

    # 2. Configure FC
    fc_config = FCConfig(
        access_key_id=os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_ID"),
        access_key_secret=os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_SECRET"),
        account_id=os.environ.get("FC_ACCOUNT_ID"),
        region_id=os.environ.get("FC_REGION_ID"),
    )

    # 3. Create FCDeployManager
    deployer = FCDeployManager(
        oss_config=oss_config,
        fc_config=fc_config,
        # build_root=os.path.dirname(__file__),
    )

    # 4. Deployment configuration
    deployment_config = {
        # Basic configuration
        # "function_name": "agent-app-example-20251224222832", # for update
        "deploy_name": f'agent-app-example-{time.strftime("%Y%m%d%H%M%S")}',
        "telemetry_enabled": True,
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
        # Environment variables
        "environment": {
            "PYTHONPATH": "/code",
            "LOG_LEVEL": "INFO",
            "DASHSCOPE_API_KEY": os.environ.get("DASHSCOPE_API_KEY"),
        },
    }

    try:
        print("🚀 Starting AgentApp deployment to Alibaba Cloud FC...")

        # 5. Execute deployment
        result = await agent_app.deploy(
            deployer,
            **deployment_config,
        )

        print("✅ Deployment successful!")
        print(f"📍 Deployment ID: {result['deploy_id']}")
        print(f"📦 Wheel path: {result['wheel_path']}")
        print(f"🌐 OSS file URL: {result['artifact_url']}")
        print(f"🏷️ Resource name: {result['resource_name']}")
        print(f"🏢 Function Name: {result['function_name']}")
        print(f"🔗 Endpoint URL: {result['endpoint_url']}")

        return result, deployer

    except Exception as e:
        print(f"❌ Deployment failed: {e}")
        raise


async def deploy_from_project_directory():
    """Deploy directly from project directory (without using AgentApp)"""

    # Configuration
    oss_config = OSSConfig.from_env()
    fc_config = FCConfig.from_env()

    deployer = FCDeployManager(
        oss_config=oss_config,
        fc_config=fc_config,
    )

    # Project deployment configuration
    project_config = {
        "project_dir": os.path.dirname(
            __file__,
        ),  # Current directory as project directory
        "cmd": "python agent_run.py",  # Startup command
        "deploy_name": "agent-app-project",
        "telemetry_enabled": True,
    }

    try:
        print("🚀 Starting deployment from project directory to FC...")

        result = await deployer.deploy(**project_config)

        print("✅ Project deployment successful!")
        print(f"📍 Deployment ID: {result['deploy_id']}")
        print(f"📦 Wheel path: {result['wheel_path']}")
        print(f"🌐 OSS file URL: {result['artifact_url']}")
        print(f"🏷️ Resource name: {result['resource_name']}")
        print(f"🏢 Function Name: {result['function_name']}")
        print(f"🔗 Endpoint URL: {result['endpoint_url']}")

        return result, deployer

    except Exception as e:
        print(f"❌ Project deployment failed: {e}")
        raise


async def deploy_from_existing_wheel():
    """Deploy from existing wheel file"""

    # Configuration
    oss_config = OSSConfig.from_env()
    fc_config = FCConfig.from_env()

    deployer = FCDeployManager(
        oss_config=oss_config,
        fc_config=fc_config,
    )

    # Assume there's an already built wheel file
    wheel_path = "/path/to/your/agent-app-1.0.0-py3-none-any.whl"

    wheel_config = {
        "external_whl_path": wheel_path,
        "deploy_name": "agent-app-from-wheel",
        "telemetry_enabled": True,
    }

    try:
        print("🚀 Starting deployment from Wheel file to FC...")

        result = await deployer.deploy(**wheel_config)

        print("✅ Wheel deployment successful!")
        print(f"📍 Deployment ID: {result['deploy_id']}")
        print(f"📦 Wheel path: {result['wheel_path']}")
        print(f"🌐 OSS file URL: {result['artifact_url']}")
        print(f"🏷️ Resource name: {result['resource_name']}")
        print(f"🏢 Function Name: {result['function_name']}")
        print(f"🔗 Endpoint URL: {result['endpoint_url']}")

        return result, deployer

    except Exception as e:
        print(f"❌ Wheel deployment failed: {e}")
        raise


async def main():
    """Main function - demonstrates different deployment methods"""
    print("🎯 FC AgentApp Deployment Example")
    print("=" * 50)

    # Check environment variables
    required_env_vars = [
        # OSS_ creds are optional; Alibaba Cloud creds are required
        "ALIBABA_CLOUD_ACCESS_KEY_ID",
        "ALIBABA_CLOUD_ACCESS_KEY_SECRET",
        "FC_ACCOUNT_ID",
        "DASHSCOPE_API_KEY",
    ]

    missing_vars = [
        var for var in required_env_vars if not os.environ.get(var)
    ]
    if missing_vars:
        print(
            f"❌ Missing required environment vars: {', '.join(missing_vars)}",
        )
        print("\nPlease set the following environment variables:")
        for var in missing_vars:
            print(f"export {var}=your_value")
        return

    deployment_type = input(
        "\nChoose deployment method:\n"
        "1. Deploy using AgentApp (Recommended)\n"
        "2. Deploy directly from project directory\n"
        "3. Deploy from existing Wheel file\n"
        "Please enter your choice (1-3): ",
    ).strip()

    try:
        if deployment_type == "1":
            result, _ = await deploy_app_to_fc()
        elif deployment_type == "2":
            result, _ = await deploy_from_project_directory()
        elif deployment_type == "3":
            result, _ = await deploy_from_existing_wheel()
        else:
            print("❌ Invalid choice")
            return

        # Display different usage instructions based on deployment type
        if deployment_type == "1":
            print(
                f"""
        Deployment completed! Detailed information has been
        saved to the output file.

        📝 Deployment Information:
        - Deployment ID: {result['deploy_id']}
        - Resource Name: {result['resource_name']}
        - Function Name: {result['function_name']}

        🔗 Check deployment status in FC console:
            {result['url']}

        📋 Next Steps:
        1. Check deployment status in FC console
        2. After successful deployment, you can access your AgentApp through
           the API endpoints provided by FC:

           # Health check
           curl {result['endpoint_url']}/health

           # Test sync endpoint
           # Add "x-agentscope-runtime-session-id" header
           # to bound a fixed instance
           curl -X POST {result['endpoint_url']}/sync \\
             -H "Content-Type: application/json" \\
             -H "x-agentscope-runtime-session-id: 123" \\
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
           # Add "x-agentscope-runtime-session-id" header
           # to bound a fixed instance
           curl -X POST {result['endpoint_url']}/async \\
             -H "Content-Type: application/json" \\
             -H "x-agentscope-runtime-session-id: 123" \\
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
           # Add "x-agentscope-runtime-session-id" header
           # to bound a fixed instance
           curl -X POST {result['endpoint_url']}/stream_async \\
             -H "Content-Type: application/json" \\
             -H "Accept: text/event-stream" \\
             -H "x-agentscope-runtime-session-id: 123" \\
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

        3. Configure gateway and domain name (if needed)
        """,
            )
        else:
            print(
                f"""
        Deployment completed! Detailed information has been
        saved to the output file.

        📝 Deployment Information:
        - Deployment ID: {result['deploy_id']}
        - Resource Name: {result['resource_name']}
        - Function Name: {result['function_name']}

        🔗 Check deployment status in FC console: {result['url']}

        📋 Next Steps:
        1. Check deployment status in FC console
        2. After successful deployment, you can access your Agent through the
           API endpoint provided by FC: {result['endpoint_url']}
        3. Configure gateway and domain name (if needed)
        """,
            )

    except Exception as e:
        print(f"❌ Error occurred during execution: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    # Run deployment
    asyncio.run(main())
