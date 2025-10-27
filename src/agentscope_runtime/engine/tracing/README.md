# 功能简介
Tracing模块用于组件和任意函数的链路跟踪，包含Log和Report两部分，其中Log按照Dashscope Log格式输出，Report使用 opentelemetry sdk上报跟踪信息。

# 使用方法
## 日志打印
1. 配置环境变量（默认开启）
```shell
export TRACE_ENABLE_LOG=true
```
2. 在任意函数上面添加注解，示例如下：
```python
from agentscope_bricks.utils.tracing_utils import trace, TraceType

@trace(trace_type=TraceType.LLM, trace_name="llm_func")
def llm_func():
    pass
```
输出如下：
```text
{"time": "2025-08-13 11:23:41.808", "step": "llm_func_start", "model": "", "user_id": "", "code": "", "message": "", "task_id": "", "request_id": "", "context": {}, "interval": {"type": "llm_func_start", "cost": 0}, "ds_service_id": "test_id", "ds_service_name": "test_name"}
{"time": "2025-08-13 11:23:41.808", "step": "llm_func_end", "model": "", "user_id": "", "code": "", "message": "", "task_id": "", "request_id": "", "context": {}, "interval": {"type": "llm_func_end", "cost": "0.000"}, "ds_service_id": "test_id", "ds_service_name": "test_name"}
```

3. 自定义日志打印(前提条件：**函数包含 kwargs 参数**)
```python
from agentscope_bricks.utils.tracing_utils import trace, TraceType

@trace(trace_type=TraceType.LLM, trace_name="llm_func")
def llm_func(**kwargs):
    trace_event = kwargs.pop("trace_event", None)
    if trace_event:
        # 自定义str类型消息
        trace_event.on_log("hello")

        # 格式化step类型消息
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
输出如下：
```text
{"time": "2025-08-13 11:27:14.727", "step": "llm_func_start", "model": "", "user_id": "", "code": "", "message": "", "task_id": "", "request_id": "", "context": {}, "interval": {"type": "llm_func_start", "cost": 0}, "ds_service_id": "test_id", "ds_service_name": "test_name"}
{"time": "2025-08-13 11:27:14.728", "step": "", "model": "", "user_id": "", "code": "", "message": "hello", "task_id": "", "request_id": "", "context": {}, "interval": {"type": "", "cost": "0"}, "ds_service_id": "test_id", "ds_service_name": "test_name"}
{"time": "2025-08-13 11:27:14.728", "step": "llm_func_mid_result", "model": "", "user_id": "", "code": "", "message": "", "task_id": "", "request_id": "", "context": {"output": "hello"}, "interval": {"type": "llm_func_mid_result", "cost": "0.000"}, "ds_service_id": "test_id", "ds_service_name": "test_name"}
{"time": "2025-08-13 11:27:14.728", "step": "llm_func_end", "model": "", "user_id": "", "code": "", "message": "", "task_id": "", "request_id": "", "context": {}, "interval": {"type": "llm_func_end", "cost": "0.000"}, "ds_service_id": "test_id", "ds_service_name": "test_name"}
```
## 信息上报
1. 配置环境变量（默认关闭）
```shell
export TRACE_ENABLE_LOG=false
export TRACE_ENABLE_REPORT=true
export TRACE_AUTHENTICATION={YOUR_AUTHENTICATION}
export TRACE_ENDPOINT={YOUR_ENDPOINT}
```
2. 在非流式输出函数上添加注解，示例如下：

```python
from agentscope_bricks.utils.tracing_utils import trace, TraceType

@trace(trace_type=TraceType.LLM,
       trace_name="llm_func")
def llm_func(args: str):
    return args + "hello"
```


3. 在流式输出函数上添加注解，示例如下：
```python
from agentscope_bricks.utils.tracing_utils import trace, TraceType

@trace(trace_type=TraceType.LLM,
       trace_name="llm_func",
       get_finish_reason_func=get_finish_reason,
       merge_output_func=merge_output)
def llm_func(args: str):
    for i in range(10):
        yield i
```
其中get_finish_reason、merge_output为自定义处理函数，非必填，默认使用message_utils.py中的get_finish_reason和merge_incremental_chunk。

get_finish_reason 为自定义的获取 finish_reason 的函数，用于判断流式输出是否结束。示例如下：
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

merge_output 为自定义的合并输出的函数，用于最终输出信息的构造。示例如下：
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



4. 设置request_id和common attributes

request id用于绑定不同请求的上下文。common attribute为公共的span属性，该请求下所有span都会加上这些属性。

**自动设置 request_id**: 当用户没有在请求处理的开始阶段手动调用 `TracingUtil.set_request_id` 时，系统会在 root span 中自动生成并设置一个唯一的 request_id。

**手动设置**: 在**未被@trace装饰**的函数中设置request_id和common attributes，比如在请求信息解析完成后立即设置。示例如下：

```python
from agentscope_bricks.utils.tracing_utils import TracingUtil

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
5. 自定义信息上报(前提条件：**函数包含 kwargs 参数**)
```python
import json
from agentscope_bricks.utils.tracing_utils import trace, TraceType

@trace(trace_type=TraceType.LLM, trace_name="llm_func")
def llm_func(**kwargs):
    trace_event = kwargs.pop("trace_event", None)
    if trace_event:
        # 设置str类型属性
        trace_event.set_attribute("key", "value")
        # 设置dict类型属性
        trace_event.set_attribute("func_7.key", json.dumps({'key0': 'value0', 'key1': 'value1'}))
```