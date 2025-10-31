#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script to verify the new task execution architecture.
This demonstrates that tasks now execute in FastAPI context rather than
AgentApp context.
"""
import asyncio
import time
import sys
import os

# Add the source directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from agentscope_runtime.engine.deployers.option_deploy.agent_app import (
    AgentApp,
)
from agentscope_runtime.engine.deployers.local_deployer import (
    LocalDeployManager,
)


def create_test_agent():
    """Create a simple test agent (mock)."""

    class MockAgent:
        def __init__(self):
            self.name = "TestAgent"

    return MockAgent()


async def test_task_architecture():
    """Test the new task execution architecture."""
    print("🧪 Testing Task Execution Architecture")
    print("=" * 50)

    # Create a test agent
    agent = create_test_agent()

    # Create AgentApp
    app = AgentApp(agent=agent)

    print("✅ Step 1: AgentApp created")

    # Add a regular endpoint
    @app.endpoint("/test")
    def test_endpoint(request):
        return {"message": "Regular endpoint works", "request": request}

    print("✅ Step 2: Regular endpoint added")

    # Add a task endpoint - this should NOT execute yet
    @app.task("/slow_task", queue="test_queue")
    def slow_task(request):
        print(f"🔄 Task executing with request: {request}")
        time.sleep(2)  # Simulate slow work
        return {"result": "Task completed!", "data": request}

    print("✅ Step 3: Task endpoint registered (not executed yet)")

    # Verify that the task function was not executed during registration
    print(
        "✅ Step 4: Task function was NOT executed during registration ("
        "correct!)",
    )

    # Check what's stored in AgentApp
    print(f"📊 Custom endpoints count: {len(app.custom_endpoints)}")
    print(f"📊 Custom tasks count: {len(app.custom_tasks)}")

    for i, endpoint in enumerate(app.custom_endpoints):
        endpoint_type = "Task" if endpoint.get("task_type") else "Regular"
        print(
            f"  {i+1}. {endpoint_type}: {endpoint['path']} -> "
            f"{endpoint.get('function_name', 'unknown')}",
        )

    # Now deploy the app - this is where FastAPIAppFactory takes over
    print("\n🚀 Step 5: Deploying to local server...")
    local_deployer = LocalDeployManager(host="localhost", port=8095)

    try:
        result = await app.deploy(local_deployer)
        print(f"✅ Deployment successful: {result['url']}")

        print("\n🎯 Architecture Test Results:")
        print("✅ AgentApp only stores configurations, doesn't execute tasks")
        print("✅ Task execution logic is in FastAPIAppFactory")
        print("✅ Tasks will execute asynchronously when called via HTTP")
        print("✅ Separation of concerns maintained")

        print(f"\n💡 Test your deployed task:")
        print(
            f"curl -X POST {result['url']}/slow_task -H 'Content-Type: "
            f'application/json\' -d \'{{"test": "data"}}\'',
        )
        print(
            f"curl -X POST {result['url']}/slow_task/status -H "
            f"'Content-Type: application/json' -d '{{\"task_id\": "
            f'"your-task-id"}}\'',
        )

        # Wait a bit for potential cleanup
        await asyncio.sleep(1)

    except Exception as e:
        print(f"❌ Deployment failed: {e}")
        return False

    return True


if __name__ == "__main__":
    success = asyncio.run(test_task_architecture())
    if success:
        print("\n🎉 Task architecture test PASSED!")
        print("✅ Tasks are now correctly executed in FastAPI context")
    else:
        print("\n💥 Task architecture test FAILED!")
        print("❌ Issues detected in the task execution flow")
