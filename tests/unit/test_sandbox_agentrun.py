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
    FilesystemSandbox,
    BrowserSandbox,
    BaseSandbox,
)


@pytest.fixture
def env():
    if os.path.exists("../../.agentrun_env"):
        load_dotenv("../../.agentrun_env")


def test_agentrun_remote_sandbox():
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

        with BrowserSandbox(base_url="http://localhost:8000") as box:
            print(box.list_tools())

            print(box.browser_navigate("https://www.example.com/"))
            print(box.browser_snapshot())

        with FilesystemSandbox(base_url="http://localhost:8000") as box:
            print(box.list_tools())
            print(box.create_directory("test"))
            print(box.list_allowed_directories())

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


if __name__ == "__main__":
    if os.path.exists("../../agentrun.env"):
        load_dotenv("../../agentrun.env")
    test_agentrun_remote_sandbox()
