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

# LangGraph 集成指南

本指南介绍了如何在 AgentScope Runtime 中集成和使用 LangGraph 来构建复杂的智能体工作流。
推荐使用 python 3.11 或更高版本以支持流模式，详情请参考 [LangGraph](https://docs.langchain.com/oss/python/langgraph/streaming#llm-tokens)。

## 📦 示例说明

### 1. 基础 LLM 交互

一个简单的示例，演示在 AgentScope Runtime 中使用 LangGraph 进行基础的 LLM 交互：

- 使用来自 DashScope 的 Qwen-Plus 模型
- 实现了一个包含单个节点的基础状态图工作流
- 展示了如何从 LLM 流式传输响应
- 包含对话历史的记忆管理
- 演示了使用 `StateGraph` 与 `START` 和 `call_model` 节点

以下是核心代码：

```{code-cell}
# -*- coding: utf-8 -*-

import os
import uuid

from langchain.agents import AgentState, create_agent
from langchain.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.base import BaseStore
from langgraph.store.memory import InMemoryStore

from agentscope_runtime.engine import AgentApp
from agentscope_runtime.engine.schemas.agent_schemas import AgentRequest

global_short_term_memory: BaseCheckpointSaver = None
global_long_term_memory: BaseStore = None


@tool
def get_weather(location: str, date: str) -> str:
    """Get the weather for a location and date."""
    print(f"Getting weather for {location} on {date}...")
    return f"The weather in {location} is sunny with a temperature of 25°C."


# Create the AgentApp instance
agent_app = AgentApp(
    app_name="LangGraphAgent",
    app_description="A LangGraph-based research assistant",
)


class CustomAgentState(AgentState):
    user_id: str
    session_id: dict


# Initialize services as instance variables
@agent_app.init
async def init_func(self):
    global global_short_term_memory
    global global_long_term_memory
    self.short_term_mem = InMemorySaver()
    self.long_term_mem = InMemoryStore()
    global_short_term_memory = self.short_term_mem
    global_long_term_memory = self.long_term_mem


# Shutdown services, in this case,
# we don't use any resources, so we don't need to do anything here
@agent_app.shutdown
async def shutdown_func(self):
    pass


@agent_app.query(framework="langgraph")
async def query_func(
    self,
    msgs,
    request: AgentRequest = None,
    **kwargs,
):
    # Extract session information
    session_id = request.session_id
    user_id = request.user_id
    print(f"Received query from user {user_id} with session {session_id}")
    tools = [get_weather]
    # Choose the LLM that will drive the agent
    llm = ChatOpenAI(
        model="qwen-plus",
        api_key=os.environ.get("DASHSCOPE_API_KEY"),
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    )
    namespace_for_long_term_memory = (user_id, "memories")

    prompt = """You are a proactive research assistant. """

    agent = create_agent(
        llm,
        tools,
        system_prompt=prompt,
        checkpointer=self.short_term_mem,
        store=self.long_term_mem,
        state_schema=CustomAgentState,
        name="LangGraphAgent",
    )
    async for chunk, meta_data in agent.astream(
        input={"messages": msgs, "session_id": session_id, "user_id": user_id},
        stream_mode="messages",
        config={"configurable": {"thread_id": session_id}},
    ):
        is_last_chunk = (
            True if getattr(chunk, "chunk_position", "") == "last" else False
        )
        if meta_data["langgraph_node"] == "tools":
            memory_id = str(uuid.uuid4())
            memory = {"lastest_tool_call": chunk.name}
            global_long_term_memory.put(
                namespace_for_long_term_memory,
                memory_id,
                memory,
            )
        yield chunk, is_last_chunk


@agent_app.endpoint("/api/memory/short-term/{session_id}", methods=["GET"])
async def get_short_term_memory(session_id: str):
    if global_short_term_memory is None:
        return {"error": "Short-term memory not initialized yet."}

    config = {"configurable": {"thread_id": session_id}}

    value = await global_short_term_memory.aget_tuple(config)

    if value is None:
        return {"error": "No memory found for session_id"}

    return {
        "session_id": session_id,
        "messages": value.checkpoint["channel_values"]["messages"],
        "metadata": value.metadata,
    }


@agent_app.endpoint("/api/memory/short-term", methods=["GET"])
async def list_short_term_memory():
    if global_short_term_memory is None:
        return {"error": "Short-term memory not initialized yet."}

    result = []
    short_mems = list(global_short_term_memory.list(None))
    for short_mem in short_mems:
        ch_vals = short_mem.checkpoint["channel_values"]
        # Ignore the __pregel_tasks field, which is not serializable
        safe_dict = {
            key: value
            for key, value in ch_vals.items()
            if key != "__pregel_tasks"
        }
        result.append(safe_dict)
    return result


@agent_app.endpoint("/api/memory/long-term/{user_id}", methods=["GET"])
async def get_long_term_memory(user_id: str):
    if global_short_term_memory is None:
        return {"error": "Short-term memory not initialized yet."}
    namespace_for_long_term_memory = (user_id, "memories")
    long_term_mem = global_long_term_memory.search(
        namespace_for_long_term_memory,
    )

    def serialize_search_item(item):
        return {
            "namespace": item.namespace,
            "key": item.key,
            "value": item.value,
            "created_at": item.created_at,
            "updated_at": item.updated_at,
            "score": item.score,
        }

    serialized = [serialize_search_item(item) for item in long_term_mem]
    return serialized


if __name__ == "__main__":
    agent_app.run(host="127.0.0.1", port=8090)
```

### 2. 具有工具调用能力的高级智能体

一个更复杂的示例，演示具有工具调用能力的智能体：

- 实现了短期（对话）和长期（持久化）记忆
- 使用检查点机制跨会话保持状态
- 提供了用于检查内存状态的 API 端点
- 包含一个用于演示目的的自定义天气工具
- 使用带有 user_id 和 session_id 字段的自定义 `AgentState` 扩展
- 实现了工具调用结果的长期记忆存储

以下核心代码：

```{code-cell}
# -*- coding: utf-8 -*-
import os
import uuid

from langchain.agents import AgentState, create_agent
from langchain.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore

from agentscope_runtime.engine import AgentApp
from agentscope_runtime.engine.schemas.agent_schemas import AgentRequest

global_short_term_memory = None
global_long_term_memory = None

@tool
def get_weather(location: str, date: str) -> str:
    """Get the weather for a location and date."""
    print(f"Getting weather for {location} on {date}...")
    return f"The weather in {location} is sunny with a temperature of 25°C."

# Create the AgentApp instance
agent_app = AgentApp(
    app_name="LangGraphAgent",
    app_description="A LangGraph-based research assistant",
)

class CustomAgentState(AgentState):
    user_id: str
    session_id: dict

# Initialize services as instance variables
@agent_app.init
async def init_func(self):
    global global_short_term_memory
    global global_long_term_memory
    self.short_term_mem = InMemorySaver()
    self.long_term_mem = InMemoryStore()
    global_short_term_memory = self.short_term_mem
    global_long_term_memory = self.long_term_mem

# Query endpoint for LangGraph integration with tools
@agent_app.query(framework="langgraph")
async def query_func(
    self,
    msgs,
    request: AgentRequest = None,
    **kwargs,
):
    # Extract session information
    session_id = request.session_id
    user_id = request.user_id
    print(f"Received query from user {user_id} with session {session_id}")

    tools = [get_weather]

    # Choose the LLM that will drive the agent
    llm = ChatOpenAI(
        model="qwen-plus",
        api_key=os.environ.get("DASHSCOPE_API_KEY"),
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    )

    namespace_for_long_term_memory = (user_id, "memories")

    prompt = """You are a proactive research assistant. """

    agent = create_agent(
        llm,
        tools,
        system_prompt=prompt,
        checkpointer=self.short_term_mem,
        store=self.long_term_mem,
        state_schema=CustomAgentState,
        name="LangGraphAgent",
    )

    async for chunk, meta_data in agent.astream(
        input={"messages": msgs, "session_id": session_id, "user_id": user_id},
        stream_mode="messages",
        config={"configurable": {"thread_id": session_id}},
    ):
        is_last_chunk = (
            True if getattr(chunk, "chunk_position", "") == "last" else False
        )
        if meta_data["langgraph_node"] == "tools":
            memory_id = str(uuid.uuid4())
            memory = {"lastest_tool_call": chunk.name}
            global_long_term_memory.put(
                namespace_for_long_term_memory,
                memory_id,
                memory,
            )
        yield chunk, is_last_chunk
if __name__ == "__main__":
  agent_app.run(host="127.0.0.1", port=8090)
```

## ⚙️ 先决条件

```{note}
在开始之前，请确保您已经安装了 AgentScope Runtime 并配置了必要的 API 密钥。
```

1. **安装依赖**：
   ```bash
   pip install agentscope-runtime
   ```

2. **设置环境变量**：
   ```bash
   # 必需：DashScope API 密钥用于 Qwen 模型
   export DASHSCOPE_API_KEY="your-dashscope-api-key"
   ```

## ▶️ 运行示例

```{tip}
确保您已经在先决条件部分设置了所有必需的环境变量，然后再运行这些示例。
```

启动服务器后，您可以通过查询界面与智能体交互，并通过提供的 API 端点检查内存状态。

### 与智能体交互

服务器运行后，您可以使用 `/query` 端点向智能体发送查询：

```bash
curl -N \
  -X POST "http://localhost:8090/process" \
  -H "Content-Type: application/json" \
  -d '{
    "input": [
      {
        "role": "user",
        "content": [
          { "type": "text", "text": "上海天气如何？" }
        ]
      }
    ],
    "session_id": "session_id_123",
    "user_id": "user_id_123"
  }'
```

## ✨ 关键特性展示

### LangGraph 集成
- 使用 `AgentState` 进行状态管理
- 使用 `StateGraph` 定义工作流
- 检查点机制实现持久化状态
- 流式响应实现实时交互

### 内存管理
- 短期记忆用于对话历史
- 长期记忆用于持久化存储
- API 端点检查内存状态
- 基于会话的内存隔离

### 工具集成
- 使用 LangChain 的 `@tool` 装饰器定义自定义工具
- 工具调用和结果处理

## 🌐 API 端点

```{important}
以下 API 端点仅在运行高级智能体示例时可用。
```

运行高级智能体示例时，以下 API 端点可用：

- `POST /process` - 向智能体发送查询
- `GET /api/memory/short-term/{session_id}` - 获取会话的短期记忆
- `GET /api/memory/short-term` - 列出所有短期记忆
- `GET /api/memory/long-term/{user_id}` - 获取用户的长期记忆

## 🔧 自定义

您可以通过以下方式自定义这些示例：

1. **添加新工具**：使用 `@tool` 装饰器定义自定义工具
2. **更改 LLM**：修改 `ChatOpenAI` 初始化以使用不同的模型
3. **扩展工作流**：向状态图添加新节点和边
4. **自定义内存**：实现不同的内存存储后端

## 📚 相关文档

- [LangGraph 文档](https://langchain-ai.github.io/langgraph/)
- [AgentScope Runtime 文档](https://runtime.agentscope.io/)