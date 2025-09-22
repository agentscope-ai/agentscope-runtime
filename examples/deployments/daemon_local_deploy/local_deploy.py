# -*- coding: utf-8 -*-
import asyncio
from contextlib import asynccontextmanager

from agentscope_runtime.engine.deployers.local_deployer import (
    LocalDeployManager,
)
from agentscope_runtime.engine.runner import Runner
from agentscope_runtime.engine.services.context_manager import ContextManager
from agentscope_runtime.engine.services.session_history_service import (
    InMemorySessionHistoryService,
)
from agentscope_runtime.engine.services.environment_manager import (
    create_environment_manager,
)
from agentscope_runtime.engine.services.sandbox_service import SandboxService
from agentscope_runtime.engine.agents.llm_agent import LLMAgent
from agentscope_runtime.engine.llms.qwen_llm import QwenLLM
from agentscope_runtime.sandbox.tools.filesystem import (
    run_ipython_cell,
    edit_file,
)

USER_ID = "user_1"
SESSION_ID = "session_001"  # Using a fixed ID for simplicity


async def prepare_context():
    session_history_service = InMemorySessionHistoryService()
    await session_history_service.create_session(
        user_id=USER_ID,
        session_id=SESSION_ID,
    )
    context_manager = ContextManager(
        session_history_service=session_history_service,
    )

    return context_manager


@asynccontextmanager
async def create_runner():
    # create agent
    agent = LLMAgent(
        model=QwenLLM(),
        name="Friday",
        agent_config={
            "sys_prompt": "You're a helpful assistant named {name}.",
        },
        tools=[
            run_ipython_cell,
            edit_file,
        ],
    )

    context_manager = await prepare_context()
    async with context_manager:
        async with create_environment_manager(
            sandbox_service=SandboxService(),
        ) as env_manager:
            runner = Runner(
                agent=agent,
                context_manager=context_manager,
                environment_manager=env_manager,
            )
            print("✅ Runner created successfully")
            yield runner


async def deploy_agent(runner):
    # Create deployment manager
    deploy_manager = LocalDeployManager(
        host="localhost",
        port=8090,
    )

    # Deploy agent as streaming service
    deploy_result = await runner.deploy(
        deploy_manager=deploy_manager,
        endpoint_path="/process",
        stream=True,  # Enable streaming responses
    )
    print(f"🚀 Agent deployed at: {deploy_result}")
    print(f"🌐 Service URL: {deploy_result['url']}")
    print(f"💚 Health check: {deploy_result['url']}/health")
    print(
        f"""
    🎯 Service deployment completed, you can test with the following commands:

    # Health check
    curl {deploy_result['url']}/health

    # Streaming request
    curl -X POST {deploy_result['url']}/process \\
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
    return deploy_manager


async def run_deployment():
    async with create_runner() as runner:
        deploy_manager = await deploy_agent(runner)

    # Keep the service running (in production, you'd handle this differently)
    print("🏃 Service is running...")

    return deploy_manager


async def main():
    try:
        deploy_manager = await run_deployment()

        # Keep the main script alive. The server is running in a daemon thread.
        while True:
            await asyncio.sleep(1)

    except (KeyboardInterrupt, asyncio.CancelledError):
        # This block will be executed when you press Ctrl+C.
        print("\nShutdown signal received. Stopping the service...")
        if deploy_manager.is_running:
            await deploy_manager.stop()
        print("✅ Service stopped.")
    except Exception as e:
        print(f"An error occurred: {e}")
        if deploy_manager.is_running:
            await deploy_manager.stop()


if __name__ == "__main__":
    asyncio.run(main())
