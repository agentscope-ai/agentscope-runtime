# -*- coding: utf-8 -*-
# pylint: disable=redefined-outer-name, protected-access, unused-argument
"""
AgentBay sandbox demo tests adapted to sandbox test style.
- Loads .env if present
- Skips gracefully when SDK or API key is missing
"""
import os

import pytest
from dotenv import load_dotenv

from agentscope_runtime.sandbox.box.agentbay.agentbay_sandbox import (
    AgentbaySandbox,
)
from agentscope_runtime.sandbox.enums import SandboxType
from agentscope_runtime.engine.services.sandbox_service import SandboxService
from agentscope_runtime.engine.services.environment_manager import (
    create_environment_manager,
)


@pytest.fixture
def env():
    # Align with existing tests under tests/sandbox
    if os.path.exists("../../.env"):
        load_dotenv("../../.env")


def _has_agentbay_sdk() -> bool:
    try:
        import agentbay  # noqa: F401  # pylint: disable=unused-import

        return True
    except Exception:
        return False


@pytest.mark.skipif(
    not _has_agentbay_sdk() or not os.getenv("AGENTBAY_API_KEY"),
    reason="AgentBay SDK or AGENTBAY_API_KEY not available",
)
def test_agentbay_sandbox_direct(env):  # noqa: ARG001
    api_key = os.getenv("AGENTBAY_API_KEY")
    # Basic happy path: create sandbox and run minimal commands
    with AgentbaySandbox(api_key=api_key, image_id="linux_latest") as box:
        # List tools
        tools = box.list_tools()
        print("tools:", tools)

        # Run a trivial shell command
        res_cmd = box.call_tool(
            "run_shell_command",
            {"command": "echo 'Hello from AgentBay!'"},
        )
        print("run_shell_command:", res_cmd)

        # File write/read
        res_write = box.call_tool(
            "write_file",
            {
                "path": "/tmp/test.txt",
                "content": "Hello from AgentBay sandbox!",
            },
        )
        print("write_file:", res_write)

        res_read = box.call_tool("read_file", {"path": "/tmp/test.txt"})
        print("read_file:", res_read)

        # Session info
        info = box.get_session_info()
        print("session_info:", info)


@pytest.mark.skipif(
    not _has_agentbay_sdk() or not os.getenv("AGENTBAY_API_KEY"),
    reason="AgentBay SDK or AGENTBAY_API_KEY not available",
)
def test_agentbay_sandbox_minimal_browser(env):  # noqa: ARG001
    """Optional: if image supports browser_* tools, run a smoke check.
    This test does not assert success strictly; it prints results for
    manual check similar to other sandbox demos. It won't fail CI if the
    selected image doesn't support browser tools.
    """
    api_key = os.getenv("AGENTBAY_API_KEY")
    with AgentbaySandbox(api_key=api_key, image_id="browser_latest") as box:
        tools = box.list_tools()
        print("tools:", tools)

        res_nav = box.call_tool(
            "browser_navigate",
            {"url": "https://example.com"},
        )
        print("browser_navigate:", res_nav)


@pytest.mark.asyncio
@pytest.mark.skipif(
    not _has_agentbay_sdk() or not os.getenv("AGENTBAY_API_KEY"),
    reason="AgentBay SDK or AGENTBAY_API_KEY not available",
)
async def test_agentbay_sandbox_via_service(env):  # noqa: ARG001
    """Create AgentBay sandbox via SandboxService and run a tiny smoke test."""
    api_key = os.getenv("AGENTBAY_API_KEY")
    service = SandboxService(bearer_token=api_key)

    async with create_environment_manager(sandbox_service=service) as em:
        sandboxes = em.connect_sandbox(
            session_id="sbx_demo_session",
            user_id="sbx_demo_user",
            env_types=[SandboxType.AGENTBAY.value],
        )
        assert sandboxes and len(sandboxes) > 0
        box = sandboxes[0]

        print("list_tools:", box.list_tools())

        res_cmd = box.call_tool(
            "run_shell_command",
            {"command": "echo 'Service path OK'"},
        )
        print("run_shell_command:", res_cmd)

        res_write = box.call_tool(
            "write_file",
            {"path": "/tmp/service_test.txt", "content": "hello"},
        )
        print("write_file:", res_write)

        res_read = box.call_tool(
            "read_file",
            {"path": "/tmp/service_test.txt"},
        )
        print("read_file:", res_read)
