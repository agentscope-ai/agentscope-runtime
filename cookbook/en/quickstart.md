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

This tutorial walks through building a simple agent application in **AgentScope Runtime** and deploying it as a service.

## Prerequisites

### 🔧 Installation Requirements

Install AgentScope Runtime with the base dependencies:

```bash
pip install agentscope-runtime
```

### 🔑 API Key Configuration

Provide an API key for your selected LLM provider. This example uses DashScope's Qwen model, so we set the DashScope API key as an environment variable:

```bash
export DASHSCOPE_API_KEY="your_api_key_here"
```

## Step-by-Step Implementation

### Step 1: Import Dependencies

Start by importing every required module:

```{code-cell}
import os

from agentscope.agent import ReActAgent
from agentscope.model import DashScopeChatModel
from agentscope.formatter import DashScopeChatFormatter
from agentscope.tool import Toolkit, execute_python_code
from agentscope.pipeline import stream_printing_messages
from agentscope.memory import InMemoryMemory

from agentscope_runtime.engine import AgentApp
from agentscope_runtime.engine.schemas.agent_schemas import AgentRequest
from agentscope_runtime.engine.deployers import LocalDeployManager
from agentscope_runtime.engine.services.agent_state import (
    InMemoryStateService,
)

print("✅ Dependencies imported successfully")
```

### Step 2: Create the Agent App

`AgentApp` is the lifecycle and request hub of the agent application. All initialisation, query handling, and shutdown routines are registered on it:

```{code-cell}
agent_app = AgentApp(
    app_name="Friday",
    app_description="A helpful assistant",
)

print("✅ Agent App created successfully")
```

### Step 3: Register Lifecycle Hooks (Init & Shutdown)

Define what happens when the service starts (state/session services) and how resources are released during shutdown:

```{code-cell}
@agent_app.init
async def init_func(self):
    self.state_service = InMemoryStateService()
    await self.state_service.start()

@agent_app.shutdown
async def shutdown_func(self):
    await self.state_service.stop()
```

### Step 4: Define the AgentScope Query Logic

```{important}
⚠️ Important
The Agent setup shown here (model, tools, conversation memory, formatter, etc.) is provided as an example configuration only.
Please adapt and replace these components with your own implementations based on your requirements.
For details on available service types, adapter usage, and how to swap them out, see {doc}`service/service`.
```

When the agent endpoint is invoked, we:

- **Load session context** to keep different sessions isolated.
- **Build an Agent**: includes the model, tools (such as executing Python code), conversation memory modules, and formatter — for details, please refer to {doc}`service/service`.
- **Stream responses** via `stream_printing_messages`, yielding `(msg, last)` so clients receive output as it is generated.
- **Persist state** so the next request can resume.

```{code-cell}
@agent_app.query(framework="agentscope")
async def query_func(
    self,
    msgs,
    request: AgentRequest = None,
    **kwargs,
):
    session_id = request.session_id
    user_id = request.user_id

    state = await self.state_service.export_state(
        session_id=session_id,
        user_id=user_id,
    )

    toolkit = Toolkit()
    toolkit.register_tool_function(execute_python_code)

    agent = ReActAgent(
        name="Friday",
        model=DashScopeChatModel(
            "qwen-turbo",
            api_key=os.getenv("DASHSCOPE_API_KEY"),
            stream=True,
        ),
        sys_prompt="You're a helpful assistant named Friday.",
        toolkit=toolkit,
        memory=InMemoryMemory(),
        formatter=DashScopeChatFormatter(),
    )
    agent.set_console_output_enabled(enabled=False)

    if state:
        agent.load_state_dict(state)

    async for msg, last in stream_printing_messages(
        agents=[agent],
        coroutine_task=agent(msgs),
    ):
        yield msg, last

    state = agent.state_dict()

    await self.state_service.save_state(
        user_id=user_id,
        session_id=session_id,
        state=state,
    )
```

### Step 5: Run the Agent App

Start the Agent API server. After launch, it listens on `http://localhost:8090/process`:

```{code-cell}
# Start the service (listen on port 8090)
agent_app.run(host="0.0.0.0", port=8090)

# If you want to enable the built-in web chat interface at the same time, set web_ui=True
# agent_app.run(host="0.0.0.0", port=8090, web_ui=True)
```

### Step 6: Send a Request

Use `curl` to post JSON input and observe SSE output:

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

The response is streamed as **Server-Sent Events (SSE)**:

```bash
data: {"sequence_number":0,"object":"response","status":"created", ... }
data: {"sequence_number":1,"object":"response","status":"in_progress", ... }
data: {"sequence_number":2,"object":"message","status":"in_progress", ... }
data: {"sequence_number":3,"object":"content","status":"in_progress","text":"The" }
data: {"sequence_number":4,"object":"content","status":"in_progress","text":" capital of France is Paris." }
data: {"sequence_number":5,"object":"message","status":"completed","text":"The capital of France is Paris." }
data: {"sequence_number":6,"object":"response","status":"completed", ... }
```

### Step 7: Deploy with `DeployManager`

AgentScope Runtime ships with a powerful deployment system. The snippet below uses `LocalDeployManager`:

```{code-cell}
async def main():
    await agent_app.deploy(LocalDeployManager(host="0.0.0.0", port=8091))
```

This spins up the agent server on the specified port so external clients can call it. Beyond the basic HTTP API, you can also interact with the deployment via protocols such as A2A, Response API, and Agent API—see {doc}`protocol` for details.

Clients can even call the service through the OpenAI SDK:

```python
from openai import OpenAI

client = OpenAI(base_url="http://0.0.0.0:8091/compatible-mode/v1")

response = client.responses.create(
  model="any_name",
  input="杭州天气如何？"
)

print(response)
```

## Further Reading

The following chapters dive deeper into related topics:

- {doc}`tool`: add tools to your agent
- {doc}`deployment`: package and ship your agent as a service
- {doc}`use`: interact with deployed services
- {doc}`contribute`: contribution guide for this project
