# -*- coding: utf-8 -*-
# pylint: disable=redefined-outer-name, unused-argument
import os

import pytest
from dotenv import load_dotenv
from agentscope_runtime.sandbox import BaseSandbox
from agentscope_runtime.sandbox.tools.base import (
    run_ipython_cell,
    run_shell_command,
)


@pytest.fixture
def env():
    if os.path.exists("../../.env"):
        load_dotenv("../../.env")


def test_tool(env):
    # Run in independent sandbox
    print(run_ipython_cell.schema)
    print(run_ipython_cell(code="print('hello world')"))
    print(run_shell_command.schema)
    print(run_shell_command(command="whoami"))

    # Run in one sandbox
    with BaseSandbox() as box:
        func1 = run_ipython_cell.bind(sandbox=box)
        func2 = run_shell_command.bind(sandbox=box)
        print(func1(code="print('hello world')"))
        print(func2(command="whoami"))

    # TODO: add assertion


if __name__ == "__main__":
    if os.path.exists("../../.env"):
        load_dotenv("../../.env")
    test_tool(None)
