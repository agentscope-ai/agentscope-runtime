---
jupytext:
  formats: md:myst
  text_representation:
    extension: .md
    format_name: myst
    format_version: 0.13
    jupytext_version: 1.11.5
kernelspec:
  display_name: Python 3
  language: python
  name: python3
---

# CrewAI 集成指南

本文档介绍如何在 AgentScope Runtime 中集成和使用 CrewAI 框架，以构建支持多轮对话、会话记忆和流式响应的协作式自主智能体。

## 📦 示例说明

以下示例演示了如何在 AgentScope Runtime 中使用 CrewAI 框架：

- 使用来自 DashScope 的 Qwen-Plus 模型。
- 通过一个智能体（agent）来组织一个简单的研究任务。
- 支持多轮对话和会话记忆。
- 采用流式输出（SSE）实时返回响应。
- 通过内存会话历史服务（InMemorySessionHistoryService）实现会话历史存储。
- 可以通过兼容 OpenAI 的 API 模式进行访问。

以下是核心代码：

```{code-cell}
# crewai_agent.py
# -*- coding: utf-8 -*-
import os
from agentscope_runtime.engine import AgentApp
from agentscope_runtime.engine.schemas.agent_schemas import AgentRequest
from agentscope_runtime.engine.services.session_history import InMemorySessionHistoryService
from agentscope_runtime.adapters.crewai.memory import create_crewai_session_history_memory

from crewai import Agent, LLM, Crew, Task

PORT = 8090

def run_app():
    """启动 AgentApp 并启用流式输出功能。"""
    agent_app = AgentApp(
        app_name="Friday",
        app_description="A helpful assistant",
    )

    @agent_app.init
    async def init_func(self):
        # 初始化会话历史服务
        self.session_history_service = InMemorySessionHistoryService()


    @agent_app.query(framework="crewai")
    async def query_func(
        self,
        msgs,
        request: AgentRequest = None,
        **kwargs,
    ):
        """使用 CrewAI 处理智能体查询。"""

        # 从输入消息中提取用户问题
        user_question = msgs[0]["content"][0]["text"]

        # 初始化 LLM
        llm = LLM(
            model="qwen-plus",
            api_key=os.environ["DASHSCOPE_API_KEY"],
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            stream=True,
        )

        # 为 crew 创建会话专用的记忆
        memory = await create_crewai_session_history_memory(
            service_or_class=self.session_history_service,
            user_id=request.user_id,
            session_id=request.session_id,
        )

        # 定义研究型 Agent
        research_analyst = Agent(
            role="Expert Research Analyst",
            goal="Analyze the user's question and provide a clear, concise, and accurate answer.",
            backstory=(
                "You are an expert analyst at a world-renowned research institute. "
                "You are known for your ability to break down complex questions and "
                "deliver well-structured, easy-to-understand answers."
            ),
            llm=llm,
        )

        # 定义研究任务
        research_task = Task(
            description=f"Investigate the following user query: '{user_question}'",
            expected_output=(
                "A comprehensive yet easy-to-read answer that directly addresses the user's query. "
                "The answer should be well-formatted and factually correct."
            ),
            agent=research_analyst,
        )

        # 组建 crew
        crew = Crew(
            agents=[research_analyst],
            tasks=[research_task],
            external_memory=memory,
            stream=True,
        )

        # 启动 crew 并流式传输结果
        async for chunk in await crew.akickoff():
            yield chunk


    agent_app.run(host="127.0.0.1", port=PORT)


if __name__ == "__main__":
    run_app()
```

## ⚙️ 先决条件

```{note}
在开始之前，请确保您已经安装了 AgentScope Runtime 与 CrewAI，并配置了必要的 API 密钥。
```

1. **安装依赖**:

   ```bash
   pip install "agentscope-runtime[ext]"
   ```

2. **设置环境变量** （DashScope 提供 Qwen 模型的 API Key）:

   ```bash
   export DASHSCOPE_API_KEY="your-dashscope-api-key"
   ```

## ▶️ 运行示例

运行示例:

```bash
python crewai_agent.py
```

## 🌐 API 交互

### 1. 向智能体提问 (`/process`)

可以使用 HTTP POST 请求与智能体进行交互，并支持 SSE 流式返回：

```bash
curl -N \
  -X POST "http://localhost:8090/process" \
  -H "Content-Type: application/json" \
  -d '{
    "input": [
      {
        "role": "user",
        "content": [
          { "type": "text", "text": "What is the capital of France?" }
        ]
      }
    ],
    "session_id": "session_1"
  }'
```

### 2. OpenAI 兼容模式

该示例同时支持 **OpenAI Compatible API**:

```python
from openai import OpenAI

client = OpenAI(base_url="http://127.0.0.1:8090/compatible-mode/v1")
resp = client.responses.create(
    model="any_model",
    input="What is CrewAI?",
)
print(resp.response["output"][0]["content"][0]["text"])
```

## 🔧 自定义

你可以通过以下方式扩展该示例:

1. **更换模型**: 将 `LLM(model="qwen-plus", ...)` 更换为其他模型。
2. **添加系统提示**:
   - 修改 Agent 的 role、goal 和 backstory 来改变其角色设定和专业领域。
   - 优化 Task 的 description 和 expected_output 以获得更具体的结果。
   - 向 Crew 中添加更多的 Agent 和 Task 实例，以构建更复杂、支持协作和委派的多智能体工作流。
3. **使用不同工具**: 为您的 Agent 分配工具，使其能够与外部服务（如网页搜索、数据库访问等）进行交互。

## 📚 相关文档

- [CrewAI 文档](https://docs.crewai.com/)
- [AgentScope Runtime 文档](https://runtime.agentscope.io/)
