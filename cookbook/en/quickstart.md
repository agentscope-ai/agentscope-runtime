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

from agentscope_runtime.engine import AgentApp
from agentscope_runtime.engine.agents.agentscope_agent import AgentScopeAgent
from agentscope_runtime.engine.deployers import LocalDeployManager
from agentscope.model import OpenAIChatModel
from agentscope.agent import ReActAgent


print("✅ Dependencies imported successfully")
```

### Step 2: Create Agent

We will take Agentscope as example.

```{code-cell}
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

```{note}
For utilizing other LLM and agent implementations from other framework, please refer to {ref}`Agno Agent <agno-agent>`, {ref}`AutoGen Agent <autogen-agent>`, and {ref}`LangGraph Agent <langgraph-agent>`.
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

### Step3: Create and Launch Agent App

Create an agent API server using agent and `AgentApp`:

```{code-cell}
app = AgentApp(agent=agent, endpoint_path="/process")

app.run(host="0.0.0.0", port=8090)
```

The server will start and listen on: `http://localhost:8090/process`.

### Step 4: Send Request to Agent

You can send JSON input to the API using `curl`:

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

You’ll see output streamed in **Server-Sent Events (SSE)** format:

```bash
data: {"sequence_number":0,"object":"response","status":"created", ... }
data: {"sequence_number":1,"object":"response","status":"in_progress", ... }
data: {"sequence_number":2,"object":"content","status":"in_progress","text":"The" }
data: {"sequence_number":3,"object":"content","status":"in_progress","text":" capital of France is Paris." }
data: {"sequence_number":4,"object":"message","status":"completed","text":"The capital of France is Paris." }
```

### Step 5: Deploy the Agent with Deployer

The AgentScope Runtime provides a powerful deployment system that allows you to deploy your agent to remote or local container. And we use `LocalDeployManager` as example:

```{code-cell}
async def main():
    await app.deploy(LocalDeployManager(host="0.0.0.0", port=8091))
```


This will run your agent API Server on the specified port, making it accessible for external requests. In addition to basic HTTP API access, you can interact with the agent through different protocols, such as A2A, Response API, Agent API, and others. Please refer {doc}`protocol` for details.

For example, user could query the deployment by OpenAI SDK with response api.

```python
from openai import OpenAI

client = OpenAI(base_url="http://0.0.0.0:8091/compatible-mode/v1")

response = client.responses.create(
  model="any_name",
  input="What is the weather in Beijing?"
)

print(response)
```