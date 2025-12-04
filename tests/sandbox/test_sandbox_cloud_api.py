# -*- coding: utf-8 -*-
# pylint: disable=redefined-outer-name, protected-access, unused-argument
"""
Cloud API sandbox demo tests adapted to sandbox test style.
- Loads .env if present
- Skips gracefully when required environment variables are missing
"""
import os

import pytest
from dotenv import load_dotenv
from agentscope_runtime.sandbox.enums import SandboxType
from agentscope_runtime.engine.services.sandbox import SandboxService


@pytest.fixture
def env():
    # Align with existing tests under tests/sandbox
    if os.path.exists("../../.env"):
        load_dotenv("../../.env")


def _has_cloud_api_dependencies() -> bool:
    try:
        __import__(
            "agentscope_runtime.sandbox.box.cloud_api.cloud_computer_sandbox",
        )
        __import__(
            "agentscope_runtime.sandbox.box.cloud_api.cloud_phone_sandbox",
        )
        return True
    except ImportError:
        return False


@pytest.mark.skipif(
    not _has_cloud_api_dependencies()
    or not os.getenv("DESKTOP_ID")
    or not os.getenv("ECD_USERNAME")
    or not os.getenv("ECD_APP_STREAM_REGION_ID")
    or not os.getenv("ECD_ALIBABA_CLOUD_REGION_ID")
    or not os.getenv("ECD_ALIBABA_CLOUD_ENDPOINT")
    or not os.getenv("ECD_ALIBABA_CLOUD_ACCESS_KEY_ID")
    or not os.getenv("ECD_ALIBABA_CLOUD_ACCESS_KEY_SECRET")
    or not os.getenv("EDS_OSS_ACCESS_KEY_ID")
    or not os.getenv("EDS_OSS_ACCESS_KEY_SECRET")
    or not os.getenv("EDS_OSS_BUCKET_NAME")
    or not os.getenv("EDS_OSS_ENDPOINT")
    or not os.getenv("EDS_OSS_PATH"),
    reason="Cloud Computer dependencies or required "
    "environment variables not available",
)
def test_cloud_computer_sandbox_direct(env):  # noqa: ARG001
    """Test CloudComputerSandbox directly with basic operations."""
    from agentscope_runtime.sandbox.box.cloud_api import (
        CloudComputerSandbox,
    )

    desktop_id = os.getenv("DESKTOP_ID")

    # Basic happy path: create sandbox and run minimal commands
    with CloudComputerSandbox(desktop_id=desktop_id) as box:
        # List tools
        tools = box.list_tools()
        print("CloudComputer tools:", tools)

        # Run a trivial shell command
        res_cmd = box.call_tool(
            "run_shell_command",
            {"command": "echo 'Hello from Cloud Computer!'"},
        )
        print("run_shell_command:", res_cmd)

        # Screenshot
        res_screenshot = box.call_tool(
            "screenshot",
            {"file_name": "test_screenshot.png"},
        )
        print("screenshot:", res_screenshot)

        # File operations
        res_write = box.call_tool(
            "write_file",
            {
                "file_path": "C:/cloud_test.txt",
                "content": "Hello from Cloud Computer sandbox!",
            },
        )
        print("write_file:", res_write)

        res_read = box.call_tool(
            "read_file",
            {"file_path": "C:/cloud_test.txt"},
        )
        print("read_file:", res_read)

        # UI operations
        res_home = box.call_tool("go_home", {})
        print("go_home:", res_home)


@pytest.mark.skipif(
    not _has_cloud_api_dependencies()
    or not os.getenv("PHONE_INSTANCE_ID")
    or not os.getenv("EDS_ALIBABA_CLOUD_ENDPOINT")
    or not os.getenv("EDS_ALIBABA_CLOUD_ACCESS_KEY_ID")
    or not os.getenv("EDS_ALIBABA_CLOUD_ACCESS_KEY_SECRET")
    or not os.getenv("EDS_OSS_ACCESS_KEY_ID")
    or not os.getenv("EDS_OSS_ACCESS_KEY_SECRET")
    or not os.getenv("EDS_OSS_BUCKET_NAME")
    or not os.getenv("EDS_OSS_ENDPOINT")
    or not os.getenv("EDS_OSS_PATH"),
    reason="Cloud Phone dependencies or required "
    "environment variables not available",
)
def test_cloud_phone_sandbox_direct(env):  # noqa: ARG001
    """Test CloudPhoneSandbox directly with basic operations."""
    from agentscope_runtime.sandbox.box.cloud_api import (
        CloudPhoneSandbox,
    )

    instance_id = os.getenv("PHONE_INSTANCE_ID")

    with CloudPhoneSandbox(instance_id=instance_id) as box:
        # List tools
        tools = box.list_tools()
        print("CloudPhone tools:", tools)

        # Run a trivial shell command
        res_cmd = box.call_tool(
            "run_shell_command",
            {"command": "echo 'Hello from Cloud Phone!'"},
        )
        print("run_shell_command:", res_cmd)

        # Screenshot
        res_screenshot = box.call_tool(
            "screenshot",
            {"file_name": "phone_screenshot.png"},
        )
        print("screenshot:", res_screenshot)

        # Navigation operations
        res_home = box.call_tool("go_home", {})
        print("go_home:", res_home)


