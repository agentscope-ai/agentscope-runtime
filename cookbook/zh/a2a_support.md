# A2A 协议支持文档

本文档介绍如何在 Agentscope Runtime SDK 中集成和使用 **A2A（Agent-to-Agent）协议**，让你的 Agent 支持 A2A 标准，并自动生成 agent card。

## 1. 背景和目的

A2A（Agent-to-Agent）协议定义了智能体之间交互（包括 action、card、metadata 等）的标准接口。通过使用 `A2AFastAPIDefaultAdapter` 包装你的智能体（agent），可以立刻启用 A2A 协议支持，并自动生成 agent card。

## 2. 主要类和方法

- `A2AFastAPIDefaultAdapter(agent)`：将已有的 agent（如 AgentScopeAgent）包装为符合 A2A 协议的服务端。
- `protocol_adapters`：在部署 runner 时指定支持的协议适配器列表，其中包括 A2A 协议适配器。

## 3. 集成步骤

你只需按以下关键步骤，即可让你的 agent 支持 A2A 协议：

### **步骤 1：创建 agent 实例**
```python
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
```
### **步骤 2：使用 A2A 协议适配器包装 agent**
```python
a2a_protocol = A2AFastAPIDefaultAdapter(agent=agent)
```

### **步骤 3：构建上下文管理服务**
```python
session_history_service = InMemorySessionHistoryService()
memory_service = InMemoryMemoryService()
context_manager = ContextManager(
    session_history_service=session_history_service,
    memory_service=memory_service,
)

```

### **步骤 4：构建 Runner**
```python
runner = Runner(
    agent=agent,
    context_manager=context_manager,
)
```

### **步骤 5：使用 protocol_adapters 参数部署 runner**
```python
deploy_manager = LocalDeployManager(host="localhost", port=server_port)

deployment_info = await runner.deploy(
    deploy_manager,
    endpoint_path=f"/{server_endpoint}",
    protocol_adapters=[a2a_protocol],  # PROTOCOL ADAPTERS declaration
)

print("✅ Service deployed successfully!")
print(f"URL: {deployment_info['url']}/{server_endpoint}")
```


## 4. 完整示例

以下示例展示如何部署一个本地支持 A2A 协议的 agent 服务：

```python
import asyncio
import os

from agentscope_runtime.engine import Runner, LocalDeployManager
from agentscope_runtime.engine.agents.agentscope_agent import AgentScopeAgent
from agentscope_runtime.engine.deployers.adapter.a2a import A2AFastAPIDefaultAdapter
from agentscope.agent import ReActAgent
from agentscope.model import DashScopeChatModel
from agentscope_runtime.engine.services.context_manager import ContextManager
from agentscope_runtime.engine.services.memory_service import InMemoryMemoryService
from agentscope_runtime.engine.services.session_history_service import InMemorySessionHistoryService

async def main():
    # Read environment variables
    server_port = int(os.environ.get("SERVER_PORT", "8090"))
    server_endpoint = os.environ.get("SERVER_ENDPOINT", "agent")

    # Step 1: Create agent instance
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

    # Step 2: Wrap agent with A2A protocol adapter
    a2a_protocol = A2AFastAPIDefaultAdapter(agent=agent)

    # Step 3: Build context management services
    session_history_service = InMemorySessionHistoryService()
    memory_service = InMemoryMemoryService()
    context_manager = ContextManager(
        session_history_service=session_history_service,
        memory_service=memory_service,
    )

    # Step 4: Build runner and deploy
    runner = Runner(
        agent=agent,
        context_manager=context_manager,
    )

    deploy_manager = LocalDeployManager(host="localhost", port=server_port)

    deployment_info = await runner.deploy(
        deploy_manager,
        endpoint_path=f"/{server_endpoint}",
        protocol_adapters=[a2a_protocol],  # PROTOCOL ADAPTERS declaration
    )

    print("✅ Service deployed successfully!")
    print(f"URL: {deployment_info['url']}/{server_endpoint}")

asyncio.run(main())
```

## 5. 注意事项

启用 A2A 协议并自动生成 agent card 端点，必须将你的 agent 用 A2AFastAPIDefaultAdapter 包装，并通过 protocol_adapters 参数进行传递。