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

# Quick Start

This guide demonstrates how to build a simple agent in the **AgentScope Runtime** framework and deploy it as a service.

## Prerequisites

### 🔧 Installation Requirements

Install AgentScope Runtime with basic dependencies:

```bash
pip install agentscope-runtime
```

### 🔑 API Key Configuration

You'll need an API key for your chosen LLM provider. This example uses DashScope (Qwen):

```bash
export DASHSCOPE_API_KEY="your_api_key_here"
```

## Step-by-Step Implementation

### Step 1: Import Dependencies

Start by importing all necessary modules:

```{code-cell}
import os
from contextlib import asynccontextmanager
from agentscope_runtime.engine import Runner
from agentscope_runtime.engine.agents.llm_agent import LLMAgent
from agentscope_runtime.engine.llms import QwenLLM
from agentscope_runtime.engine.schemas.agent_schemas import (
    MessageType,
    RunStatus,
    AgentRequest,
)
from agentscope_runtime.engine.services.context_manager import (
    ContextManager,
)

print("✅ Dependencies imported successfully")
```

### Step 2: Create LLM Agent

Initialize your LLM model and create the agent:

```{code-cell}
# Create an LLM instance
model = QwenLLM(
    model_name="qwen-turbo",
    api_key=os.getenv("DASHSCOPE_API_KEY")
)

# Create the LLM Agent
llm_agent = LLMAgent(
    model=model,
    name="llm_agent",
    description="A simple LLM agent for text generation",
)

print("✅ LLM Agent created successfully")
```

```{note}
For utilizing other LLM and agent implementations from other framework, please refer to {ref}`AgentScope Agent <agentscope-agent>`, {ref}`Agno Agent <agno-agent>`, {ref}`AutoGen Agent <autogen-agent>`, and {ref}`LangGraph Agent <langgraph-agent>`.
```

(agentscope-agent)=

#### (Optional) With AgentScope Agent

````{note}
If you want to use Agent from AgentScope, you should install AgentScope via:
```bash
pip install "agentscope-runtime[agentscope]"
```
````

```{code-cell}
from agentscope.agent import ReActAgent
from agentscope.model import OpenAIChatModel
from agentscope_runtime.engine.agents.agentscope_agent import AgentScopeAgent

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

print("✅ AgentScope agent created successfully")
```

(agno-agent)=

#### (Optional) With Agno Agent

````{note}
If you want to use Agent from Agno, you should install Agno via:
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
    agent_config={
        "instructions": "You're a helpful assistant.",
    },
    agent_builder=Agent,
)

print("✅ Agno agent created successfully")
```

(autogen-agent)=

#### (Optional) With AutoGen Agent

````{note}
If you want to use Agent from AutoGen, you should install AutoGen via:
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

(langgraph-agent)=

#### (Optional) With LangGraph Agent

````{note}
If you want to use Agent from LangGraph, you should install LangGraph via:
```bash
pip install "agentscope-runtime[langgraph]"
```
````

```{code-cell}
from typing import TypedDict
from langgraph import graph, types
from agentscope_runtime.engine.agents.langgraph_agent import LangGraphAgent


# define the state
class State(TypedDict, total=False):
    id: str


# define the node functions
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

### Step3: Create Runner

Establish the runtime context for managing agent lifecycle:

```{code-cell}
@asynccontextmanager
async def create_runner():
    async with Runner(
        agent=llm_agent,
        context_manager=ContextManager(),
    ) as runner:
        print("✅ Runner created successfully")
        yield runner
```

### Step 4: Define Interaction Function

Implement a function to test your agent with streaming responses:

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
                        "text": "What is the capital of France?",
                    },
                ],
            },
        ],
    )

    # Stream the response
    print("🤖 Agent is processing your request...")
    all_result = ""
    async for message in runner.stream_query(request=request):
        # Check if this is a completed message
        if (
            message.object == "message"
            and MessageType.MESSAGE == message.type
            and RunStatus.Completed == message.status
        ):
            all_result = message.content[0].text

    print(f"📝 Agent response: {all_result}")
    return all_result
```

### Step 5: Test Agent Interaction

Execute the interaction flow to test your agent's functionality:

```{code-cell}
async def test_interaction():
    async with create_runner() as runner:
        await interact_with_agent(runner)

await test_interaction()
```

## Deploy the Agent with Deployer

The AgentScope Runtime provides a powerful deployment system that allows you to expose your agents as web services.

### Step 6: Create Deployment Function

Set up the deployment configuration with the `LocalDeployManager`:

```{code-cell}
from agentscope_runtime.engine.deployers import LocalDeployManager

