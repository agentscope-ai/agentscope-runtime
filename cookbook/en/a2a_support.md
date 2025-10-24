# A2A Protocol Support Documentation

This document explains how to integrate and use the **A2A (Agent-to-Agent) protocol** in the Agentscope Runtime SDK, allowing your agent to support the A2A standard and automatically generate the agent card.

## 1. Background & Purpose

A2A (Agent-to-Agent) protocol defines a standard interface for interaction between intelligent agents (including action, card, metadata, etc.). By wrapping your agent with `A2AFastAPIDefaultAdapter`, you can instantly enable A2A protocol support and automatically generate the agent card.

## 2. Main Classes and Methods

- `A2AFastAPIDefaultAdapter(agent)`: Wraps an existing agent (e.g., AgentScopeAgent) as an A2A protocol-compliant server.
- `protocol_adapters`: A list specifying supported protocol adapters when deploying the runner, including the A2A protocol adapter.

## 3. Integration Steps

Below are the key steps you need to add A2A protocol support to your agent:

### **Step 1: Create your agent instance**
```python
agent = AgentScopeAgent(
        name="Friday",
        model=OpenAIChatModel(
            "gpt-4",
            api_key=os.getenv("OPENAI_API_KEY"),
        ),
        agent_config={
            "sys_prompt": "You're a helpful assistant named Friday.",
        },
        agent_builder=ReActAgent,
    )
```
### **Step 2: Wrap agent with A2A protocol adapter**
```python
a2a_protocol = A2AFastAPIDefaultAdapter(agent=agent)
```

### **Step 3: Build context management services**
```python
session_history_service = InMemorySessionHistoryService()
memory_service = InMemoryMemoryService()
context_manager = ContextManager(
    session_history_service=session_history_service,
    memory_service=memory_service,
)

```

### **Step 4: Build runner**
```python
runner = Runner(
    agent=agent,
    context_manager=context_manager,
)
```

### **Step 5: Deploy runner with the protocol_adapters argument**
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


## 4. Complete Example

The following example demonstrates how to deploy a local agent service that supports A2A protocol:

```python
import asyncio
import os

from agentscope_runtime.engine import Runner, LocalDeployManager
from agentscope_runtime.engine.agents.agentscope_agent import AgentScopeAgent
from agentscope_runtime.engine.deployers.adapter.a2a import A2AFastAPIDefaultAdapter
from agentscope.agent import ReActAgent
from agentscope.model import OpenAIChatModel
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
        model=OpenAIChatModel(
            "gpt-4",
            api_key=os.getenv("OPENAI_API_KEY"),
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

## 5. Notes

Wrapping your agent with A2AFastAPIDefaultAdapter and passing it through protocol_adapters are both required for enabling the A2A protocol and auto-generating your agent card endpoint.