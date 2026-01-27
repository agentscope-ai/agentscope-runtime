# -*- coding: utf-8 -*-
# pylint: disable=redefined-outer-name, unused-argument, too-many-branches, too-many-statements, consider-using-with, subprocess-popen-preexec-fn # noqa: E501
import os
import signal
import subprocess
import time

import pytest
import requests
from dotenv import load_dotenv

from agentscope_runtime.sandbox import (
    BaseSandbox,
    BrowserSandbox,
    FilesystemSandbox,
    GuiSandbox,
    MobileSandbox,
    BaseSandboxAsync,
)


@pytest.fixture
def env():
    if os.path.exists("../../.env"):
        load_dotenv("../../.env")


def test_local_sandbox(env):
    with BaseSandbox() as box:
        print(box.list_tools())
        print(
            box.call_tool(
                "run_ipython_cell",
                arguments={
                    "code": "print('hello world')",
                },
            ),
        )

        print(box.run_ipython_cell(code="print('hi')"))
        print(box.run_shell_command(command="echo hello"))

    with BrowserSandbox() as box:
        print(box.list_tools())

        print(box.browser_navigate("https://www.example.com/"))
        print(box.browser_snapshot())

    with FilesystemSandbox() as box:
        print(box.list_tools())
        print(box.create_directory("test"))
        print(box.list_allowed_directories())

    with GuiSandbox() as box:
        print(box.list_tools())
        print(box.computer_use(action="get_cursor_position"))

    with MobileSandbox() as box:
        print(box.list_tools())
        print(box.mobile_get_screen_resolution())
        print(box.mobile_tap([360, 150]))


@pytest.mark.asyncio
async def test_local_sandbox_async(env):
    async with BaseSandboxAsync() as box:
        print(await box.list_tools_async())
        print(
            await box.call_tool_async(
                "run_ipython_cell",
                arguments={"code": "print('hello async world')"},
            ),
        )
        print(await box.run_ipython_cell(code="print('hi async')"))
        print(await box.run_shell_command(command="echo hello async"))


@pytest.mark.asyncio
async def test_remote_sandbox(env):
    server_process = None
    try:
        print("Starting server process...")
        server_process = subprocess.Popen(
            ["runtime-sandbox-server"],
            stdout=None,
            stderr=None,
            preexec_fn=os.setsid if os.name != "nt" else None,
        )
        max_retries = 10
        retry_count = 0
        server_ready = False
        print("Waiting for server to start...")
        while retry_count < max_retries:
            try:
                response = requests.get(
                    "http://localhost:8000/health",
                    timeout=1,
                )
                if response.status_code == 200:
                    server_ready = True
                    print("Server is ready!")
                    break
            except requests.exceptions.RequestException:
                pass
            time.sleep(1)
            retry_count += 1
            print(f"Retry {retry_count}/{max_retries}...")

        if not server_ready:
            raise RuntimeError("Server failed to start within timeout period")

        with BaseSandbox(base_url="http://localhost:8000") as box:
            print(box.list_tools())
            print(
                box.call_tool(
                    "run_ipython_cell",
                    arguments={
                        "code": "print('hello world')",
                    },
                ),
            )

            print(box.run_ipython_cell(code="print('hi')"))
            print(box.run_shell_command(command="echo hello"))

        async with BaseSandboxAsync(base_url="http://localhost:8000") as box:
            print(await box.list_tools_async())
            print(
                await box.call_tool_async(
                    "run_ipython_cell",
                    arguments={
                        "code": "print('hello world')",
                    },
                ),
            )

            print(await box.run_ipython_cell(code="print('hi')"))
            print(await box.run_shell_command(command="echo hello"))

        with BrowserSandbox(base_url="http://localhost:8000") as box:
            print(box.list_tools())

            print(box.browser_navigate("https://www.example.com/"))
            print(box.browser_snapshot())

        with FilesystemSandbox(base_url="http://localhost:8000") as box:
            print(box.list_tools())
            print(box.create_directory("test"))
            print(box.list_allowed_directories())

        with GuiSandbox(base_url="http://localhost:8000") as box:
            print(box.list_tools())
            print(box.computer_use(action="get_cursor_position"))

        with MobileSandbox(base_url="http://localhost:8000") as box:
            print(box.list_tools())
            print(box.mobile_get_screen_resolution())
            print(box.mobile_tap([360, 150]))

    except Exception as e:
        print(f"Error occurred: {e}")
        raise

    finally:
        if server_process:
            print("Cleaning up server process...")
            try:
                if os.name == "nt":  # Windows
                    server_process.terminate()
                else:  # Unix/Linux
                    os.killpg(os.getpgid(server_process.pid), signal.SIGTERM)

                try:
                    server_process.wait(timeout=5)
                    print("Server process terminated gracefully")
                except subprocess.TimeoutExpired:
                    print("Force killing server process...")
                    if os.name == "nt":
                        server_process.kill()
                    else:
                        os.killpg(
                            os.getpgid(server_process.pid),
                            signal.SIGKILL,
                        )
                    server_process.wait()
            except Exception as cleanup_error:
                print(f"Error during cleanup: {cleanup_error}")


