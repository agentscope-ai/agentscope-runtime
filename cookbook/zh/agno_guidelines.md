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

# Agno 集成指南

本指南介绍了如何在 **AgentScope Runtime** 中集成和使用 **Agno** 来构建具备多轮对话和流式响应能力的智能体。

## 📦 示例说明

下面的示例演示了如何在 AgentScope Runtime 中使用 [Agno](https://docs.agno.com/)：

- 使用来自 DashScope 的 Qwen-Plus 模型
- 支持多轮对话与会话记忆
- 采用 **流式输出**（SSE）实时返回响应
- 实现基于内存数据库（`InMemoryDb`）的会话历史存储
- 可以通过 OpenAI Compatible 模式访问

以下是核心代码：

```{code-cell}
# agno_agent.py
# -*- coding: utf-8 -*-
import os
from agno.agent import Agent
from agno.models.dashscope import DashScope
from agno.db.in_memory import InMemoryDb
from agentscope_runtime.engine import AgentApp
from agentscope_runtime.engine.schemas.agent_schemas import AgentRequest

PORT = 8090

def run_app():
    """启动 AgentApp 并启用流式输出功能"""
    agent_app = AgentApp(
        app_name="Friday",
        app_description="A helpful assistant",
    )

    @agent_app.init
    async def init_func(self):
        # Agno 内存数据库，详情见 https://docs.agno.com/reference/storage
        self.db = InMemoryDb()

    @agent_app.query(framework="agno")
    async def query_func(
        self,
        msgs,
        request: AgentRequest = None,
        **kwargs,
    ):
        session_id = request.session_id

        agent = Agent(
            name="Friday",
            instructions="You're a helpful assistant named Friday",
            model=DashScope(
                id="qwen-plus",
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                api_key=os.getenv("DASHSCOPE_API_KEY"),
            ),
            db=self.db,
            session_id=session_id,
            add_history_to_context=True,
        )

        # 流式返回响应
        async for event in agent.arun(
            msgs,
            stream=True,
            stream_events=True,
        ):
            yield event

    agent_app.run(host="127.0.0.1", port=PORT)

if __name__ == "__main__":
    run_app()
```

## ⚙️ 先决条件

```{note}
在开始之前，请确保您已经安装了 AgentScope Runtime 与 Agno，并配置了必要的 API 密钥。
```

1. **安装依赖**：

   ```bash
   pip install "agentscope-runtime[ext]"
   ```

2. **设置环境变量**（DashScope 提供 Qwen 模型的 API Key）：

   ```bash
   export DASHSCOPE_API_KEY="your-dashscope-api-key"
   ```

## ▶️ 运行示例

运行示例：

```
python agno_agent.py
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

该示例同时支持 **OpenAI Compatible API**：

```python
from openai import OpenAI

client = OpenAI(base_url="http://127.0.0.1:8090/compatible-mode/v1")
resp = client.responses.create(
    model="any_model",
    input="Who are you?",
)
print(resp.response["output"][0]["content"][0]["text"])
```

## 🔧 自定义

你可以通过以下方式扩展该示例：

1. **更换模型**：在 `DashScope(id="qwen-plus", ...)` 中更换成其他模型
2. **增加系统提示**：修改 `instructions` 字段实现不同角色人设
3. **更换数据库后端**：将 `InMemoryDb` 替换成其他存储

## 📚 相关文档

* [Agno 文档](https://docs.agno.com/reference)

- [AgentScope Runtime 文档](https://runtime.agentscope.io/)