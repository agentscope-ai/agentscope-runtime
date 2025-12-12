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

# LangGraph Integration Guide

This guide introduces how to integrate and use LangGraph with AgentScope Runtime to build complex agent workflows.

## 📦 Example Descriptions

### 1. Basic LLM Interaction

A simple example demonstrating basic LLM interaction using LangGraph within AgentScope Runtime:

- Uses Qwen-Plus model from DashScope
- Implements a basic state graph workflow with a single node
- Shows how to stream responses from the LLM
- Includes memory management for conversation history
- Demonstrates the use of `StateGraph` with `START` and `call_model` nodes

Here is the core code:

```{code-cell}
# -*- coding: utf-8 -*-
import os

from langchain.agents import AgentState
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import START, StateGraph

from agentscope_runtime.engine import AgentApp
from agentscope_runtime.engine.schemas.agent_schemas import AgentRequest

global_short_term_memory = None

# Create the AgentApp instance
agent_app = AgentApp(
    app_name="LangGraphAgent",
    app_description="A LangGraph-based research assistant",
)

# Initialize services as instance variables
@agent_app.init
async def init_func(self):
    global global_short_term_memory
    self.short_term_mem = InMemorySaver()
    global_short_term_memory = self.short_term_mem

# Query endpoint for LangGraph integration
@agent_app.query(framework="langgraph")
async def query_func(
    self,
    msgs,
    request: AgentRequest = None,
    **kwargs,
):
    # Extract session information
    session_id = request.session_id
    user_id = request.user_id
    print(f"Received query from user {user_id} with session {session_id}")

    # Initialize LLM
    llm = ChatOpenAI(
        model="qwen-plus",
        api_key=os.environ.get("DASHSCOPE_API_KEY"),
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    )

    def call_model(state: AgentState):
        """Call the LLM to generate a response"""
        model_response = llm.invoke(state["messages"])
        return {"messages": model_response}

    # Define workflow
    workflow = StateGraph(AgentState)
    workflow.add_node("call_model", call_model)
    workflow.add_edge(START, "call_model")
    graph = workflow.compile(name="langgraph_agent")

    # Stream response
    async for chunk, meta_data in graph.astream(
        input={"messages": msgs},
        stream_mode="messages",
        config={"configurable": {"thread_id": session_id}},
    ):
        is_last_chunk = (
            True if getattr(chunk, "chunk_position", "") == "last" else False
        )
        yield chunk, is_last_chunk
if __name__ == "__main__":
  agent_app.run(host="127.0.0.1", port=8090)
```

## ▶️ Running Examples

```{tip}
Make sure you have set all the required environment variables in the Prerequisites section before running these examples.
```

After starting the server, you can interact with the agent through the query interface and inspect memory states through the provided API endpoints.

### Interacting with the Agent

Once the server is running, you can send queries to the agent using the `/query` endpoint:

```bash
curl -N \
  -X POST "http://localhost:8090/process" \
  -H "Content-Type: application/json" \
  -d '{
    "input": [
      {
        "role": "user",
        "content": [
          { "type": "text", "text": "what is the capital of France?" }
        ]
      }
    ],
    "session_id": "sessionid123",
    "user_id": "userid123"
  }'
```

## ✨ Key Features Demonstration

### LangGraph Integration
- State management with `AgentState`
- Workflow definition using `StateGraph`
- Checkpointing for persistent state
- Streaming responses for real-time interaction

### Memory Management
- Short-term memory for conversation history
- Long-term memory for persistent storage
- API endpoints to inspect memory states
- Session-based memory isolation

### Tool Integration
- Custom tool definition using LangChain's `@tool` decorator
- Tool calling and result handling

## 🌐 API Endpoints

```{important}
The following API endpoints are only available when running the advanced agent example.
```

When running the advanced agent example, the following API endpoints are available:

- `POST /process` - Send queries to the agent
- `GET /api/memory/short-term/{session_id}` - Get short-term memory for a session
- `GET /api/memory/short-term` - List all short-term memories
- `GET /api/memory/long-term/{user_id}` - Get long-term memory for a user

## 🔧 Customization

You can customize these examples by:

1. **Adding new tools**: Define custom tools using the `@tool` decorator
2. **Changing the LLM**: Modify the `ChatOpenAI` initialization to use different models
3. **Extending the workflow**: Add new nodes and edges to the state graph
4. **Customizing memory**: Implement different memory storage backends

## 📚 Related Documentation

- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [AgentScope Runtime Documentation](https://runtime.agentscope.io/)