@pytest.mark.asyncio
@pytest.mark.skipif(
    not _has_cloud_api_dependencies()
    or not os.getenv("DESKTOP_ID")
    or not os.getenv("ECD_USERNAME")
    or not os.getenv("ECD_APP_STREAM_REGION_ID")
    or not os.getenv("ECD_ALIBABA_CLOUD_REGION_ID")
    or not os.getenv("ECD_ALIBABA_CLOUD_ENDPOINT")
    or not os.getenv("ECD_ALIBABA_CLOUD_ACCESS_KEY_ID")
    or not os.getenv("ECD_ALIBABA_CLOUD_ACCESS_KEY_SECRET")
    or not os.getenv("EDS_OSS_ACCESS_KEY_ID")
    or not os.getenv("EDS_OSS_ACCESS_KEY_SECRET")
    or not os.getenv("EDS_OSS_BUCKET_NAME")
    or not os.getenv("EDS_OSS_ENDPOINT")
    or not os.getenv("EDS_OSS_PATH")
    or not os.getenv("DOCKER_HOST"),
    reason="Cloud Computer dependencies or required environment"
    " variables not available",
)
async def test_cloud_computer_sandbox_via_service(env):  # noqa: ARG001
    """Create CloudComputerSandbox via SandboxService
    and run a tiny smoke test."""
    async with SandboxService() as service:
        sandboxes = service.connect(
            session_id="cloud_computer_demo_session",
            user_id="cloud_computer_demo_user",
            sandbox_types=[SandboxType.CLOUD_COMPUTER.value],
        )
        assert sandboxes and len(sandboxes) > 0
        box = sandboxes[0]

        print("CloudComputer list_tools:", box.list_tools())

        res_cmd = box.call_tool(
            "run_shell_command",
            {"command": "echo 'Cloud Computer Service path OK'"},
        )
        print("CloudComputer run_shell_command:", res_cmd)

        res_screenshot = box.call_tool(
            "screenshot",
            {"file_name": "service_screenshot.png"},
        )
        print("CloudComputer screenshot:", res_screenshot)


@pytest.mark.asyncio
@pytest.mark.skipif(
    not _has_cloud_api_dependencies()
    or not os.getenv("PHONE_INSTANCE_ID")
    or not os.getenv("EDS_ALIBABA_CLOUD_ENDPOINT")
    or not os.getenv("EDS_ALIBABA_CLOUD_ACCESS_KEY_ID")
    or not os.getenv("EDS_ALIBABA_CLOUD_ACCESS_KEY_SECRET")
    or not os.getenv("EDS_OSS_ACCESS_KEY_ID")
    or not os.getenv("EDS_OSS_ACCESS_KEY_SECRET")
    or not os.getenv("EDS_OSS_BUCKET_NAME")
    or not os.getenv("EDS_OSS_ENDPOINT")
    or not os.getenv("EDS_OSS_PATH")
    or not os.getenv("DOCKER_HOST"),
    reason="Cloud Phone dependencies or required environment"
    " variables not available",
)
async def test_cloud_phone_sandbox_via_service(env):  # noqa: ARG001
    """Create CloudPhoneSandbox via SandboxService and
    run a tiny smoke test."""
    async with SandboxService() as service:
        sandboxes = service.connect(
            session_id="cloud_phone_demo_session",
            user_id="cloud_phone_demo_user",
            sandbox_types=[SandboxType.CLOUD_PHONE.value],
        )
        assert sandboxes and len(sandboxes) > 0
        box = sandboxes[0]

        print("CloudPhone list_tools:", box.list_tools())

        res_cmd = box.call_tool(
            "run_shell_command",
            {"command": "echo 'Cloud Phone Service path OK'"},
        )
        print("CloudPhone run_shell_command:", res_cmd)

        res_screenshot = box.call_tool(
            "screenshot",
            {"file_name": "phone_service_screenshot.png"},
        )
        print("CloudPhone screenshot:", res_screenshot)
