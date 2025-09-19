# -*- coding: utf-8 -*-
# pylint:disable=wrong-import-position, wrong-import-order

import os

from agentscope_runtime.engine.agents.llm_agent import LLMAgent
from agentscope_runtime.engine.llms import QwenLLM
from others.other_project import version

model = QwenLLM(
    model_name="qwen-turbo",
    api_key=os.getenv("DASHSCOPE_API_KEY"),
)
llm_agent = LLMAgent(model=model, name="llm_agent")
print(version)