@pytest.mark.asyncio
async def test_local_sandbox_fs_async(env):
    async with BaseSandboxAsync() as box:
        # create dir + write + read(text)
        ok = await box.fs.mkdir_async("dir_async")
        assert isinstance(ok, bool)

        r1 = await box.fs.write_async("dir_async/a.txt", "hello async")
        assert isinstance(r1, dict)

        txt = await box.fs.read_async("dir_async/a.txt", fmt="text")
        assert txt == "hello async"

        # exists + list
        assert await box.fs.exists_async("dir_async/a.txt") is True
        items = await box.fs.list_async("dir_async", depth=2)
        assert isinstance(items, list)

        # streaming download
        stream = await box.fs.read_async("dir_async/a.txt", fmt="stream")
        assert hasattr(stream, "__aiter__")
        buf = b""
        async for chunk in stream:
            buf += chunk
        assert buf == b"hello async"

        # move + remove
        mv = await box.fs.move_async("dir_async/a.txt", "dir_async/b.txt")
        assert isinstance(mv, dict)
        assert await box.fs.exists_async("dir_async/b.txt") is True

        await box.fs.remove_async("dir_async/b.txt")
        assert await box.fs.exists_async("dir_async/b.txt") is False


def test_local_sandbox_fs(env, tmp_path):
    with BaseSandbox() as box:
        # create dir + write + read(text)
        ok = box.fs.mkdir("dir")
        assert isinstance(ok, bool)

        r1 = box.fs.write("dir/a.txt", "hello")
        assert isinstance(r1, dict)

        txt = box.fs.read("dir/a.txt", fmt="text")
        assert txt == "hello"

        # exists + list
        assert box.fs.exists("dir/a.txt") is True
        items = box.fs.list("dir", depth=2)
        assert isinstance(items, list)

        # streaming download
        out = b""
        for chunk in box.fs.read("dir/a.txt", fmt="stream"):
            out += chunk
        assert out == b"hello"

        # write_from_path (stream upload)
        local_file = tmp_path / "local.txt"
        local_file.write_text("from local", encoding="utf-8")

        r2 = box.fs.write_from_path("dir/from_local.txt", str(local_file))
        assert isinstance(r2, dict)
        assert box.fs.read("dir/from_local.txt", fmt="text") == "from local"

        # move + remove
        mv = box.fs.move("dir/a.txt", "dir/b.txt")
        assert isinstance(mv, dict)
        assert box.fs.exists("dir/b.txt") is True

        box.fs.remove("dir/b.txt")
        assert box.fs.exists("dir/b.txt") is False


if __name__ == "__main__":
    if os.path.exists("../../.env"):
        load_dotenv("../../.env")
    test_remote_sandbox(None)
