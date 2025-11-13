# -*- coding: utf-8 -*-
# pylint:disable=redefined-outer-name, unused-argument
import os

import pytest

from agentscope_runtime.engine.agents.agentscope_agent import AgentScopeAgent
from agentscope_runtime.engine.helpers.helper import simple_call_agent_tool
from agentscope_runtime.sandbox.tools.browser import (
    browser_navigate,
    browser_take_screenshot,
    browser_snapshot,
    browser_click,
    browser_type,
)

BROWSER_TOOLS = [
    browser_navigate,
    browser_take_screenshot,
    browser_snapshot,
    browser_click,
    browser_type,
]


SYSTEM_PROMPT = """You are Web Using AI assistant named Friday.

# Objective
Your goal is to complete given tasks by controlling a browser to navigate web pages.

## Web Browsing Guidelines
- Use `browser_navigate` command to jump to specific webpages when needed.
- Use `generate_response` to answer user once you got all information required.
- Always answer in English.

### Observing Guidelines
- Always take action based on the elements on the webpage. Never create urls or generate new pages.
- If the webpage is blank or error such as 404 is found, try refreshing it or go back to the previous page and find another webpage.
"""  # noqa: E501


@pytest.fixture
def env():
    if os.path.exists("../../.env"):
        from dotenv import load_dotenv

        load_dotenv("../../.env")


@pytest.mark.asyncio
async def test_react_agent_runner(env):
    from agentscope.agent import ReActAgent
    from agentscope.model import DashScopeChatModel

    agent = AgentScopeAgent(
        name="Friday",
        model=DashScopeChatModel(
            "qwen-max",
            api_key=os.getenv("DASHSCOPE_API_KEY"),
        ),
        agent_config={
            "sys_prompt": SYSTEM_PROMPT,
        },
        tools=BROWSER_TOOLS,
        agent_builder=ReActAgent,
    )

    query = "What is in example.com?"
    gt_list = ["Example Domain"]
    all_result = await simple_call_agent_tool(agent, query)

    assert gt_list[0] in all_result
