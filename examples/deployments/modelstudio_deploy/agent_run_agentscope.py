# -*- coding: utf-8 -*-

import os

from agentscope.model import DashScopeChatModel
from agentscope_runtime.engine.agents.agentscope_agent import AgentScopeAgent


model = DashScopeChatModel(
    model_name="qwen-turbo",
    api_key=os.getenv("DASHSCOPE_API_KEY"),
)

agent = AgentScopeAgent(
    name="agentscope_assistant",
    model=model,
    agent_config={
        "sys_prompt": "You are a helpful assistant.",
    },
)
