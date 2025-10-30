# -*- coding: utf-8 -*-
"""
Example showing how to use AgentApp with custom endpoints
for deployment to various platforms including ModelStudio.
"""
import os
import asyncio

from agentscope_runtime.engine.deployers.option_deploy.agent_app import (
    AgentApp,
)
from agentscope_runtime.engine.agents.agentscope_agent import AgentScopeAgent
from agentscope_runtime.engine.deployers.local_deployer import (
    LocalDeployManager,
)
from agentscope_runtime.engine.deployers.modelstudio_deployer import (
    ModelstudioDeployManager,
    OSSConfig,
    ModelstudioConfig,
)

from agentscope.agent import ReActAgent
from agentscope.model import DashScopeChatModel


# Define custom endpoint functions in this module so they can be imported
def sync_handler(request):
    """Synchronous custom endpoint handler."""
    return {
        "status": "ok",
        "type": "sync",
        "message": "Hello from sync endpoint",
        "request_data": request,
    }


async def async_handler(request):
    """Asynchronous custom endpoint handler."""
    await asyncio.sleep(0.1)  # Simulate async work
    return {
        "status": "ok",
        "type": "async",
        "message": "Hello from async endpoint",
        "request_data": request,
    }


async def stream_async_handler(request):
    """Asynchronous streaming endpoint handler."""
    for i in range(5):
        await asyncio.sleep(0.2)
        yield f"async chunk {i}: {request.get('message', 'no message')}\n"


def stream_sync_handler(request):
    """Synchronous streaming endpoint handler."""
    for i in range(3):
        yield f"sync chunk {i}: {request.get('message', 'no message')}\n"


def health_check_custom(request):
    """Custom health check endpoint."""
    return {
        "status": "healthy",
        "service": "custom-agent-app",
        "version": "1.0.0",
        "custom": True,
    }


async def create_agent_app():
    """Create AgentApp with custom endpoints."""

    # Create agent
    agent = AgentScopeAgent(
        name="CustomAgent",
        model=DashScopeChatModel(
            "qwen-turbo",
            api_key=os.getenv("DASHSCOPE_API_KEY"),
        ),
        agent_config={
            "sys_prompt": "You're a helpful assistant with custom endpoints.",
        },
        agent_builder=ReActAgent,
    )

    # Create AgentApp
    app = AgentApp(agent=agent)

    # Add custom endpoints using decorators
    @app.endpoint("/sync")
    def sync_endpoint(request):
        return sync_handler(request)

    @app.endpoint("/async")
    async def async_endpoint(request):
        return await async_handler(request)

    @app.endpoint("/stream_async")
    async def stream_async_endpoint(request):
        async for chunk in stream_async_handler(request):
            yield chunk

    @app.endpoint("/stream_sync")
    def stream_sync_endpoint(request):
        for chunk in stream_sync_handler(request):
            yield chunk

    @app.endpoint("/health_custom")
    def health_custom_endpoint(request):
        return health_check_custom(request)

    # Add custom task endpoints - these now run truly asynchronously
    @app.task("/background_task", queue="default")
    def long_running_task(request):
        # Simulate long-running work
        import time

        time.sleep(5)  # This won't block other requests now
        result = f"Long task completed with data: {request}"
        return {"processed": result, "duration": "5 seconds"}

    @app.task("/async_background_task", queue="async_queue")
    async def async_long_running_task(request):
        # Simulate async long-running work
        await asyncio.sleep(3)
        result = f"Async task completed with data: {request}"
        return {"processed": result, "duration": "3 seconds"}

    # You can also add endpoints programmatically
    app.add_endpoint(
        "/programmatic",
        lambda req: {"added": "programmatically"},
    )

    return app


async def deploy_to_local():
    """Deploy AgentApp to local server with custom endpoints."""
    print("🚀 Deploying AgentApp with custom endpoints to local server...")

    app = await create_agent_app()

    # Deploy to local server
    local_deployer = LocalDeployManager(
        host="localhost",
        port=8090,
    )

    result = await app.deploy(local_deployer)

    print(f"✅ Local deployment successful!")
    print(f"🌐 Service URL: {result['url']}")
    print(f"📋 Available endpoints:")
    print(f"  - {result['url']}/process (main agent endpoint)")
    print(f"  - {result['url']}/sync (custom sync endpoint)")
    print(f"  - {result['url']}/async (custom async endpoint)")
    print(f"  - {result['url']}/stream_async (custom async streaming)")
    print(f"  - {result['url']}/stream_sync (custom sync streaming)")
    print(f"  - {result['url']}/health_custom (custom health check)")
    print(f"  - {result['url']}/background_task (async background task)")
    print(f"  - {result['url']}/background_task/status (task status check)")
    print(f"  - {result['url']}/async_background_task (async background task)")
    print(
        f"  - {result['url']}/async_background_task/status (async task status check)",
    )
    print(f"  - {result['url']}/programmatic (programmatically added)")
    print(f"  - {result['url']}/health (standard health check)")

    return result


