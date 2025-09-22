# Responses API 协议支持文档

本文档介绍如何在 Agentscope Runtime SDK 中集成和使用 **Responses API 协议**，让你的 Agent 支持 OpenAI Response API 兼容的流式响应接口。

## 1. 背景和目的

Responses API 协议提供了与 OpenAI Response API 兼容的流式响应接口，支持 Server-Sent Events (SSE) 流式输出。通过使用 `ResponseAPIDefaultAdapter` 包装你的智能体（agent），可以立刻启用 Responses API 协议支持，实现与 OpenAI 兼容的流式响应体验。

## 2. 主要类和方法

- `ResponseAPIDefaultAdapter()`：将已有的 agent 包装为符合 Responses API 协议的服务端。
- `protocol_adapters`：在部署 runner 时指定支持的协议适配器列表，其中包括 Responses API 协议适配器。
- 支持流式响应：通过 SSE (Server-Sent Events) 实现实时流式输出。

## 3. 集成步骤

你只需按以下关键步骤，即可让你的 agent 支持 Responses API 协议：

### **步骤 1：创建 agent 实例**
```python
from agentscope.agent import ReActAgent
from agentscope.model import DashScopeChatModel
from agentscope_runtime.engine.agents.agentscope_agent import AgentScopeAgent

agent = AgentScopeAgent(
    name="Friday",
    model=DashScopeChatModel(
        "qwen-max",
        api_key=os.getenv("DASHSCOPE_API_KEY"),
    ),
    agent_config={
        "sys_prompt": "You're a helpful assistant named {name}.",
    },
    agent_builder=ReActAgent,
)
```

### **步骤 2：使用 Responses API 协议适配器包装 agent**
```python
from agentscope_runtime.engine.deployers.adapter.responses.response_api_protocol_adapter import ResponseAPIDefaultAdapter

responses_adapter = ResponseAPIDefaultAdapter()
```

### **步骤 3：构建上下文管理服务**
```python
from agentscope_runtime.engine.services.context_manager import ContextManager
from agentscope_runtime.engine.services.memory_service import InMemoryMemoryService
from agentscope_runtime.engine.services.session_history_service import InMemorySessionHistoryService

session_history_service = InMemorySessionHistoryService()
memory_service = InMemoryMemoryService()
context_manager = ContextManager(
    session_history_service=session_history_service,
    memory_service=memory_service,
)
```

### **步骤 4：构建 Runner**
```python
from agentscope_runtime.engine import Runner

runner = Runner(
    agent=agent,
    context_manager=context_manager,
)
```

### **步骤 5：使用 protocol_adapters 参数部署 runner**
```python
from agentscope_runtime.engine import LocalDeployManager

deploy_manager = LocalDeployManager(host="localhost", port=server_port)

deployment_info = await runner.deploy(
    deploy_manager,
    endpoint_path=f"/{server_endpoint}",
    protocol_adapters=[responses_adapter],  # PROTOCOL ADAPTERS declaration
)

print("✅ Service deployed successfully!")
print(f"URL: {deployment_info['url']}/{server_endpoint}")
```

## 4. 完整示例

以下示例展示如何部署一个本地支持 Responses API 协议的 agent 服务：

```python
import asyncio
import os
from dotenv import load_dotenv

from agentscope_runtime.engine import Runner, LocalDeployManager
from agentscope_runtime.engine.agents.agentscope_agent import AgentScopeAgent
from agentscope_runtime.engine.deployers.adapter.responses.response_api_protocol_adapter import ResponseAPIDefaultAdapter
from agentscope_runtime.engine.services.context_manager import ContextManager
from agentscope_runtime.engine.services.memory_service import InMemoryMemoryService
from agentscope_runtime.engine.services.session_history_service import InMemorySessionHistoryService

async def main():
    # Load environment variables
    load_dotenv()

    # Read environment variables
    server_port = int(os.environ.get("SERVER_PORT", "8090"))
    server_endpoint = os.environ.get("SERVER_ENDPOINT", "agent")

    # Step 1: Create agent instance
    from agentscope.agent import ReActAgent
    from agentscope.model import DashScopeChatModel

    agent = AgentScopeAgent(
        name="Friday",
        model=DashScopeChatModel(
            "qwen-max",
            api_key=os.getenv("DASHSCOPE_API_KEY"),
        ),
        agent_config={
            "sys_prompt": "You're a helpful assistant named {name}.",
        },
        agent_builder=ReActAgent,
    )

    # Step 2: Wrap agent with Responses API protocol adapter
    responses_adapter = ResponseAPIDefaultAdapter()

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

    try:
        deployment_info = await runner.deploy(
            deploy_manager,
            endpoint_path=f"/{server_endpoint}",
            protocol_adapters=[responses_adapter],  # PROTOCOL ADAPTERS declaration
        )

        print("✅ Service deployed successfully!")
        print(f"   URL: {deployment_info['url']}")
        print(f"   Endpoint: {deployment_info['url']}/{server_endpoint}")
        print("\nAgent Service is running in the background.")

        # Keep the service running
        await asyncio.sleep(3600)  # Run for 1 hour

    except (KeyboardInterrupt, asyncio.CancelledError):
        print("\nShutdown signal received. Stopping the service...")
        if deploy_manager.is_running:
            await deploy_manager.stop()
        print("✅ Service stopped.")
    except Exception as e:
        print(f"An error occurred: {e}")
        if deploy_manager.is_running:
            await deploy_manager.stop()
    finally:
        if deploy_manager.is_running:
            await deploy_manager.stop()
        print("✅ Service stopped after test.")

if __name__ == "__main__":
    asyncio.run(main())
```

## 5. API 端点

部署成功后，你的服务将提供以下 API 端点：

- **主要端点**: `POST /compatible-mode/v1/responses`
- **支持流式响应**: 通过 Server-Sent Events (SSE) 实现实时流式输出
- **CORS 支持**: 支持跨域请求

## 6. 请求格式

Responses API 使用与 OpenAI Response API 兼容的请求格式：

```json
{
  "model": "your-model-name",
  "messages": [
    {
      "role": "user",
      "content": "Hello, how are you?"
    }
  ],
  "stream": true,
  "max_tokens": 1000,
  "temperature": 0.7
}
```

## 7. 注意事项

1. **协议适配器**: 启用 Responses API 协议，必须将你的 agent 用 `ResponseAPIDefaultAdapter` 包装，并通过 `protocol_adapters` 参数进行传递。

2. **流式响应**: Responses API 协议支持流式输出，客户端需要正确处理 SSE 事件。

3. **超时设置**: 默认请求超时时间为 300 秒，可通过 `timeout` 参数调整。

4. **并发限制**: 默认最大并发请求数为 100，可通过 `max_concurrent_requests` 参数调整。

5. **环境变量**: 确保设置正确的 API 密钥（如 `DASHSCOPE_API_KEY`）和其他必要的环境变量。

## 8. 故障排除

- **服务启动失败**: 检查端口是否被占用，确保环境变量设置正确
- **API 调用失败**: 检查请求格式是否符合 OpenAI Response API 规范
- **流式响应中断**: 检查网络连接和客户端 SSE 处理逻辑
