---
jupytext:
  formats: md:myst
  text_representation:
    extension: .md
    format_name: myst
    format_version: 0.13
    jupytext_version: 1.11.5
kernelspec:
  display_name: Python 3.10
  language: python
  name: python3
---

# Reference: Full Deployment Example

This tutorial shows how to build and deploy a *Reason + Act (ReAct)* agent with AgentScope Runtime and the [**AgentScope framework**](https://github.com/agentscope-ai/agentscope).

```{note}
The ReAct paradigm interleaves reasoning traces with task-specific actions, which is especially effective for tool-use scenarios. Combining AgentScope's `ReActAgent` with AgentScope Runtime gives you both smart decision-making and safe tool execution.
```

## Prerequisites

### Install Dependencies

```bash
pip install agentscope-runtime
```

### Sandbox

```{note}
Make sure the browser sandbox environment is ready; refer to {doc}`sandbox/sandbox` for details.
```

Pull the browser sandbox image:

```bash
docker pull agentscope-registry.ap-southeast-1.cr.aliyuncs.com/agentscope/runtime-sandbox-browser:latest && docker tag agentscope-registry.ap-southeast-1.cr.aliyuncs.com/agentscope/runtime-sandbox-browser:latest agentscope/runtime-sandbox-browser:latest
```

### API Keys

Provide an API key for your LLM provider. This example uses DashScope (Qwen), but you can adapt it to any vendor:

```bash
export DASHSCOPE_API_KEY="your_api_key_here"
```

## Step-by-Step Implementation

### Step 1: Import Dependencies

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
from agentscope_runtime.engine.services.agent_state import InMemoryStateService
from agentscope_runtime.engine.services.sandbox import SandboxService
from agentscope_runtime.sandbox import BrowserSandbox
```

### Step 2: Prepare Browser Sandbox Tools

Like `tests/sandbox/test_sandbox.py`, you can validate the browser sandbox via a context manager:

```{code-cell}
with BrowserSandbox() as box:
    print(box.list_tools())
    print(box.browser_navigate("https://www.example.com/"))
    print(box.browser_snapshot())
```

If the service needs to reuse sandbox instances over time, manage them with `SandboxService` (see `tests/sandbox/test_sandbox_service.py`):

```{code-cell}
import asyncio

async def bootstrap_browser_sandbox():
    sandbox_service = SandboxService()
    await sandbox_service.start()

    session_id = "demo_session"
    user_id = "demo_user"

    sandboxes = sandbox_service.connect(
        session_id=session_id,
        user_id=user_id,
        sandbox_types=["browser"],
    )
    browser_box = sandboxes[0]
    browser_box.browser_navigate("https://www.example.com/")
    browser_box.browser_snapshot()

    await sandbox_service.stop()

asyncio.run(bootstrap_browser_sandbox())
```

Here, `sandbox_types=["browser"]` matches the test suite, so a single browser sandbox instance is reused for the same `session_id` / `user_id` pair.

### Step 3: Build the AgentApp

```{important}
⚠️ Important
The Agent setup shown here (model, tools, conversation memory, formatter, etc.) is provided as an example configuration only.
Please adapt and replace these components with your own implementations based on your requirements.
For details on available service types, adapter usage, and how to swap them out, see {doc}`service/service`.
```

The logic mirrors the `run_app()` test: initialize services, wire up session memory, and stream responses.

```{code-cell}
PORT = 8090

agent_app = AgentApp(
    app_name="Friday",
    app_description="A helpful assistant",
)


@agent_app.init
async def init_func(self):
    self.state_service = InMemoryStateService()
    self.sandbox_service = SandboxService()

    await self.state_service.start()
    await self.sandbox_service.start()


@agent_app.shutdown
async def shutdown_func(self):
    await self.state_service.stop()
    await self.sandbox_service.stop()


@agent_app.query(framework="agentscope")
async def query_func(self, msgs, request: AgentRequest = None, **kwargs):
    session_id = request.session_id
    user_id = request.user_id

    state = await self.state_service.export_state(
        session_id=session_id,
        user_id=user_id,
    )

    sandboxes = self.sandbox_service.connect(
        session_id=session_id,
        user_id=user_id,
        sandbox_types=["browser"],
    )
    browser_box = sandboxes[0]

    toolkit = Toolkit()
    for tool in (
        browser_box.browser_navigate,
        browser_box.browser_snapshot,
        browser_box.browser_take_screenshot,
        browser_box.browser_click,
        browser_box.browser_type,
    ):
        toolkit.register_tool_function(tool)
    toolkit.register_tool_function(execute_python_code)

    agent = ReActAgent(
        name="Friday",
        model=DashScopeChatModel(
            "qwen-turbo",
            api_key=os.getenv("DASHSCOPE_API_KEY"),
            enable_thinking=True,
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

    await self.state_service.save_state(
        user_id=user_id,
        session_id=session_id,
        state=agent.state_dict(),
    )
```

The `query_func` streams SSE responses and persists the latest agent state, enabling multi-turn memory. Because `SandboxService` is scoped to `session_id` / `user_id`, the same browser sandbox is reused until the session ends.

### Step 4: Launch the Service

```{code-cell}
if __name__ == "__main__":
    agent_app.run(host="127.0.0.1", port=PORT)
```

Once running, call `http://127.0.0.1:8090/process` for streaming answers.

### Step 5: Test SSE Output

```bash
curl -N \
  -X POST "http://127.0.0.1:8090/process" \
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

You should see multiple `data: {...}` SSE events ending with `data: [DONE]`. A response containing “Paris” indicates success.

### Step 6: Verify Multi-turn Memory

Reuse the same `session_id` to test `AgentScopeSessionHistoryMemory`: send “My name is Alice.” first, then ask “What is my name?”—the reply should mention “Alice”.

### Step 7: OpenAI-Compatible Mode

AgentApp exposes a `compatible-mode/v1` path so you can test with the official `openai` SDK:

```{code-cell}
from openai import OpenAI

client = OpenAI(base_url="http://127.0.0.1:8090/compatible-mode/v1")
resp = client.responses.create(
    model="any_name",
    input="Who are you?",
)

print(resp.response["output"][0]["content"][0]["text"])
```

A successful result should look like “I'm Friday ...”.

## Summary

Following these steps, you now have a ReAct agent with streaming responses, session memory, browser sandbox tooling, and an OpenAI-compatible endpoint. To deploy remotely or extend the toolset, swap out the model, state services, or registered tools as needed.