async def deploy_to_modelstudio():
    """Deploy AgentApp to ModelStudio with custom endpoints."""
    print("🚀 Deploying AgentApp with custom endpoints to ModelStudio...")

    app = await create_agent_app()

    # Configure ModelStudio deployment
    oss_config = OSSConfig(
        access_key_id=os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_ID"),
        access_key_secret=os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_SECRET"),
    )

    modelstudio_config = ModelstudioConfig(
        workspace_id=os.environ.get("MODELSTUDIO_WORKSPACE_ID"),
        access_key_id=os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_ID"),
        access_key_secret=os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_SECRET"),
        dashscope_api_key=os.environ.get("DASHSCOPE_API_KEY"),
    )

    modelstudio_deployer = ModelstudioDeployManager(
        oss_config=oss_config,
        modelstudio_config=modelstudio_config,
    )

    # Deploy with custom configuration
    result = await app.deploy(
        modelstudio_deployer,
        deploy_name="agent-with-custom-endpoints",
        requirements=[
            "agentscope",
            "fastapi",
            "uvicorn",
        ],
        environment={
            "DASHSCOPE_API_KEY": os.environ.get("DASHSCOPE_API_KEY"),
        },
    )

    print(f"✅ ModelStudio deployment successful!")
    print(f"📍 Deployment ID: {result['deploy_id']}")
    print(f"📦 Wheel path: {result['wheel_path']}")
    print(f"🌐 OSS file URL: {result['artifact_url']}")
    print(f"🏷️ Resource name: {result['resource_name']}")
    print(f"🏢 Workspace ID: {result['workspace_id']}")
    print(f"📊 Console URL: {result['url']}")

    return result


async def main():
    """Main function to demonstrate custom endpoints deployment."""
    print("🎯 AgentApp Custom Endpoints Deployment Example")
    print("=" * 60)

    deployment_type = input(
        "\nChoose deployment target:\n"
        "1. Local server (immediate testing)\n"
        "2. ModelStudio (cloud deployment)\n"
        "Please enter your choice (1-2): ",
    ).strip()

    try:
        if deployment_type == "1":
            result = await deploy_to_local()
            print("\n💡 Test your custom endpoints with curl:")
            print(
                f"curl -X POST {result['url']}/sync -H 'Content-Type: application/json' -d '{{}}'",
            )
            print(
                f"curl -X POST {result['url']}/async -H 'Content-Type: application/json' -d '{{}}'",
            )
            print(
                f"curl -X POST {result['url']}/health_custom -H 'Content-Type: application/json' -d '{{}}'",
            )
            print(f"\n💡 Test background tasks:")
            print(f"# Submit a background task")
            print(
                f"curl -X POST {result['url']}/background_task -H 'Content-Type: application/json' -d '{{\"data\": \"test\"}}'",
            )
            print(f"# Check task status (use task_id from previous response)")
            print(
                f"curl -X GET {result['url']}/background_task/status -H 'Content-Type: application/json' -d '{{\"task_id\": \"your-task-id\"}}'",
            )

        elif deployment_type == "2":
            # Check required environment variables
            required_env_vars = [
                "MODELSTUDIO_WORKSPACE_ID",
                "ALIBABA_CLOUD_ACCESS_KEY_ID",
                "ALIBABA_CLOUD_ACCESS_KEY_SECRET",
                "DASHSCOPE_API_KEY",
            ]

            missing_vars = [
                var for var in required_env_vars if not os.environ.get(var)
            ]
            if missing_vars:
                print(
                    f"❌ Missing required environment variables: {', '.join(missing_vars)}",
                )
                return

            result = await deploy_to_modelstudio()
            print(
                "\n📋 Once deployed, all custom endpoints will be available via ModelStudio API gateway",
            )

        else:
            print("❌ Invalid choice")
            return

    except Exception as e:
        print(f"❌ Deployment failed: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
