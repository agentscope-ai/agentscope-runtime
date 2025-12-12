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
Recommend to use python 3.11 or above for stream mode, refer to [LangGraph](https://docs.langchain.com/oss/python/langgraph/streaming#llm-tokens) for more details.

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
import uuid

from langchain.agents import AgentState, create_agent
from langchain.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.base import BaseStore
from langgraph.store.memory import InMemoryStore

from agentscope_runtime.engine import AgentApp
from agentscope_runtime.engine.schemas.agent_schemas import AgentRequest

global_short_term_memory: BaseCheckpointSaver = None
global_long_term_memory: BaseStore = None


@tool
def get_weather(location: str, date: str) -> str:
    """Get the weather for a location and date."""
    print(f"Getting weather for {location} on {date}...")
    return f"The weather in {location} is sunny with a temperature of 25°C."


# Create the AgentApp instance
agent_app = AgentApp(
    app_name="LangGraphAgent",
    app_description="A LangGraph-based research assistant",
)


class CustomAgentState(AgentState):
    user_id: str
    session_id: dict


# Initialize services as instance variables
@agent_app.init
async def init_func(self):
    global global_short_term_memory
    global global_long_term_memory
    self.short_term_mem = InMemorySaver()
    self.long_term_mem = InMemoryStore()
    global_short_term_memory = self.short_term_mem
    global_long_term_memory = self.long_term_mem


# Shutdown services, in this case,
# we don't use any resources, so we don't need to do anything here
@agent_app.shutdown
async def shutdown_func(self):
    pass


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
    tools = [get_weather]
    # Choose the LLM that will drive the agent
    llm = ChatOpenAI(
        model="qwen-plus",
        api_key=os.environ.get("DASHSCOPE_API_KEY"),
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    )
    namespace_for_long_term_memory = (user_id, "memories")

    prompt = """You are a proactive research assistant. """

    agent = create_agent(
        llm,
        tools,
        system_prompt=prompt,
        checkpointer=self.short_term_mem,
        store=self.long_term_mem,
        state_schema=CustomAgentState,
        name="LangGraphAgent",
    )
    async for chunk, meta_data in agent.astream(
        input={"messages": msgs, "session_id": session_id, "user_id": user_id},
        stream_mode="messages",
        config={"configurable": {"thread_id": session_id}},
    ):
        is_last_chunk = (
            True if getattr(chunk, "chunk_position", "") == "last" else False
        )
        if meta_data["langgraph_node"] == "tools":
            memory_id = str(uuid.uuid4())
            memory = {"lastest_tool_call": chunk.name}
            global_long_term_memory.put(
                namespace_for_long_term_memory,
                memory_id,
                memory,
            )
        yield chunk, is_last_chunk


@agent_app.endpoint("/api/memory/short-term/{session_id}", methods=["GET"])
async def get_short_term_memory(session_id: str):
    if global_short_term_memory is None:
        return {"error": "Short-term memory not initialized yet."}

    config = {"configurable": {"thread_id": session_id}}

    value = await global_short_term_memory.aget_tuple(config)

    if value is None:
        return {"error": "No memory found for session_id"}

    return {
        "session_id": session_id,
        "messages": value.checkpoint["channel_values"]["messages"],
        "metadata": value.metadata,
    }


@agent_app.endpoint("/api/memory/short-term", methods=["GET"])
async def list_short_term_memory():
    if global_short_term_memory is None:
        return {"error": "Short-term memory not initialized yet."}

    result = []
    short_mems = list(global_short_term_memory.list(None))
    for short_mem in short_mems:
        ch_vals = short_mem.checkpoint["channel_values"]
        # Ignore the __pregel_tasks field, which is not serializable
        safe_dict = {
            key: value
            for key, value in ch_vals.items()
            if key != "__pregel_tasks"
        }
        result.append(safe_dict)
    return result


@agent_app.endpoint("/api/memory/long-term/{user_id}", methods=["GET"])
async def get_long_term_memory(user_id: str):
    if global_short_term_memory is None:
        return {"error": "Short-term memory not initialized yet."}
    namespace_for_long_term_memory = (user_id, "memories")
    long_term_mem = global_long_term_memory.search(
        namespace_for_long_term_memory,
    )

    def serialize_search_item(item):
        return {
            "namespace": item.namespace,
            "key": item.key,
            "value": item.value,
            "created_at": item.created_at,
            "updated_at": item.updated_at,
            "score": item.score,
        }

    serialized = [serialize_search_item(item) for item in long_term_mem]
    return serialized


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