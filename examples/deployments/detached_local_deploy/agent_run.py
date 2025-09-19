# -*- coding: utf-8 -*-
"""Agent definition for detached local deployment example."""

import os
from agentscope_runtime.engine.agents.llm_agent import LLMAgent
from agentscope_runtime.engine.llms import QwenLLM

# Create the agent with QwenLLM
model = QwenLLM(
    model_name="qwen-turbo",
    api_key=os.getenv("DASHSCOPE_API_KEY"),
)

llm_agent = LLMAgent(
    model=model,
    name="DetachedAgent",
    agent_config={
        "sys_prompt": (
            "You are a helpful assistant running in detached mode. "
            "You can help users with various tasks and questions."
        ),
    },
)
