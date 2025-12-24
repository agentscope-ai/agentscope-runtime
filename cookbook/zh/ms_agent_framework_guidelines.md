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

# Microsoft Agent Framework 集成指南

本文档介绍了如何在 **AgentScope Runtime** 中集成和使用 **Microsoft Agent Framework**来构建支持多轮会话、会话记忆及流式响应的智能体。

## 📦 示例说明

下面的示例演示了如何在 AgentScope Runtime 中使用 [Microsoft Agent Framework](https://learn.microsoft.com/en-us/agent-framework/)：

- 使用来自 DashScope 的 Qwen-Plus 模型
- 支持多轮对话与会话记忆
- 采用 **流式输出**（SSE）实时返回响应
- 实现基于内存数据库（`InMemoryDb`）的会话历史存储
- 可以通过 OpenAI Compatible 模式访问

以下是核心代码：

```{code-cell}
# ms_agent.py
# -*- coding: utf-8 -*-
import os
from agent_framework.openai import OpenAIChatClient

from agentscope_runtime.engine import AgentApp
from agentscope_runtime.engine.schemas.agent_schemas import AgentRequest
from agentscope_runtime.engine.services.agent_state import InMemoryStateService

PORT = 8090


def run_app():
    """启动 AgentApp 并启用流式输出功能"""
    agent_app = AgentApp(
        app_name="Friday",
        app_description="A helpful assistant",
    )

    @agent_app.init
    async def init_func(self):
        self.state_service = InMemoryStateService()
        await self.state_service.start()

    @agent_app.shutdown
    async def shutdown_func(self):
        await self.state_service.stop()

    @agent_app.query(framework="agno")
    async def query_func(
        self,
        msgs,
        request: AgentRequest = None,
        **kwargs,
    ):
        """处理智能体查询"""
        session_id = request.session_id
        user_id = request.user_id

        # 导出历史上下文
        thread = await self.state_service.export_state(
            session_id=session_id,
            user_id=user_id,
        )

        # 创建 agent
        agent = OpenAIChatClient(
            model_id="qwen-plus",
            api_key=os.environ["DASHSCOPE_API_KEY"],
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        ).create_agent(
            instructions="You're a helpful assistant named Friday",
            name="Friday",
        )

        # 恢复或新建对话线程
        if thread:
            thread = await agent.deserialize_thread(thread)
        else:
            thread = agent.get_new_thread()

        # 流式响应
        async for event in agent.run_stream(
            msgs,
            thread=thread,
        ):
            yield event

        # 保存会话状态
        serialized_thread = await thread.serialize()
        await self.state_service.save_state(
            user_id=user_id,
            session_id=session_id,
            state=serialized_thread,
        )

    agent_app.run(host="127.0.0.1", port=PORT)


if __name__ == "__main__":
    run_app()
```

## ⚙️ 先决条件

```{note}
在开始之前，请确保您已经安装了 AgentScope Runtime 与 Microsoft Agent Framework，并配置了必要的 API 密钥。
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
python ms_agent.py
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

1. **更换模型**：将 `OpenAIChatClient` 中的 `model_id` 替换为其他模型，或者使用其他模型提供商的Client
2. **增加系统提示**：修改 `instructions` 字段实现不同角色人设

## 📚 相关文档

* [Microsoft Agent Framework 文档](https://learn.microsoft.com/en-us/agent-framework/overview/agent-framework-overview)

- [AgentScope Runtime 文档](https://runtime.agentscope.io/)