async def deploy_agent(runner):
    # Create deployment manager
    deploy_manager = LocalDeployManager(
        host="localhost",
        port=8090,
    )

    # Deploy the agent as a streaming service
    deploy_result = await runner.deploy(
        deploy_manager=deploy_manager,
        endpoint_path="/process",
        stream=True,  # Enable streaming responses
    )
    print(f"🚀Agent deployed at: {deploy_result}")
    print(f"🌐 Service URL: {deploy_manager.service_url}")
    print(f"💚 Health check: {deploy_manager.service_url}/health")

    return deploy_manager
```

### Step 7: Execute Deployment

Deploy your agent as a production-ready service:

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
The agent runner exposes a `deploy` method that takes a `DeployManager` instance and deploys the agent.
The service port is set as the parameter `port` when creating the `LocalDeployManager`.
The service endpoint path is set as the parameter `endpoint_path` when deploying the agent.
In this example, we set the endpoint path to `/process`.
After deployment, you can access the service at `http://localhost:8090/process`.
```

### (Optional) Step 8: Deploy Multiple Agents

Agentscope Runtime supports deploying multiple agents on different ports.
```{code-cell}
async def deploy_multiple_agents():
    async with create_runner() as runner:
        # Deploy multiple agents on different ports
        deploy_manager1 = LocalDeployManager(host="localhost", port=8092)
        deploy_manager2 = LocalDeployManager(host="localhost", port=8093)

        # Deploy first agent
        result1 = await runner.deploy(
            deploy_manager=deploy_manager1,
            endpoint_path="/agent1",
            stream=True,
        )

        # Deploy second agent (you could use different runner/agent)
        result2 = await runner.deploy(
            deploy_manager=deploy_manager2,
            endpoint_path="/agent2",
            stream=True,
        )

        print(f"🚀 Agent 1deployed: {result1}")
        print(f"🚀 Agent2 deployed: {result2}")

        return deploy_manager1, deploy_manager2

# Deploy multiple agents
deploy_managers = await deploy_multiple_agents()
```

### Step 9: Test the Deployed Agent

Test your deployed agent using HTTP requests:

```{code-cell}
import requests


def test_deployed_agent():
    # Prepare the test payload
    payload = {
        "input": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "What is the capital of France?"},
                ],
            },
        ],
        "session_id": "test_session_001",
        "user_id": "test_user_001",
    }

    print("🧪 Testing deployed agent...")

    # Test streaming responses
    try:
        response = requests.post(
            "http://localhost:8090/process",
            json=payload,
            stream=True,
            timeout=30,
        )

        print("📡 Streaming Response:")
        for line in response.iter_lines():
            if line:
                print(f"{line.decode('utf-8')}")
        print("✅ Streaming test completed")
    except requests.exceptions.RequestException as e:
        print(f"❌ Streaming test failed: {e}")

    # Test JSON responses (if available)
    try:
        response = requests.post(
            "http://localhost:8090/process",
            json=payload,
            timeout=30,
        )

        if response.status_code == 200:
            print(f"📄 JSON Response: {response.content}")
            print("✅ JSON test completed")
        else:
            print(f"⚠️ JSON endpoint returned status: {response.status_code}")

    except requests.exceptions.RequestException as e:
        print(f"ℹ️ JSON endpoint not available or failed: {e}")


# Run the test
test_deployed_agent()
```

### Step 10: Service Management

#### Service Status

```{code-cell}
# Check service status
print(f"Service running: {deploy_manager.is_running}")
print(f"Service URL: {deploy_manager.service_url}")
```

#### Stopping the Service

```{code-cell}
async def stop_services(*_deploy_managers):
    """Stop deployed services"""
    async def _stop():
        for i, manager in enumerate(_deploy_managers):
            if manager.is_running:
                await manager.stop()
            print(f"🛑 Service {i} stopped")
    await _stop()

await stop_services(deploy_manager)
```

## Summary

This guide demonstrates two main scenarios for using the AgentScope Runtime framework:

### 🏃 Runner for Simple Agent Interaction

Build and test agents using the `Runner` class:

✅ Create and configure agents (LLMAgent, AgentScope, Agno, LangGraph)

✅ Set up Runner with context management

✅ Test agent responses through streaming

✅ Validate agent functionality before deployment

### 🚀 Agent Deployment as Production Service

Deploy agents as production-ready web services:

✅ Use `LocalDeployManager` for local deployment

✅ Expose agents as FastAPI web services

✅ Support both streaming and JSON responses

✅ Include health checks and service monitoring

✅ Handle multiple agent deployments
