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
from contextlib import asynccontextmanager
from agentscope_runtime.engine import Runner
from agentscope_runtime.engine.agents.agentscope_agent import AgentScopeAgent
from agentscope.model import DashScopeChatModel
from agentscope.agent import ReActAgent
from agentscope_runtime.engine.schemas.agent_schemas import (
    MessageType,
    RunStatus,
    AgentRequest,
)
from agentscope_runtime.engine.services.context_manager import (
    ContextManager,
)

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

### 步骤3：创建Runner上下文管理器

建立用于管理智能体生命周期的运行时上下文：

```{code-cell}
@asynccontextmanager
async def create_runner():
    async with Runner(
        agent=llm_agent,
        context_manager=ContextManager(),
    ) as runner:
        print("✅ Runner创建成功")
        yield runner
```

### 步骤4：定义交互函数

实现一个函数来测试您的智能体并获取流式响应：

```{code-cell}
async def interact_with_agent(runner):
    # Create a request
    request = AgentRequest(
        input=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "法国的首都是什么？",
                    },
                ],
            },
        ],
    )

    # 流式获取响应
    print("🤖 智能体正在处理您的请求...")
    all_result = ""
    async for message in runner.stream_query(request=request):
        # Check if this is a completed message
        if (
            message.object == "message"
            and MessageType.MESSAGE == message.type
            and RunStatus.Completed == message.status
        ):
            all_result = message.content[0].text

    print(f"📝智能体回复: {all_result}")
    return all_result
```

### 步骤5：测试智能体交互

执行交互流程以测试您的智能体功能：

```{code-cell}
async def test_interaction():
    async with create_runner() as runner:
        await interact_with_agent(runner)

await test_interaction()
```

## 使用部署器部署智能体

AgentScope Runtime提供了强大的部署系统，允许您将智能体作为Web服务公开。

### 步骤6：创建部署函数

使用 `LocalDeployManager` 设置部署配置：

```{code-cell}
from agentscope_runtime.engine.deployers import LocalDeployManager

async def deploy_agent(runner):
    # 创建部署管理器
    deploy_manager = LocalDeployManager(
        host="localhost",
        port=8090,
    )

    # 将智能体部署为流式服务
    deploy_result = await runner.deploy(
        deploy_manager=deploy_manager,
        endpoint_path="/process",
        stream=True,  # Enable streaming responses
    )
    print(f"🚀智能体部署在: {deploy_result}")
    print(f"🌐服务URL: {deploy_manager.service_url}")
    print(f"💚 健康检查: {deploy_manager.service_url}/health")

    return deploy_manager
```

### 步骤7：执行部署

将您的智能体部署为生产就绪的服务：

```{code-cell}
async def run_deployment():
    async with create_runner() as runner:
        deploy_manager = await deploy_agent(runner)

    # Keep the service running (in production, you'd handle this differently)
    print("🏃 Service is running...")

    return deploy_manager

# Deploy the agent
deploy_manager = await run_deployment()
```

```{note}
智能体运行器公开了一个`deploy` 方法，该方法接受一个 `DeployManager` 实例并部署智能体。
服务端口在创建 `LocalDeployManager` 时通过参数 `port`设置。
服务端点路径在部署智能体时通过参数 `endpoint_path` 设置。
在此示例中，我们将端点路径设置为 `/process`。
部署后，您可以在`http://localhost:8090/process` 访问服务。
```

### （可选）步骤8：部署多个智能体

Agentscope Runtime支持在不同端口上部署多个智能体。

```{code-cell}
async def deploy_multiple_agents():
    async with create_runner() as runner:
        # 在不同端口上部署多个智能体
        deploy_manager1 = LocalDeployManager(host="localhost", port=8092)
        deploy_manager2 = LocalDeployManager(host="localhost", port=8093)

        # 部署第一个智能体
        result1 = await runner.deploy(
            deploy_manager=deploy_manager1,
            endpoint_path="/agent1",
            stream=True,
        )

        # 部署第二个智能体（您可以使用不同的runner/智能体）
        result2 = await runner.deploy(
            deploy_manager=deploy_manager2,
            endpoint_path="/agent2",
            stream=True,
        )

        print(f"🚀 智能体1已部署: {result1}")
        print(f"🚀 智能体2已部署: {result2}")

        return deploy_manager1, deploy_manager2

# Deploy multiple agents
deploy_managers = await deploy_multiple_agents()
```

### 步骤9：测试部署的智能体

使用HTTP请求测试您部署的智能体：

```{code-cell}
import requests


def test_deployed_agent():
    # 准备测试负载
    payload = {
        "input": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "法国的首都是什么？"},
                ],
            },
        ],
        "session_id": "test_session_001",
        "user_id": "test_user_001",
    }

    print("🧪 测试部署的智能体...")

    # 测试流式响应
    try:
        response = requests.post(
            "http://localhost:8090/process",
            json=payload,
            stream=True,
            timeout=30,
        )

        print("📡 流式响应:")
        for line in response.iter_lines():
            if line:
                print(f"{line.decode('utf-8')}")
        print("✅ 流式测试完成")
    except requests.exceptions.RequestException as e:
        print(f"❌ 流式测试失败: {e}")
    except requests.exceptions.RequestException as e:
        print(f"ℹ️ JSON端点不可用或失败: {e}")


# Run the test
test_deployed_agent()
```

### 步骤10：服务管理

#### 服务状态

```{code-cell}
# 检查服务状态
print(f"服务运行中: {deploy_manager.is_running}")
print(f"服务URL: {deploy_manager.service_url}")
```

#### 停止服务

```{code-cell}
async def stop_services(*_deploy_managers):
    """停止部署的服务"""
    async def _stop():
        for i, manager in enumerate(_deploy_managers):
            if manager.is_running:
                await manager.stop()
            print(f"🛑 服务{i}已停止")
    await _stop()

await stop_services(deploy_manager)
```

## 总结

本指南演示了使用AgentScope Runtime框架的两个主要场景：

### 🏃 Runner用于简单的智能体交互

使用Runner 类构建和测试智能体：

✅ 创建和配置智能体（AgentScope、Agno、LangGraph）

✅ 使用上下文管理设置`Runner`

✅ 通过流式传输测试智能体响应

✅ 在部署前验证智能体功能

### 🚀 智能体部署为生产服务

将智能体部署为生产就绪的Web服务：

✅使用 `LocalDeployManager` 进行本地部署

✅将智能体公开为FastAPI Web服务

✅ 支持流式和JSON响应

✅ 包括健康检查和服务监控

✅ 处理多个智能体部署
