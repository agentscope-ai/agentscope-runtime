# -*- coding: utf-8 -*-
# pylint:disable=redefined-outer-name, unused-argument
import os
import pytest

from agentscope_runtime.sandbox.tools.function_tool import FunctionTool
from agentscope_runtime.engine.agents.autogen_agent import AutogenAgent
from agentscope_runtime.engine.helpers.helper import simple_call_agent_tool
from agentscope_runtime.sandbox.tools.mcp_tool import MCPConfigConverter


@pytest.fixture
def env():
    if os.path.exists("../../.env"):
        from dotenv import load_dotenv

        load_dotenv("../../.env")


class MathCalculator:
    def calculate_power(self, base: int, exponent: int) -> int:
        """Calculate the power of a number."""
        print(f"Calculating {base}^{exponent}...")
        return base**exponent


calculator = MathCalculator()
calculate_power = FunctionTool(calculator.calculate_power)
mcp_tools = MCPConfigConverter(
    server_configs={
        "mcpServers": {
            "time": {
                "command": "uvx",
                "args": [
                    "mcp-server-time",
                    "--local-timezone=America/New_York",
                ],
            },
        },
    },
).to_builtin_tools()


@pytest.mark.asyncio
async def test_autogen_agent_runner(env):
    from autogen_agentchat.agents import AssistantAgent
    from autogen_ext.models.openai import OpenAIChatCompletionClient
    from agentscope_runtime.sandbox.tools.filesystem import (
        run_ipython_cell,
        edit_file,
    )

    agent = AutogenAgent(
        name="Friday",
        model=OpenAIChatCompletionClient(
            model="qwen-max",
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            model_info={
                "vision": False,
                "function_calling": True,
                "json_output": False,
                "family": "unknown",
                "structured_output": False,
            },
            api_key=os.getenv("DASHSCOPE_API_KEY"),
        ),
        agent_config={
            "system_message": "You're a helpful assistant",
        },
        tools=[
            run_ipython_cell,
            edit_file,
            calculate_power,
        ]
        + mcp_tools,
        agent_builder=AssistantAgent,
    )

    gt_list = [
        "32768",
        "32,768",
    ]
    query = "Calculate 8^5 with tools."

    all_result = await simple_call_agent_tool(agent, query)

    assert gt_list[0] in all_result or gt_list[1] in all_result

    gt_list = [
        "New York",
        "New_York",
    ]
    query = "What time is it now in America/New_York?"
    all_result = await simple_call_agent_tool(agent, query)
    assert gt_list[0] in all_result or gt_list[1] in all_result
