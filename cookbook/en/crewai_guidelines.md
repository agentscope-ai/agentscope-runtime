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

# CrewAI Integration Guide

This document describes how to integrate and use the CrewAI framework within AgentScope Runtime to build collaborative autonomous agents that support multi-turn conversations, session memory, and streaming responses.

## 📦 Example Overview

The following example demonstrates how to use the CrewAI framework inside AgentScope Runtime:

- Uses the Qwen-Plus model from DashScope.
- Orchestrates a simple research task with one agent.
- Supports multi-turn conversation and session memory.
- Employs streaming output (SSE) to return responses in real-time.
- Implements session history storage via an in-memory service (InMemorySessionHistoryService).
- Can be accessed through an OpenAI-compatible API mode.

Here’s the core code:

```{code-cell}
# crewai_agent.py
# -*- coding: utf-8 -*-
import os
from agentscope_runtime.engine import AgentApp
from agentscope_runtime.engine.schemas.agent_schemas import AgentRequest
from agentscope_runtime.engine.services.session_history import InMemorySessionHistoryService
from agentscope_runtime.adapters.crewai.memory import create_crewai_session_history_memory

from crewai import Agent, LLM, Crew, Task

PORT = 8090

def run_app():
    """Start AgentApp and enable streaming output."""
    agent_app = AgentApp(
        app_name="Friday",
        app_description="A helpful assistant",
    )

    @agent_app.init
    async def init_func(self):
        # Initialize the session history service
        self.session_history_service = InMemorySessionHistoryService()


    @agent_app.query(framework="crewai")
    async def query_func(
        self,
        msgs,
        request: AgentRequest = None,
        **kwargs,
    ):
        """Handle agent queries using CrewAI."""

        # Extract user query from the input message
        user_question = msgs[0]["content"][0]["text"]

        # Initialize the LLM
        llm = LLM(
            model="qwen-plus",
            api_key=os.environ["DASHSCOPE_API_KEY"],
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            stream=True,
        )

        # Create session-specific memory for the crew
        memory = await create_crewai_session_history_memory(
            service_or_class=self.session_history_service,
            user_id=request.user_id,
            session_id=request.session_id,
        )

        # Define the Research Agent
        research_analyst = Agent(
            role="Expert Research Analyst",
            goal="Analyze the user's question and provide a clear, concise, and accurate answer.",
            backstory=(
                "You are an expert analyst at a world-renowned research institute. "
                "You are known for your ability to break down complex questions and "
                "deliver well-structured, easy-to-understand answers."
            ),
            llm=llm,
        )

        # Define the Research Task
        research_task = Task(
            description=f"Investigate the following user query: '{user_question}'",
            expected_output=(
                "A comprehensive yet easy-to-read answer that directly addresses the user's query. "
                "The answer should be well-formatted and factually correct."
            ),
            agent=research_analyst,
        )

        # Assemble the crew
        crew = Crew(
            agents=[research_analyst],
            tasks=[research_task],
            external_memory=memory,
            stream=True,
        )

        # Kick off the crew and stream the results
        async for chunk in await crew.akickoff():
            yield chunk


    agent_app.run(host="127.0.0.1", port=PORT)


if __name__ == "__main__":
    run_app()
```

## ⚙️ Prerequisites

```{note}
Before starting, make sure you have installed AgentScope Runtime and CrewAI, and configured the required API keys.
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
python crewai_agent.py
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
    input="What is CrewAI?",
)
print(resp.response["output"][0]["content"][0]["text"])
```

## 🔧 Customization

You can extend this example by:

1. **Changing the model**: Replace `LLM(model="qwen-plus", ...)` with another model.
2. **Adding system prompts**:
   - Modify the agent's role, goal, and backstory to change its persona and expertise.
   - Improve the task's description and expected_output for more specific results.
   - Add more Agent and Task instances to the Crew to build more complex, multi-agent workflows for collaboration and delegation.
3. **Use Different Tools**: Assign tools to your agents to allow them to interact with external services, such as searching the web or accessing databases.

## 📚 References

- [CrewAI Documentation](https://docs.crewai.com/)
- [AgentScope Runtime Documentation](https://runtime.agentscope.io/)
