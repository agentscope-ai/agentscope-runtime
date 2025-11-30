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

# Tracing Method Introduction

The tracing module provides comprehensive tracing capabilities for monitoring and logging various events in the AgentScope runtime. This documentation covers the two main usage patterns: decorator-based tracing and context manager-based tracing.

## Overview

The tracing module consists of several key components:

+ **Tracer**: The main tracing class that manages event tracking
+ **TracerHandler**: Abstract base class for different logging handlers
+ **TraceType**: Enumeration of supported trace event types
+ **@trace decorator**: Convenient decorator for function-level tracing
+ **Context manager**: Manual tracing with fine-grained control

## Trace Types

The module supports various trace event types:

```{code-cell}
from agentscope_runtime.engine.tracing import TraceType

# Available trace types
print("LLM:", TraceType.LLM)
print("TOOL:", TraceType.TOOL)
print("AGENT_STEP:", TraceType.AGENT_STEP)
print("SEARCH:", TraceType.SEARCH)
print("IMAGE_GENERATION:", TraceType.IMAGE_GENERATION)
print("RAG:", TraceType.RAG)
print("INTENTION:", TraceType.INTENTION)
print("PLUGIN_CENTER:", TraceType.PLUGIN_CENTER)
```

## Usage Pattern 1: Decorator-Based Tracing

The `@trace` decorator provides a convenient way to trace any function execution automatically.

Additionally, the user could pass in any additional information to `**kwargs`for the record, and`trace`method could automatically get that info.

### Basic Decorator Usage

```{code-cell}
from agentscope_runtime.engine.tracing import trace, TraceType

@trace(TraceType.AGENT_STEP)
async def stream_query(user_id: str, request: dict, tools: list = None, **kwargs):
    """Example function showing decorator-based tracing."""
    # Your function logic here
    result = {"status": "success", "user_id": user_id}
    return result

# Usage
import asyncio
result = await stream_query("user123", {"query": "test"}, tools=[])
print("Result:", result)
```

Notice that for the method with a generator as the result, especially in the LLM generating case, the trace will only record the first and last generator result to avoid recording redundant logs.

## Usage Pattern 2: Context Manager-Based Tracing

To have more precise control, you can use a context manager. This method allows you to manually control when tracing starts and stops, as well as add custom logging during execution.

### Basic Context Manager Usage

```{code-cell}
from agentscope_runtime.engine.tracing import Tracer, TraceType
from agentscope_runtime.engine.tracing.local_logging_handler import LocalLogHandler

# Create tracer with handlers
tracer = Tracer(handlers=[LocalLogHandler(enable_console=True)])

# Using context manager for tracing
with tracer.event(
    event_type=TraceType.LLM,
    payload={"key": "value"},
) as event:
    # Log messages during execution
    tracer.log("msg1", **{"key1": "value1", "key2": {"key3": "value3"}})

    # Log through the event context
    event.on_log(
        "msg2",
        **{"step_suffix": "last_resp", "payload": {"key": "value"}},
    )

    # Your actual logic here
    result = "processing completed"
    print("Processing result:", result)
```

## Handler Types

Currently, we only provide a default local log tracer; more handlers will be supported, such as langfuse. The user could fulfill a custom handler based on their preference.

Meanwhile, the user could add multiple handlers at the same time in one trace.

### Multiple Handlers

```{code-cell}
from agentscope_runtime.engine.tracing import Tracer, TraceType
from agentscope_runtime.engine.tracing.base import BaseLogHandler
from agentscope_runtime.engine.tracing.local_logging_handler import LocalLogHandler

# Create tracer with multiple handlers
tracer = Tracer(handlers=[
    BaseLogHandler(),
    LocalLoggingHandler(enable_console=True)
])

with tracer.event(
    event_type=TraceType.SEARCH,
    payload={"query": "test query", "source": "database"},
) as event:
    tracer.log("Search started")
    # Simulate search operation
    search_results = ["result1", "result2", "result3"]
    event.on_end(payload={"results": search_results, "count": len(search_results)})
```

## Error Handling

The tracing system automatically handles errors and logs them appropriately:

```{code-cell}
from agentscope_runtime.engine.tracing import Tracer, TraceType
from agentscope_runtime.engine.tracing.local_logging_handler import LocalLogHandler

tracer = Tracer(handlers=[LocalLoggingHandler(enable_console=True)])

def function_with_error():
    """Function that raises an exception to demonstrate error handling."""
    with tracer.event(
        event_type=TraceType.TOOL,
        payload={"tool_name": "error_prone_tool"},
    ) as event:
        tracer.log("Starting tool execution")
        # Simulate an error
        raise ValueError("This is a simulated error")

# Execute and handle the error
try:
    function_with_error()
except ValueError as e:
    print(f"Caught error: {e}")
```

## Integration with AgentScope Runtime

The tracing module is designed to integrate smoothly with the AgentScope runtime. Here's how it is usually used in the runner:

```{code-cell}
from agentscope_runtime.engine.tracing import trace, TraceType

# Example from runner.py
@trace(TraceType.AGENT_STEP)
async def stream_query(
    self,
    user_id: str,
    request: dict,
    tools: list = None,
    **kwargs: Any,
):
    """Stream query method with automatic tracing."""
    # Agent step logic here
    response = {"user_id": user_id, "status": "processing"}
    return response

# Usage in agent context
async def example_agent_usage():
    """Example of how the traced method would be used."""
    result = await stream_query(
        user_id="user123",
        request={"query": "Hello, agent!"},
        tools=[]
    )
    return result

# Execute
result = await example_agent_usage()
print("Agent result:", result)
```

