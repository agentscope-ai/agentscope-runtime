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

# 快速开始

本教程演示如何在 **AgentScope Runtime** 框架中构建一个简单的智能体并将其部署为服务。

## 前置条件

### 🔧 安装要求

安装带有基础依赖的 AgentScope Runtime：

```bash
pip install agentscope-runtime
```

### 🔑 API密钥配置

您需要为所选的大语言模型提供商提供API密钥。本示例使用DashScope（Qwen）：

```bash
export DASHSCOPE_API_KEY="your_api_key_here"
```

## 分步实现

### 步骤1：导入依赖

首先导入所有必要的模块：

```{code-cell}
import os

from agentscope_runtime.engine import AgentApp
from agentscope_runtime.engine.agents.agentscope_agent import AgentScopeAgent
from agentscope_runtime.engine.deployers import LocalDeployManager
from agentscope.model import OpenAIChatModel
from agentscope.agent import ReActAgent


print("✅ 依赖导入成功")
```

### 步骤2：创建智能体

我们这里使用agentscope作为示例：

```{code-cell}
from agentscope.agent import ReActAgent
from agentscope.model import DashScopeChatModel
from agentscope_runtime.engine.agents.agentscope_agent import AgentScopeAgent

agent = AgentScopeAgent(
    name="Friday",
    model=DashScopeChatModel(
        "qwen-turbo",
        api_key=os.getenv("DASHSCOPE_API_KEY"),
    ),
    agent_config={
        "sys_prompt": "You're a helpful assistant named Friday.",
    },
    agent_builder=ReActAgent,
)

print("✅ AgentScope agent created successfully")
```
```{note}
要使用来自其他框架的其他LLM和智能体实现，请参考 {ref}`Agno智能体<agno-agent-zh>`、{ref}`AutoGen智能体 <autogen-agent-zh>`和{ref}`LangGraph智能体 <langgraph-agent-zh>`。
```

(agno-agent-zh)=

#### （可选）使用Agno Agent

````{note}
如果您想要使用Agno的智能体，您应该通过以下命令安装Agno：
```bash
pip install "agentscope-runtime[agno]"
```
````

```{code-cell}
from agno.agent import Agent
from agno.models.openai import OpenAIChat
from agentscope_runtime.engine.agents.agno_agent import AgnoAgent

agent = AgnoAgent(
    name="Friday",
    model=OpenAIChat(
        id="gpt-4",
    ),
    agent_config={"instructions": "You're a helpful assistant.",
    },
    agent_builder=Agent,
)

print("✅ Agno agent created successfully")
```

(autogen-agent-zh)=

#### （可选）使用AutoGen Agent

````{note}
如果您想要使用AutoGen的智能体，您应该通过以下命令安装AutoGen：
```bash
pip install "agentscope-runtime[autogen]"
```
````

```{code-cell}
from autogen_agentchat.agents import AssistantAgent
from autogen_ext.models.openai import OpenAIChatCompletionClient
from agentscope_runtime.engine.agents.autogen_agent import AutogenAgent

agent = AutogenAgent(
    name="Friday",
    model=OpenAIChatCompletionClient(
        model="gpt-4",
    ),
    agent_config={
        "system_message": "You're a helpful assistant",
    },
    agent_builder=AssistantAgent,
)

print("✅ AutoGen agent created successfully")
```

(langgraph-agent-zh)=

#### （可选）使用 LangGraph Agent

````{note}
如果您想要使用LangGraph的智能体，您应该通过以下命令安装LangGraph：
```bash
pip install "agentscope-runtime[langgraph]"
```
````

```{code-cell}
from typing import TypedDict
from langgraph import graph, types
from agentscope_runtime.engine.agents.langgraph_agent import LangGraphAgent


# 定义状态
class State(TypedDict, total=False):
    id: str


# 定义节点函数
async def set_id(state: State):
    new_id = state.get("id")
    assert new_id is not None, "must set ID"
    return types.Command(update=State(id=new_id), goto="REVERSE_ID")


async def reverse_id(state: State):
    new_id = state.get("id")
    assert new_id is not None, "ID must be set before reversing"
    return types.Command(update=State(id=new_id[::-1]))


state_graph = graph.StateGraph(state_schema=State)
state_graph.add_node("SET_ID", set_id)
state_graph.add_node("REVERSE_ID", reverse_id)
state_graph.set_entry_point("SET_ID")
compiled_graph = state_graph.compile(name="ID Reversal")
agent = LangGraphAgent(graph=compiled_graph)

print("✅ LangGraph agent created successfully")
```

### 步骤3：创建并启动Agent App

用agent和 `AgentApp` 创建一个 Agent API 服务器：

```{code-cell}
app = AgentApp(agent=agent, endpoint_path="/process")

app.run(host="0.0.0.0", port=8090)
```

运行后，服务器会启动并监听：`http://localhost:8090/process`

### 步骤4：发送一个请求

你可以使用 `curl` 向 API 发送 JSON 输入：

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
    ]
  }'
```

你将会看到以 **Server-Sent Events (SSE)** 格式流式输出的响应：

```bash
data: {"sequence_number":0,"object":"response","status":"created", ... }
data: {"sequence_number":1,"object":"response","status":"in_progress", ... }
data: {"sequence_number":2,"object":"content","status":"in_progress","text":"The" }
data: {"sequence_number":3,"object":"content","status":"in_progress","text":" capital of France is Paris." }
data: {"sequence_number":4,"object":"message","status":"completed","text":"The capital of France is Paris." }
```

### 步骤5: 使用 Deployer 部署代理

AgentScope Runtime 提供了一个功能强大的部署系统，可以将你的智能体部署到远程或本地容器中。这里我们以 `LocalDeployManager` 为例：

```{code-cell}
async def main():
    await app.deploy(LocalDeployManager(host="0.0.0.0", port=8091))
```

这段代码会在指定的端口运行你的智能体API Server，使其能够响应外部请求。除了基本的 HTTP API 访问外，你还可以使用不同的协议与智能体进行交互，例如：A2A、Response API、Agent API等。详情请参考 {doc}`protocol`。
