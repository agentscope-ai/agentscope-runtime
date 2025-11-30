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

# 执行轨迹追踪

追踪模块为监控和记录AgentScope Runtime中各种事件提供全面的追踪功能。本文档涵盖两种主要使用模式：基于装饰器的追踪和基于上下文管理器的追踪。

## 概述

追踪模块包含几个关键组件：

+ **Tracer**：管理事件追踪的主要追踪类
+ **TracerHandler**：不同日志处理程序的抽象基类
+ **TraceType**：支持的追踪事件类型枚举
+ **@trace装饰器**：便于函数级追踪的装饰器
+ **上下文管理器**：具有细粒度控制的手动追踪

## 追踪类型

该模块支持各种追踪事件类型：

```{code-cell}
from agentscope_runtime.engine.tracing import TraceType

# 可用的追踪类型
print("LLM:", TraceType.LLM)
print("TOOL:", TraceType.TOOL)
print("AGENT_STEP:", TraceType.AGENT_STEP)
print("SEARCH:", TraceType.SEARCH)
print("IMAGE_GENERATION:", TraceType.IMAGE_GENERATION)
print("RAG:", TraceType.RAG)
print("INTENTION:", TraceType.INTENTION)
print("PLUGIN_CENTER:", TraceType.PLUGIN_CENTER)
```

## 使用模式1：基于装饰器的追踪

`@trace`装饰器提供自动追踪任何函数执行的便利方式。

此外，用户可以向`**kwargs`传递任何额外信息进行记录，`trace`方法可以自动获取这些信息。

### 基本装饰器用法

```{code-cell}
from agentscope_runtime.engine.tracing import trace, TraceType

@trace(TraceType.AGENT_STEP)
async def stream_query(user_id: str, request: dict, tools: list = None, **kwargs):
    """展示基于装饰器追踪的示例函数。"""
    # 您的函数逻辑在这里
    result = {"status": "success", "user_id": user_id}
    return result

# 使用方法
import asyncio
result = await stream_query("user123", {"query": "test"}, tools=[])
print("Result:", result)
```

请注意，对于以生成器为结果的方法，特别是在LLM生成情况下，追踪只会记录第一个和最后一个生成器结果，以避免记录冗余日志。

## 使用模式2：基于上下文管理器的追踪

为了更精细的控制，您可以使用上下文管理器方法。允许你手动控制追踪何时开始和结束，并在执行期间添加自定义日志记录。

### 基本上下文管理器用法

```{code-cell}
from agentscope_runtime.engine.tracing import Tracer, TraceType
from agentscope_runtime.engine.tracing.local_logging_handler import LocalLogHandler

# 创建带有处理程序的追踪器
tracer = Tracer(handlers=[LocalLogHandler(enable_console=True)])

# 使用上下文管理器进行追踪
with tracer.event(
    event_type=TraceType.LLM,
    payload={"key": "value"},
) as event:
    # 在执行期间记录消息
    tracer.log("msg1", **{"key1": "value1", "key2": {"key3": "value3"}})

    # 通过事件上下文,任何位置记录额外信息
    event.on_log(
        "msg2",
        **{"step_suffix": "last_resp", "payload": {"key": "value"}},
    )

    # 您的实际逻辑在这里
    result = "processing completed"
    print("Processing result:", result)
```

## 处理程序类型

目前，我们只提供默认的本地日志追踪器，将来会支持更多处理程序，如langfuse。用户可以根据自己的偏好实现自定义处理程序。

同时，用户可以在一个追踪中同时添加多个处理程序。

### 多处理程序

```{code-cell}
from agentscope_runtime.engine.tracing import Tracer, TraceType
from agentscope_runtime.engine.tracing.base import BaseLogHandler
from agentscope_runtime.engine.tracing.local_logging_handler import LocalLogHandler

# 创建带有多个处理程序的追踪器
tracer = Tracer(handlers=[
    BaseLogHandler(),
    LocalLogHandler(enable_console=True)
])

with tracer.event(
    event_type=TraceType.SEARCH,
    payload={"query": "test query", "source": "database"},
) as event:
    tracer.log("Search started")
    # 模拟搜索操作
    search_results = ["result1", "result2", "result3"]
    #对于需要额外记录信息的情况
    event.on_log(payload={"results": search_results, "count": len(search_results)})
```

## 错误处理

追踪系统自动处理错误并适当地记录它们：

```{code-cell}
from agentscope_runtime.engine.tracing import Tracer, TraceType
from agentscope_runtime.engine.tracing.local_logging_handler import LocalLogHandler

tracer = Tracer(handlers=[LocalLogHandler(enable_console=True)])

def function_with_error():
    """引发异常以演示错误处理的函数。"""
    with tracer.event(
        event_type=TraceType.TOOL,
        payload={"tool_name": "error_prone_tool"},
    ) as event:
        # 模拟错误
        raise ValueError("This is a simulated error")

# 执行并处理错误
try:
    function_with_error()
except ValueError as e:
    print(f"Caught error: {e}")
```

## 与AgentScope Runtime的集成

追踪模块旨在与AgentScope Runtime无缝集成。以下是它在运行器中的典型使用方式：

```{code-cell}
from agentscope_runtime.engine.tracing import trace, TraceType

# 来自runner.py的示例
@trace(TraceType.AGENT_STEP)
async def stream_query(
    self,
    user_id: str,
    request: dict,
    tools: list = None,
    **kwargs: Any,
):
    """带有自动追踪的流查询方法。"""
    # 智能体步骤逻辑在这里
    response = {"user_id": user_id, "status": "processing"}
    return response

# 在智能体上下文中的用法
async def example_agent_usage():
    """演示如何使用被追踪方法的示例。"""
    result = await stream_query(
        user_id="user123",
        request={"query": "Hello, agent!"},
        tools=[]
    )
    return result

# 执行
result = await example_agent_usage()
print("Agent result:", result)
```
