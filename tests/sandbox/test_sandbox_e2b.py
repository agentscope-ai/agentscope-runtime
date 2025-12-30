# -*- coding: utf-8 -*-
# pylint: disable=redefined-outer-name, protected-access, unused-argument
"""
E2B sandbox demo tests adapted to sandbox test style.
- Loads .env if present
- Skips gracefully when SDK or API key is missing
"""
import os

import pytest
from dotenv import load_dotenv

from agentscope_runtime.sandbox.box.e2b import (
    E2bSandBox,
)
from agentscope_runtime.sandbox.enums import SandboxType
from agentscope_runtime.engine.services.sandbox import SandboxService


@pytest.fixture
def env():
    # Align with existing tests under tests/sandbox
    if os.path.exists("../../.env"):
        load_dotenv("../../.env")


def _has_e2b_sdk() -> bool:
    try:
        import e2b  # noqa: F401  # pylint: disable=unused-import

        return True
    except Exception:
        return False


@pytest.mark.skipif(
    not _has_e2b_sdk() or not os.getenv("E2B_API_KEY"),
    reason="E2B SDK or E2B_API_KEY not available",
)
def test_e2b_sandbox_direct(env):  # noqa: ARG001
    """Test E2BSandbox directly with basic operations."""

    # Basic happy path: create sandbox and run minimal commands
    with E2bSandBox() as box:
        # List tools
        tools = box.list_tools()
        print("E2B tools:", tools)

        # Run a trivial shell command
        res_cmd = box.call_tool(
            "run_shell_command",
            {"command": "echo 'Hello from E2B!'"},
        )
        print("run_shell_command:", res_cmd)

        # screenshot
        res_screenshot = box.call_tool(
            "screenshot",
            {"file_path": f"{os.getcwd()}/screenshot.png"},
        )
        print("screenshot:", res_screenshot)


@pytest.mark.asyncio
@pytest.mark.skipif(
    not _has_e2b_sdk()
    or not os.getenv("E2B_API_KEY")
    or not os.getenv("DOCKER_HOST"),
    reason="E2B SDK or E2B_API_KEY or DOCKER_HOST not available",
)
async def test_e2b_sandbox_via_service(env):  # noqa: ARG001
    """Create E2B sandbox via SandboxService and run a tiny smoke test."""
    service = SandboxService()

    async with service:
        sandboxes = service.connect(
            session_id="e2b_demo_session",
            user_id="e2b_demo_user",
            sandbox_types=[SandboxType.E2B.value],
        )
        assert sandboxes and len(sandboxes) > 0
        box = sandboxes[0]

        print("E2B list_tools:", box.list_tools())

        res_cmd = box.call_tool(
            "run_shell_command",
            {"command": "echo 'Service path OK'"},
        )
        print("E2B run_shell_command:", res_cmd)

        # screenshot
        res_screenshot = box.call_tool(
            "screenshot",
            {"file_path": f"{os.getcwd()}/screenshot.png"},
        )
        print("screenshot:", res_screenshot)
