# -*- coding: utf-8 -*-
# pylint: disable=redefined-outer-name, unused-argument, too-many-branches, too-many-statements, consider-using-with, subprocess-popen-preexec-fn # noqa: E501
import os
import tempfile
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
async def test_local_sandbox_fs_async(env, tmp_path):
    """
    Full coverage test for SandboxFSAsync facade:
      - mkdir_async
      - write_async (str / bytes / file-like stream)
      - read_async (text / bytes / stream)
      - exists_async
      - list_async
      - move_async
      - remove_async
      - write_many_async
      - write_from_path_async
    """
    async with BaseSandboxAsync() as box:
        base_dir = "dir_async"

        # ---- mkdir ----
        ok = await box.fs.mkdir_async(base_dir)
        assert isinstance(ok, bool)

        # ---- write str + read text ----
        r1 = await box.fs.write_async(f"{base_dir}/a.txt", "hello async")
        assert isinstance(r1, dict)

        txt = await box.fs.read_async(f"{base_dir}/a.txt", fmt="text")
        assert txt == "hello async"

        # ---- exists ----
        assert await box.fs.exists_async(f"{base_dir}/a.txt") is True
        assert await box.fs.exists_async(f"{base_dir}/not-exist.txt") is False

        # ---- list ----
        items = await box.fs.list_async(base_dir, depth=10)
        assert isinstance(items, list)

        # ---- write bytes + read bytes ----
        payload_b = b"\x00\x01hello-bytes\xff"
        r2 = await box.fs.write_async(
            f"{base_dir}/b.bin",
            payload_b,
            content_type="application/octet-stream",
        )
        assert isinstance(r2, dict)

        got_b = await box.fs.read_async(f"{base_dir}/b.bin", fmt="bytes")
        assert isinstance(got_b, (bytes, bytearray))
        assert bytes(got_b) == payload_b

        # ---- stream write (file-like) + read bytes + read stream ----
        stream_payload = b"stream-upload-content-" * 1024  # ~22KB
        with tempfile.NamedTemporaryFile("wb", delete=False) as tf:
            tmp_file_path = tf.name
            tf.write(stream_payload)

        try:
            with open(tmp_file_path, "rb") as f:
                r3 = await box.fs.write_async(
                    f"{base_dir}/c.bin",
                    f,  # file-like streaming upload
                    content_type="application/octet-stream",
                )
            assert isinstance(r3, dict)

            got_stream_b = await box.fs.read_async(
                f"{base_dir}/c.bin",
                fmt="bytes",
            )
            assert bytes(got_stream_b) == stream_payload

            stream = await box.fs.read_async(f"{base_dir}/c.bin", fmt="stream")
            buf = b""
            async for chunk in stream:
                buf += chunk
            assert buf == stream_payload
        finally:
            try:
                os.remove(tmp_path)
            except Exception:
                pass

        # ---- move ----
        mv = await box.fs.move_async(
            f"{base_dir}/a.txt",
            f"{base_dir}/a_moved.txt",
        )
        assert isinstance(mv, dict)
        assert await box.fs.exists_async(f"{base_dir}/a.txt") is False
        assert await box.fs.exists_async(f"{base_dir}/a_moved.txt") is True

        # ---- write_many ----
        # include str + bytes (keep it small and deterministic)
        batch_payload = b"batch-bytes-123"
        batch = [
            {"path": f"{base_dir}/batch1.txt", "data": "batch hello"},
            {
                "path": f"{base_dir}/batch2.bin",
                "data": batch_payload,
                "content_type": "application/octet-stream",
            },
        ]
        res_batch = await box.fs.write_many_async(batch)
        assert isinstance(res_batch, list)
        assert len(res_batch) == 2, (
            f"write_many_async should return 2 entries, got {len(res_batch)}: "
            f"{res_batch}"
        )

        assert await box.fs.exists_async(f"{base_dir}/batch1.txt") is True
        assert (
            await box.fs.read_async(
                f"{base_dir}/batch1.txt",
                fmt="text",
            )
            == "batch hello"
        )
        assert (
            bytes(
                await box.fs.read_async(
                    f"{base_dir}/batch2.bin",
                    fmt="bytes",
                ),
            )
            == batch_payload
        )

        # ---- write_from_path ----
        with tempfile.NamedTemporaryFile("wb", delete=False) as tf2:
            tmp2 = tf2.name
            tf2.write(b"from-local-file-async")

        try:
            r4 = await box.fs.write_from_path_async(
                f"{base_dir}/from_path.txt",
                tmp2,
                content_type="text/plain; charset=utf-8",
            )
            assert isinstance(r4, dict)

            assert (
                await box.fs.read_async(
                    f"{base_dir}/from_path.txt",
                    fmt="text",
                )
                == "from-local-file-async"
            )
        finally:
            try:
                os.remove(tmp2)
            except Exception:
                pass

        # ---- remove (file) ----
        await box.fs.remove_async(f"{base_dir}/a_moved.txt")
        assert await box.fs.exists_async(f"{base_dir}/a_moved.txt") is False

        # ---- remove (directory) ----
        for p in [
            f"{base_dir}/b.bin",
            f"{base_dir}/c.bin",
            f"{base_dir}/batch1.txt",
            f"{base_dir}/batch2.bin",
            f"{base_dir}/from_path.txt",
        ]:
            if await box.fs.exists_async(p):
                await box.fs.remove_async(p)

        try:
            await box.fs.remove_async(base_dir)
        except Exception:
            pass


