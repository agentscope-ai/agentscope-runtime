# -*- coding: utf-8 -*-
# pylint:disable=redefined-outer-name, unused-argument
import os

import pytest

from agentscope_runtime.sandbox.tools.function_tool import function_tool
from agentscope_runtime.engine.agents.agentscope_agent import AgentScopeAgent
from agentscope_runtime.engine.helpers.helper import (
    simple_call_agent_tool_wo_env,
)


@pytest.fixture
def env():
    if os.path.exists("../../.env"):
        from dotenv import load_dotenv

        load_dotenv("../../.env")


@function_tool()
def calculate_power(base: int, exponent: int) -> int:
    """Calculate the base raised to the power of the exponent."""
    print(f"Calculating {base}^{exponent}...")
    return base**exponent


@pytest.mark.asyncio
async def test_react_agent_runner(env):
    from agentscope.agent import ReActAgent
    from agentscope.model import DashScopeChatModel
    from agentscope.tool import Toolkit, view_text_file

    toolkit = Toolkit()
    # Register an unrelated tool
    toolkit.register_tool_function(view_text_file)

    agent = AgentScopeAgent(
        name="Friday",
        model=DashScopeChatModel(
            "qwen-max",
            api_key=os.getenv("DASHSCOPE_API_KEY"),
        ),
        agent_config={
            "sys_prompt": "You're a helpful assistant named Friday.",
            "toolkit": toolkit,
        },
        tools=[
            calculate_power,
        ],
        agent_builder=ReActAgent,
    )

    gt_list = [
        "32768",
        "32,768",
    ]
    query = "Calculate 8^5 with tools."

    all_result = await simple_call_agent_tool_wo_env(agent, query)

    assert gt_list[0] in all_result or gt_list[1] in all_result


@pytest.mark.asyncio
async def test_react_agent_runner_reasoning(env):
    from agentscope.agent import ReActAgent
    from agentscope.model import DashScopeChatModel
    from agentscope.tool import Toolkit, view_text_file

    toolkit = Toolkit()
    # Register an unrelated tool
    toolkit.register_tool_function(view_text_file)

    agent = AgentScopeAgent(
        name="Friday",
        model=DashScopeChatModel(
            "qwen-plus",
            api_key=os.getenv("DASHSCOPE_API_KEY"),
            enable_thinking=True,
        ),
        agent_config={
            "sys_prompt": "You're a helpful assistant named Friday.",
            "toolkit": toolkit,
        },
        tools=[
            calculate_power,
        ],
        agent_builder=ReActAgent,
    )

    gt_list = [
        "32768",
        "32,768",
    ]
    query = "Calculate 8^5 with tools."

    all_result = await simple_call_agent_tool_wo_env(agent, query)

    assert gt_list[0] in all_result or gt_list[1] in all_result
