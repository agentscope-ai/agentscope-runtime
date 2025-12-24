# LangGraph Integration Examples

This directory contains examples demonstrating how to integrate LangGraph with AgentScope Runtime to build sophisticated agent workflows.

## Overview

LangGraph is a library for building stateful, multi-actor applications with LLMs, used to create agent and multi-agent workflows. These examples show how to leverage LangGraph's powerful workflow capabilities within the AgentScope Runtime framework.

## Examples

### 1. Basic LLM Interaction (`run_langgraph_llm.py`)

A simple example that demonstrates basic LLM interaction using LangGraph within AgentScope Runtime:

- Uses Qwen-Plus model from DashScope
- Implements a basic state graph workflow with a single node
- Shows how to stream responses from the LLM
- Includes memory management for conversation history
- Demonstrates the use of `StateGraph` with `START` and `call_model` nodes

### 2. Advanced Agent with Tools (`run_langgraph_agent.py`)

A more complex example that demonstrates an agent with tool calling capabilities:

- Integrates custom tools defined in `my_tools.py`
- Implements both short-term (conversation) and long-term (persistent) memory
- Uses checkpointing to maintain state across sessions
- Provides API endpoints to inspect memory states
- Demonstrates tool calling and result handling
- Includes a custom weather tool for demonstration purposes
- Uses a custom `AgentState` extension with user_id and session_id fields
- Implements long-term memory storage for tool call results

### 3. Custom Tools (`my_tools.py`)

A collection of custom tools that can be used by LangGraph agents:

- File operations: Read and update plan files
- Text file viewing with range support
- Web search using Alibaba Cloud IQS API
- Memory management utilities

Key tools include:
- `read_plan_file(file_path)`: Reads the content of a plan file
- `update_plan_file(file_path, content, adjust_plan=False, adjustment_reason="")`: Updates or creates a plan file with content, with optional plan adjustment
- `iqs_generic_search(query, category=None, limit=5)`: Searches the web using Alibaba Cloud IQS API with support for category filtering
- `_view_text_file(file_path, ranges=None)`: Internal utility for reading text files with optional range support

## Prerequisites

1. **Install dependencies**:
   ```bash
   pip install agentscope-runtime[langgraph]
   ```

2. **Set environment variables**:
   ```bash
   # Required: DashScope API key for Qwen models
   export DASHSCOPE_API_KEY="your-dashscope-api-key"

   # Optional: Alibaba Cloud IQS API key for web search (used in my_tools.py)
   export IQS_API_KEY="your-iqs-api-key"
   ```

## Running the Examples

### Basic LLM Interaction

```bash
python examples/langgraph/run_langgraph_llm.py
```

### Advanced Agent with Tools

```bash
python examples/langgraph/run_langgraph_agent.py
```

After starting the server, you can interact with the agent through the query interface and inspect memory states through the provided API endpoints.

### Interacting with the Agent

Once the server is running, you can send queries to the agent using the `/query` endpoint:

```bash
curl -X POST http://localhost:8090/query \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "What is the weather like in Beijing?"}],
    "user_id": "user123",
    "session_id": "session456"
  }'
```

## Key Features Demonstrated

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
- File system operations
- Web search capabilities

## API Endpoints

When running the advanced agent example, the following API endpoints are available:

- `POST /query` - Send queries to the agent
- `GET /api/memory/short-term/{session_id}` - Get short-term memory for a session
- `GET /api/memory/short-term` - List all short-term memories
- `GET /api/memory/long-term/{user_id}` - Get long-term memory for a user

## Customization

You can customize these examples by:

1. **Adding new tools**: Extend `my_tools.py` with additional functions decorated with `@tool`
2. **Changing the LLM**: Modify the `ChatOpenAI` initialization to use different models
3. **Extending the workflow**: Add new nodes and edges to the state graph
4. **Customizing memory**: Implement different memory storage backends

## Related Documentation

- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [AgentScope Runtime Documentation](https://runtime.agentscope.io/)