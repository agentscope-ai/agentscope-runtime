# Feature Overview
The Tracing module is used for tracing components and arbitrary functions, including two parts: Log and Report. The Log part outputs in Dashscope Log format, while the Report part uses the OpenTelemetry SDK to report tracing information.

# Usage
## Logging
1. Configure environment variables (enabled by default)
```shell
export TRACE_ENABLE_LOG=true
```
2. Add decorator to any function, example:
```python
from agentscope_runtime.engine.tracing import trace, TraceType

@trace(trace_type=TraceType.LLM, trace_name="llm_func")
def llm_func():
    pass
```
Output:
```text
{"time": "2025-08-13 11:23:41.808", "step": "llm_func_start", "model": "", "user_id": "", "code": "", "message": "", "task_id": "", "request_id": "", "context": {}, "interval": {"type": "llm_func_start", "cost": 0}, "ds_service_id": "test_id", "ds_service_name": "test_name"}
{"time": "2025-08-13 11:23:41.808", "step": "llm_func_end", "model": "", "user_id": "", "code": "", "message": "", "task_id": "", "request_id": "", "context": {}, "interval": {"type": "llm_func_end", "cost": "0.000"}, "ds_service_id": "test_id", "ds_service_name": "test_name"}
```

3. Custom logging (prerequisite: **function contains kwargs parameter**)
```python
from agentscope_runtime.engine.tracing import trace, TraceType

@trace(trace_type=TraceType.LLM, trace_name="llm_func")
def llm_func(**kwargs):
    trace_event = kwargs.pop("trace_event", None)
    if trace_event:
        # Custom string message
        trace_event.on_log("hello")

        # Formatted step message
        trace_event.on_log(
            "",
            **{
                "step_suffix": "mid_result",
                "payload": {
                    "output": "hello",
                },
            },
        )
```
Output:
```text
{"time": "2025-08-13 11:27:14.727", "step": "llm_func_start", "model": "", "user_id": "", "code": "", "message": "", "task_id": "", "request_id": "", "context": {}, "interval": {"type": "llm_func_start", "cost": 0}, "ds_service_id": "test_id", "ds_service_name": "test_name"}
{"time": "2025-08-13 11:27:14.728", "step": "", "model": "", "user_id": "", "code": "", "message": "hello", "task_id": "", "request_id": "", "context": {}, "interval": {"type": "", "cost": "0"}, "ds_service_id": "test_id", "ds_service_name": "test_name"}
{"time": "2025-08-13 11:27:14.728", "step": "llm_func_mid_result", "model": "", "user_id": "", "code": "", "message": "", "task_id": "", "request_id": "", "context": {"output": "hello"}, "interval": {"type": "llm_func_mid_result", "cost": "0.000"}, "ds_service_id": "test_id", "ds_service_name": "test_name"}
{"time": "2025-08-13 11:27:14.728", "step": "llm_func_end", "model": "", "user_id": "", "code": "", "message": "", "task_id": "", "request_id": "", "context": {}, "interval": {"type": "llm_func_end", "cost": "0.000"}, "ds_service_id": "test_id", "ds_service_name": "test_name"}
```
## Reporting
1. Configure environment variables (disabled by default)
```shell
export TRACE_ENABLE_LOG=false
export TRACE_ENABLE_REPORT=true
export TRACE_AUTHENTICATION={YOUR_AUTHENTICATION}
export TRACE_ENDPOINT={YOUR_ENDPOINT}
```
2. Add decorator to non-streaming functions, example:

```python
from agentscope_runtime.engine.tracing import trace, TraceType

@trace(trace_type=TraceType.LLM,
       trace_name="llm_func")
def llm_func(args: str):
    return args + "hello"
```


3. Add decorator to streaming functions, example:
```python
from agentscope_runtime.engine.tracing import trace, TraceType
from agentscope_runtime.engine.tracing.message_util import (
    get_finish_reason,
    merge_incremental_chunk,
)

@trace(trace_type=TraceType.LLM,
       trace_name="llm_func",
       get_finish_reason_func=get_finish_reason,
       merge_output_func=merge_incremental_chunk)
def llm_func(args: str):
    for i in range(10):
        yield i
```
Where get_finish_reason and merge_incremental_chunk are custom processing functions, optional, defaults to get_finish_reason and merge_incremental_chunk in message_util.py.

get_finish_reason is a custom function to get finish_reason, used to determine if streaming output has ended. Example:
```python
from openai.types.chat import ChatCompletionChunk
from typing import List, Optional

def get_finish_reason(response: ChatCompletionChunk) -> Optional[str]:
    finish_reason = None
    if hasattr(response, 'choices') and len(response.choices) > 0:
        if response.choices[0].finish_reason:
            finish_reason = response.choices[0].finish_reason

    return finish_reason
```

merge_output is a custom function to merge output, used to construct the final output information. Example:
```python
from openai.types.chat import ChatCompletionChunk
from typing import List, Optional

def merge_incremental_chunk(
    responses: List[ChatCompletionChunk],
) -> Optional[ChatCompletionChunk]:
    # get usage or finish reason
    merged = ChatCompletionChunk(**responses[-1].__dict__)

    # if the responses has usage info, then merge the finish reason chunk to usage chunk
    if not merged.choices and len(responses) > 1:
        merged.choices = responses[-2].choices

    for resp in reversed(responses[:-1]):
        for i, j in zip(merged.choices, resp.choices):
            if isinstance(i.delta.content, str) and isinstance(
                j.delta.content,
                str,
            ):
                i.delta.content = j.delta.content + i.delta.content
        if merged.usage and resp.usage:
            merged.usage.total_tokens += resp.usage.total_tokens

    return merged
```



4. Setting request_id and common attributes

request_id is used to bind the context of different requests. common attributes are public span attributes, all spans under this request will have these attributes.

**Automatic request_id setting**: When the user does not manually call `TracingUtil.set_request_id` at the beginning of request processing, the system will automatically generate and set a unique request_id in the root span.

**Manual setting**: Set request_id and common attributes in functions **not decorated with @trace**, for example, set immediately after request information is parsed. Example:

```python
from agentscope_runtime.engine.tracing import TracingUtil

common_attributes = {
    "gen_ai.user.id": "user_id",
    "bailian.app.id": "app_id",
    "bailian.app.owner_id": "app_id",
    "bailian.app.env": "pre",
    "bailian.app.workspace": "workspace"
}
TracingUtil.set_request_id("request_id")
TracingUtil.set_common_attributes(common_attributes)
```
5. Custom reporting (prerequisite: **function contains kwargs parameter**)
```python
import json
from agentscope_runtime.engine.tracing import trace, TraceType

@trace(trace_type=TraceType.LLM, trace_name="llm_func")
def llm_func(**kwargs):
    trace_event = kwargs.pop("trace_event", None)
    if trace_event:
        # Set string attribute
        trace_event.set_attribute("key", "value")
        # Set dict attribute
        trace_event.set_attribute("func_7.key", json.dumps({'key0': 'value0', 'key1': 'value1'}))
```
