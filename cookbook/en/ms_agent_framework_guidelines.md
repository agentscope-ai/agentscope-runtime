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

# Microsoft Agent Framework Integration Guide

This document describes how to integrate and use the **Microsoft Agent Framework** within **AgentScope Runtime** to build agents that support multi-turn conversations, conversation memory, and streaming responses.

## 📦 Example Overview

The following example demonstrates how to use the [Microsoft Agent Framework](https://learn.microsoft.com/en-us/agent-framework/) inside AgentScope Runtime:

- Uses the Qwen-Plus model from DashScope
- Supports multi-turn conversation and session memory
- Employs **streaming output** (SSE) to return responses in real-time
- Implements session history storage via an in-memory database (`InMemoryDb`)
- Can be accessed through an OpenAI-compatible API mode

Here’s the core code:

```{code-cell}
# ms_agent.py
# -*- coding: utf-8 -*-
import os
from agent_framework.openai import OpenAIChatClient

from agentscope_runtime.engine import AgentApp
from agentscope_runtime.engine.schemas.agent_schemas import AgentRequest
from agentscope_runtime.engine.services.agent_state import InMemoryStateService

PORT = 8090


def run_app():
    """Start AgentApp and enable streaming output."""
    agent_app = AgentApp(
        app_name="Friday",
        app_description="A helpful assistant",
    )

    @agent_app.init
    async def init_func(self):
        self.state_service = InMemoryStateService()
        await self.state_service.start()

    @agent_app.shutdown
    async def shutdown_func(self):
        await self.state_service.stop()

    @agent_app.query(framework="agno")
    async def query_func(
        self,
        msgs,
        request: AgentRequest = None,
        **kwargs,
    ):
        """Handle agent queries."""
        session_id = request.session_id
        user_id = request.user_id

        # Export historical context
        thread = await self.state_service.export_state(
            session_id=session_id,
            user_id=user_id,
        )

        # Create agent
        agent = OpenAIChatClient(
            model_id="qwen-plus",
            api_key=os.environ["DASHSCOPE_API_KEY"],
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        ).create_agent(
            instructions="You're a helpful assistant named Friday",
            name="Friday",
        )

        # Restore or create conversation thread
        if thread:
            thread = await agent.deserialize_thread(thread)
        else:
            thread = agent.get_new_thread()

        # Streaming responses
        async for event in agent.run_stream(
            msgs,
            thread=thread,
        ):
            yield event

        # Save session state
        serialized_thread = await thread.serialize()
        await self.state_service.save_state(
            user_id=user_id,
            session_id=session_id,
            state=serialized_thread,
        )

    agent_app.run(host="127.0.0.1", port=PORT)


if __name__ == "__main__":
    run_app()
```

## ⚙️ Prerequisites

```{note}
Before starting, make sure you have installed AgentScope Runtime and Microsoft Agent Framework, and configured the required API keys.
```

1. **Install dependencies**:

   ```bash
   pip install "agentscope-runtime[ext]"
   ```

2. **Set environment variables** (DashScope provides the Qwen model API Key):

   ```bash
   export DASHSCOPE_API_KEY="your-dashscope-api-key"
   ```

## ▶️ Run the Example

To run the example:

```
python ms_agent.py
```

## 🌐 API Interaction

### 1. Ask the Agent (`/process`)

You can send HTTP POST requests to interact with the agent, with support for SSE streaming responses:

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
    ],
    "session_id": "session_1"
  }'
```

### 2. OpenAI-Compatible Mode

This example also supports the **OpenAI Compatible API**:

```python
from openai import OpenAI

client = OpenAI(base_url="http://127.0.0.1:8090/compatible-mode/v1")
resp = client.responses.create(
    model="any_model",
    input="Who are you?",
)
print(resp.response["output"][0]["content"][0]["text"])
```

## 🔧 Customization

You can extend the example in the following ways:

1. **Change the model** — Replace the `model_id` in `OpenAIChatClient` with another model, or use a client from another model provider.
2. **Add system prompts** — Modify the `instructions` field to create a different persona for the agent.

## 📚 相关文档

* [Microsoft Agent Framework Documentation](https://learn.microsoft.com/en-us/agent-framework/overview/agent-framework-overview)

- [AgentScope Runtime Documentation](https://runtime.agentscope.io/)