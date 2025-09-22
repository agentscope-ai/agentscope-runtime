# Responses API Protocol Support Documentation

This document explains how to integrate and use the **Responses API Protocol** in Agentscope Runtime SDK, enabling your Agent to support OpenAI Response API compatible streaming response interfaces.

## 1. Background and Purpose

The Responses API Protocol provides a streaming response interface compatible with OpenAI Response API, supporting Server-Sent Events (SSE) streaming output. By wrapping your agent with `ResponseAPIDefaultAdapter`, you can immediately enable Responses API protocol support and achieve OpenAI-compatible streaming response experience.

## 2. Main Classes and Methods

- `ResponseAPIDefaultAdapter()`: Wraps existing agents as Responses API protocol-compliant servers.
- `protocol_adapters`: Specifies the list of supported protocol adapters when deploying runners, including Responses API protocol adapters.
- Streaming Response Support: Implements real-time streaming output through SSE (Server-Sent Events).

## 3. Integration Steps

You only need to follow these key steps to enable Responses API protocol support for your agent:

### **Step 1: Create Agent Instance**
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

### **Step 2: Wrap Agent with Responses API Protocol Adapter**
```python
from agentscope_runtime.engine.deployers.adapter.responses.response_api_protocol_adapter import ResponseAPIDefaultAdapter

responses_adapter = ResponseAPIDefaultAdapter()
```

### **Step 3: Build Context Management Services**
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

### **Step 4: Build Runner**
```python
from agentscope_runtime.engine import Runner

runner = Runner(
    agent=agent,
    context_manager=context_manager,
)
```

### **Step 5: Deploy Runner with protocol_adapters Parameter**
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

## 4. Complete Example

The following example demonstrates how to deploy a local agent service that supports Responses API protocol:

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

## 5. API Endpoints

After successful deployment, your service will provide the following API endpoints:

- **Main Endpoint**: `POST /compatible-mode/v1/responses`
- **Streaming Response Support**: Real-time streaming output through Server-Sent Events (SSE)
- **CORS Support**: Cross-origin request support

## 6. Request Format

Responses API uses OpenAI Response API compatible request format:

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

## 7. Important Notes

1. **Protocol Adapter**: To enable Responses API protocol, you must wrap your agent with `ResponseAPIDefaultAdapter` and pass it through the `protocol_adapters` parameter.

2. **Streaming Response**: Responses API protocol supports streaming output, and clients need to properly handle SSE events.

3. **Timeout Settings**: Default request timeout is 300 seconds, adjustable via the `timeout` parameter.

4. **Concurrency Limits**: Default maximum concurrent requests is 100, adjustable via the `max_concurrent_requests` parameter.

5. **Environment Variables**: Ensure correct API keys (such as `DASHSCOPE_API_KEY`) and other necessary environment variables are set.

## 8. Troubleshooting

- **Service Startup Failure**: Check if the port is occupied and ensure environment variables are set correctly
- **API Call Failure**: Check if the request format complies with OpenAI Response API specifications
- **Streaming Response Interruption**: Check network connection and client SSE handling logic
