# -*- coding: utf-8 -*-
# pylint: disable=unused-argument

import asyncio
import os

import pytest
from agentscope.agent import ReActAgent
from agentscope.formatter import DashScopeChatFormatter
from agentscope.model import DashScopeChatModel
from agentscope.pipeline import stream_printing_messages
from agentscope.memory import InMemoryMemory

from agentscope_runtime.engine.app import AgentApp
from agentscope_runtime.engine.deployers.adapter.a2a import (
    A2AFastAPIDefaultAdapter,
)
from agentscope_runtime.engine.deployers.local_deployer import (
    LocalDeployManager,
)
from agentscope_runtime.engine.schemas.agent_schemas import AgentRequest
from agentscope_runtime.engine.services.agent_state import (
    InMemoryStateService,
)


def local_deploy():
    asyncio.run(_local_deploy())


async def _local_deploy():
    from dotenv import load_dotenv

    load_dotenv()

    server_port = int(os.environ.get("SERVER_PORT", "8090"))
    server_endpoint = os.environ.get("SERVER_ENDPOINT", "agent")

    deploy_id = ""
    # Create AgentApp
    agent_app = AgentApp(
        app_name="Friday",
        app_description="A helpful assistant",
    )

    # Initialize services
    @agent_app.init
    async def init_func(self):
        self.state_service = InMemoryStateService()
        await self.state_service.start()

    @agent_app.shutdown
    async def shutdown_func(self):
        await self.state_service.stop()

    # Define query handler
    @agent_app.query(framework="agentscope")
    async def query_func(
        self,
        msgs,
        request: AgentRequest = None,
        **kwargs,
    ):
        session_id = request.session_id
        user_id = request.user_id

        state = await self.state_service.export_state(
            session_id=session_id,
            user_id=user_id,
        )

        agent = ReActAgent(
            name="Friday",
            model=DashScopeChatModel(
                "qwen-turbo",
                api_key=os.getenv("DASHSCOPE_API_KEY"),
                stream=True,
            ),
            sys_prompt="You're a helpful assistant named Friday.",
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

    # Create A2A protocol adapter
    a2a_protocol = A2AFastAPIDefaultAdapter(
        agent_name="Friday",
        agent_description="A helpful assistant",
    )

    deploy_manager = LocalDeployManager(host="localhost", port=server_port)
    try:
        deployment_info = await agent_app.deploy(
            deploy_manager,
            endpoint_path=f"/{server_endpoint}",
            protocol_adapters=[a2a_protocol],
        )
        deploy_id = deployment_info["deploy_id"]

        print("✅ Service deployed successfully!")
        print(f"   URL: {deployment_info['url']}")
        print(f"   Endpoint: {deployment_info['url']}/{server_endpoint}")
        print("\nAgent Service is running in the background.")

        # Run the service for a short duration
        await asyncio.sleep(1)

    except (KeyboardInterrupt, asyncio.CancelledError):
        # This block will be executed when you press Ctrl+C.
        print("\nShutdown signal received. Stopping the service...")
        if deploy_manager.is_running:
            await deploy_manager.stop(deploy_id)
        print("✅ Service stopped.")
    except Exception as e:
        print(f"An error occurred: {e}")
        if deploy_manager.is_running:
            await deploy_manager.stop(deploy_id)
    finally:
        if deploy_manager.is_running:
            await deploy_manager.stop(deploy_id)
        print("✅ Service stopped after test.")


@pytest.mark.asyncio
async def test_local_deployer_a2a():
    await _local_deploy()
