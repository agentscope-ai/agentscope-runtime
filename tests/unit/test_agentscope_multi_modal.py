# -*- coding: utf-8 -*-
# pylint:disable=redefined-outer-name, unused-argument
import os

import pytest

from agentscope_runtime.engine.schemas.agent_schemas import AgentRequest
from agentscope_runtime.engine.agents.agentscope_agent import AgentScopeAgent
from agentscope_runtime.engine.helpers.helper import (
    simple_call_agent_tool_wo_env,
)


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
            "qwen-vl-plus",
            api_key=os.getenv("DASHSCOPE_API_KEY"),
        ),
        agent_config={
            "sys_prompt": "You're a helpful assistant named Friday.",
        },
        agent_builder=ReActAgent,
    )

    image_url = (
        "https://agentscope.oss-cn-zhangjiakou.aliyuncs.com/unittest_cat.png"
    )

    request = AgentRequest(
        input=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "What is in the image?",
                    },
                    {
                        "type": "image",
                        "image_url": image_url,
                    },
                ],
            },
        ],
    )

    all_result = await simple_call_agent_tool_wo_env(agent, request)

    assert "cat" in all_result
