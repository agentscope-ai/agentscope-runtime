# -*- coding: utf-8 -*-
# pylint: disable=redefined-outer-name, unused-argument, too-many-branches, too-many-statements, consider-using-with, subprocess-popen-preexec-fn # noqa: E501
import os
import pytest

from dotenv import load_dotenv

from agentscope_runtime.engine.services.sandbox import SandboxService


@pytest.fixture
def env():
    if os.path.exists("../../.env"):
        load_dotenv("../../.env")


@pytest.mark.asyncio
async def test_sandbox_service(env):
    sandbox_service = SandboxService()
    await sandbox_service.start()

    session_id = "session_123"
    user_id = "user_12345"

    sandboxes = sandbox_service.connect(
        session_id=session_id,
        user_id=user_id,
        sandbox_types=["base"],
    )

    base_sandbox = sandboxes[0]

    result = base_sandbox.run_ipython_cell("print('Hello, World!')")
    base_sandbox.run_ipython_cell("a=1")

    assert (
        len(result["content"]) > 0
        and result["content"][0]["text"] == "Hello, World!\n"
        and result["isError"] is False
    ), f"Unexpected result: {result}"

    new_sandboxes = sandbox_service.connect(
        session_id=session_id,
        user_id=user_id,
        sandbox_types=["base"],
    )

    new_base_sandbox = new_sandboxes[0]

    result = new_base_sandbox.run_ipython_cell("print(a)")

    assert (
        len(result["content"]) > 0
        and result["content"][0]["text"] == "1\n"
        and result["isError"] is False
    ), f"Unexpected result: {result}"

    await sandbox_service.stop()


if __name__ == "__main__":
    import asyncio

    if os.path.exists("../../.env"):
        load_dotenv("../../.env")
    asyncio.run(test_sandbox_service(None))