def test_local_sandbox_fs(env, tmp_path):
    """
    Full coverage test for SandboxFS facade (sync):
      - mkdir
      - write (str / bytes / file-like stream)
      - read (text / bytes / stream)
      - exists
      - list
      - move
      - remove
      - write_many
      - write_from_path
    """
    with BaseSandbox() as box:
        base_dir = "dir_sync"

        # ---- mkdir ----
        ok = box.fs.mkdir(base_dir)
        assert isinstance(ok, bool)

        # ---- write str + read text ----
        r1 = box.fs.write(f"{base_dir}/a.txt", "hello sync")
        assert isinstance(r1, dict)

        txt = box.fs.read(f"{base_dir}/a.txt", fmt="text")
        assert txt == "hello sync"

        # ---- exists ----
        assert box.fs.exists(f"{base_dir}/a.txt") is True
        assert box.fs.exists(f"{base_dir}/not-exist.txt") is False

        # ---- list ----
        items = box.fs.list(base_dir, depth=10)
        assert isinstance(items, list)

        # ---- write bytes + read bytes ----
        payload_b = b"\x00\x01hello-bytes\xff"
        r2 = box.fs.write(
            f"{base_dir}/b.bin",
            payload_b,
            content_type="application/octet-stream",
        )
        assert isinstance(r2, dict)

        got_b = box.fs.read(f"{base_dir}/b.bin", fmt="bytes")
        assert isinstance(got_b, (bytes, bytearray))
        assert bytes(got_b) == payload_b

        # ---- stream write (file-like) + read bytes + read stream ----
        stream_payload = b"stream-upload-content-" * 1024  # ~22KB
        with tempfile.NamedTemporaryFile("wb", delete=False) as tf:
            tmp_file_path = tf.name
            tf.write(stream_payload)

        try:
            with open(tmp_file_path, "rb") as f:
                r3 = box.fs.write(
                    f"{base_dir}/c.bin",
                    f,  # file-like streaming upload
                    content_type="application/octet-stream",
                )
            assert isinstance(r3, dict)

            got_stream_b = box.fs.read(f"{base_dir}/c.bin", fmt="bytes")
            assert bytes(got_stream_b) == stream_payload

            buf = b""
            for chunk in box.fs.read(f"{base_dir}/c.bin", fmt="stream"):
                buf += chunk
            assert buf == stream_payload
        finally:
            try:
                os.remove(tmp_file_path)
            except Exception:
                pass

        # ---- move ----
        mv = box.fs.move(
            f"{base_dir}/a.txt",
            f"{base_dir}/a_moved.txt",
        )
        assert isinstance(mv, dict)
        assert box.fs.exists(f"{base_dir}/a.txt") is False
        assert box.fs.exists(f"{base_dir}/a_moved.txt") is True

        # ---- write_many ----
        batch_payload = b"batch-bytes-123"
        batch = [
            {"path": f"{base_dir}/batch1.txt", "data": "batch hello"},
            {
                "path": f"{base_dir}/batch2.bin",
                "data": batch_payload,
                "content_type": "application/octet-stream",
            },
        ]
        res_batch = box.fs.write_many(batch)
        assert isinstance(res_batch, list)
        assert len(res_batch) == 2, (
            f"write_many should return 2 entries, got {len(res_batch)}: "
            f"{res_batch}"
        )

        assert box.fs.exists(f"{base_dir}/batch1.txt") is True
        assert (
            box.fs.read(
                f"{base_dir}/batch1.txt",
                fmt="text",
            )
            == "batch hello"
        )
        assert (
            bytes(
                box.fs.read(
                    f"{base_dir}/batch2.bin",
                    fmt="bytes",
                ),
            )
            == batch_payload
        )

        # ---- write_from_path ----
        with tempfile.NamedTemporaryFile("wb", delete=False) as tf2:
            tmp2 = tf2.name
            tf2.write(b"from-local-file-sync")

        try:
            r4 = box.fs.write_from_path(
                f"{base_dir}/from_path.txt",
                tmp2,
                content_type="text/plain; charset=utf-8",
            )
            assert isinstance(r4, dict)

            assert (
                box.fs.read(
                    f"{base_dir}/from_path.txt",
                    fmt="text",
                )
                == "from-local-file-sync"
            )
        finally:
            try:
                os.remove(tmp2)
            except Exception:
                pass

        # ---- remove (file) ----
        box.fs.remove(f"{base_dir}/a_moved.txt")
        assert box.fs.exists(f"{base_dir}/a_moved.txt") is False

        # ---- remove (directory) ----
        for p in [
            f"{base_dir}/b.bin",
            f"{base_dir}/c.bin",
            f"{base_dir}/batch1.txt",
            f"{base_dir}/batch2.bin",
            f"{base_dir}/from_path.txt",
        ]:
            if box.fs.exists(p):
                box.fs.remove(p)

        # directory delete policy may vary
        try:
            box.fs.remove(base_dir)
        except Exception:
            pass


if __name__ == "__main__":
    if os.path.exists("../../.env"):
        load_dotenv("../../.env")
    test_remote_sandbox(None)
