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

# Agno Integration Guide

This guide explains how to integrate and use **Agno** within the **AgentScope Runtime** to build agents with multi-turn dialogue and streaming response capabilities.

## 📦 Example Overview

The following example demonstrates how to use [Agno](https://docs.agno.com/) inside AgentScope Runtime:

- Uses the Qwen-Plus model from DashScope
- Supports multi-turn conversation with session memory
- Provides **streaming output** (SSE) for real-time responses
- Stores conversation history in an in-memory database (`InMemoryDb`)
- Can be accessed via OpenAI Compatible mode

Here’s the core code:

```{code-cell}
# agno_agent.py
# -*- coding: utf-8 -*-
import os
from agno.agent import Agent
from agno.models.dashscope import DashScope
from agno.db.in_memory import InMemoryDb
from agentscope_runtime.engine import AgentApp
from agentscope_runtime.engine.schemas.agent_schemas import AgentRequest

PORT = 8090

def run_app():
    """Start AgentApp and enable streaming output"""
    agent_app = AgentApp(
        app_name="Friday",
        app_description="A helpful assistant",
    )

    @agent_app.init
    async def init_func(self):
        # Agno in-memory database, see https://docs.agno.com/reference/storage
        self.db = InMemoryDb()

    @agent_app.query(framework="agno")
    async def query_func(
        self,
        msgs,
        request: AgentRequest = None,
        **kwargs,
    ):
        session_id = request.session_id

        agent = Agent(
            name="Friday",
            instructions="You're a helpful assistant named Friday",
            model=DashScope(
                id="qwen-plus",
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                api_key=os.getenv("DASHSCOPE_API_KEY"),
            ),
            db=self.db,
            session_id=session_id,
            add_history_to_context=True,
        )

        # Stream the response
        async for event in agent.arun(
            msgs,
            stream=True,
            stream_events=True,
        ):
            yield event

    agent_app.run(host="127.0.0.1", port=PORT)

if __name__ == "__main__":
    run_app()
```

## ⚙️ Prerequisites

```{note}
Before starting, make sure you have installed AgentScope Runtime and Agno, and configured the required API keys.
```

1. **Install dependencies**:

   ```bash
   pip install "agentscope-runtime[ext]"
   ```

2. **Set environment variables** (DashScope provides the API key for Qwen models):

   ```bash
   export DASHSCOPE_API_KEY="your-dashscope-api-key"
   ```

## ▶️ Run the Example

Run the example:

```bash
python agno_agent.py
```

## 🌐 API Interaction

### 1. Ask the Agent (`/process`)

You can send an HTTP POST request to interact with the agent, with SSE streaming enabled:

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

You can extend this example by:

1. **Changing the model**: Replace `DashScope(id="qwen-plus", ...)` with another model.
2. **Adding system prompts**: Modify the `instructions` field for different personas.
3. **Switching the database backend**: Replace `InMemoryDb` with another storage implementation.

## 📚 References

- [Agno Documentation](https://docs.agno.com/reference)
- [AgentScope Runtime Documentation](https://runtime.agentscope.io/)