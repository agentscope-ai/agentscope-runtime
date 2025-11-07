# -*- coding: utf-8 -*-
# pylint: disable=redefined-outer-name, unused-argument, protected-access
"""
Integrated test: AgentScope + AgentBay sandbox via SandboxService.
- Loads ../../.env if present
- Skips if required API keys are missing
- Runs a minimal end-to-end flow: setup env, create agent, perform a tiny task
"""
import os

import pytest

from agentscope_runtime.sandbox.enums import SandboxType
from agentscope_runtime.engine.services.sandbox_service import SandboxService
from agentscope_runtime.engine.services.environment_manager import (
    create_environment_manager,
)


@pytest.fixture
def env():
    if os.path.exists("../../.env"):
        from dotenv import load_dotenv

        load_dotenv("../../.env")


def _has_required_env() -> bool:
    return bool(
        os.getenv("DASHSCOPE_API_KEY") and os.getenv("AGENTBAY_API_KEY"),
    )


@pytest.mark.asyncio
@pytest.mark.skipif(
    not _has_required_env(),
    reason="Missing required API keys",
)
async def test_agentscope_agent_with_agentbay_sandbox(env):  # noqa: ARG001
    from agentscope import init, agent
    from agentscope.model import DashScopeChatModel
    from agentscope.formatter import DashScopeChatFormatter
    from agentscope.tool import Toolkit, ToolResponse
    from agentscope.message import Msg

    # Setup SandboxService and EnvironmentManager
    sandbox_service = SandboxService(
        bearer_token=os.getenv("AGENTBAY_API_KEY"),
    )

    async with create_environment_manager(
        sandbox_service=sandbox_service,
    ) as em:
        sandboxes = em.connect_sandbox(
            session_id="itest_session",
            user_id="itest_user",
            env_types=[SandboxType.AGENTBAY.value],
        )
        assert sandboxes and len(sandboxes) > 0
        box = sandboxes[0]

        # Setup AgentScope agent
        init()
        model = DashScopeChatModel(
            model_name="qwen-max",
            api_key=os.getenv("DASHSCOPE_API_KEY"),
        )
        formatter = DashScopeChatFormatter()

        toolkit = Toolkit()

        async def write_file(path: str, content: str) -> ToolResponse:
            res = box.call_tool(
                "write_file",
                {"path": path, "content": content},
            )
            if res.get("success"):
                return ToolResponse(content=f"Wrote to {path}")
            return ToolResponse(
                content=f"Failed: {res.get('error', 'Unknown')}",
            )

        async def read_file(path: str) -> ToolResponse:
            res = box.call_tool("read_file", {"path": path})
            if res.get("success"):
                return ToolResponse(
                    content=f"Read {path}:\n{res.get('content','')}",
                )
            return ToolResponse(
                content=f"Failed: {res.get('error', 'Unknown')}",
            )

        toolkit.register_tool_function(
            write_file,
            func_description="Write file in sandbox",
        )
        toolkit.register_tool_function(
            read_file,
            func_description="Read file in sandbox",
        )

        test_agent = agent.ReActAgent(
            name="CloudAssistant",
            sys_prompt="You can write and read files in a cloud sandbox.",
            model=model,
            formatter=formatter,
            toolkit=toolkit,
        )

        # Run a tiny e2e task
        msg = Msg(
            name="user",
            role="user",
            content="Create /tmp/itest.txt with 'hello' then read it",
        )
        _ = await test_agent.reply(msg)

        # Smoke-check the underlying sandbox operations directly
        w = box.call_tool(
            "write_file",
            {"path": "/tmp/itest2.txt", "content": "hi"},
        )
        assert w.get("success") is True
        r = box.call_tool("read_file", {"path": "/tmp/itest2.txt"})
        assert r.get("success") is True
