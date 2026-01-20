# 智能体应用API调用

当 `AgentApp` 成功部署并监听 `127.0.0.1:8090` 后，可以通过流式接口、OpenAI 兼容接口和 AG-UI 接口完成推理调用。

## 环境要求

- 已按照官方流程启动 `AgentApp`（示例名称为 Friday）。
- 在运行环境中配置好模型密钥，例如 `DASHSCOPE_API_KEY`。
- 客户端推荐使用支持异步与 SSE 的 HTTP 库（如 `aiohttp`, `httpx`）。

## `/process`：SSE 流式接口

### 请求体格式

```json
{
  "input": [
    {
      "role": "user",
      "content": [
        { "type": "text", "text": "What is the capital of France?" }
      ]
    }
  ],
  "session_id": "可选，同一会话复用",
  "user_id": "可选，便于区分多用户"
}
```

- `input` 遵循 Agentscope 消息格式，可包含多条消息及富媒体内容。
- `session_id` 用于让 `StateService` / `SessionHistoryService` 等服务记录上下文，支持多轮记忆以及智能体状态持久化。
- `user_id` 默认可缺省，如需统计不同账号可自行传入。

### 解析流式响应

服务端以 Server-Sent Events 协议返回增量结果，每行形如 `data: {...}`，最终以 `data: [DONE]` 结束。下方代码节选自 `test_process_endpoint_stream_async`，演示如何解析并抽取文本：

```python
async with session.post(url, json=payload) as resp:
    assert resp.headers["Content-Type"].startswith("text/event-stream")
    async for chunk, _ in resp.content.iter_chunks():
        if not chunk:
            continue
        line = chunk.decode("utf-8").strip()
        if not line.startswith("data:"):
            continue
        data_str = line[len("data:") :].strip()
        if data_str == "[DONE]":
            break
        event = json.loads(data_str)
        text = event["output"][0]["content"][0]["text"]
        # 在此累积或实时显示 text
```

### 多轮对话示例

下面的例子展示了如何在多次请求中复用 `session_id`，实现“记住用户姓名”等效果：

1. 第一次调用：`"My name is Alice."`
2. 第二次调用：`"What is my name?"`

SSE 输出中会包含 “Alice”，表明状态与会话历史已经生效。

```python
session_id = "123456"

url = f"http://localhost:{PORT}/process"

async with aiohttp.ClientSession() as session:
    payload1 = {
        "input": [
            {
                "role": "user",
                "content": [{"type": "text", "text": "My name is Alice."}],
            },
        ],
        "session_id": session_id,
    }
    async with session.post(url, json=payload1) as resp:
        assert resp.status == 200
        assert resp.headers.get("Content-Type", "").startswith(
            "text/event-stream",
        )
        async for chunk, _ in resp.content.iter_chunks():
            if not chunk:
                continue
            line = chunk.decode("utf-8").strip()
            if (
                line.startswith("data:")
                and line[len("data:") :].strip() == "[DONE]"
            ):
                break

payload2 = {
    "input": [
        {
            "role": "user",
            "content": [{"type": "text", "text": "What is my name?"}],
        },
    ],
    "session_id": session_id,
}

async with aiohttp.ClientSession() as session:
    async with session.post(url, json=payload2) as resp:
        assert resp.status == 200
        assert resp.headers.get("Content-Type", "").startswith(
            "text/event-stream",
        )

        found_name = False

        async for chunk, _ in resp.content.iter_chunks():
            if not chunk:
                continue
            line = chunk.decode("utf-8").strip()
            if line.startswith("data:"):
                data_str = line[len("data:") :].strip()
                if data_str == "[DONE]":
                    break
                try:
                    event = json.loads(data_str)
                except json.JSONDecodeError:
                    continue

                if "output" in event:
                    try:
                        text_content = event["output"][0]["content"][0][
                            "text"
                        ].lower()
                        if "alice" in text_content:
                            found_name = True
                    except Exception:
                        pass

        assert found_name, "Did not find 'Alice' in the second turn output"

```

## `/compatible-mode/v1/responses`：OpenAI 兼容接口

若现有系统已经接入 OpenAI 官方 SDK，可直接指向兼容端点，几乎零改造即可使用：

```python
from openai import OpenAI

client = OpenAI(base_url="http://127.0.0.1:8090/compatible-mode/v1")
resp = client.responses.create(
    model="any_name",
    input="Who are you?",
)
print(resp.response["output"][0]["content"][0]["text"])
```

该接口完全复用了 Responses API 的返回格式，测试用例 `test_openai_compatible_mode` 也验证了模型会自报家门为 "Friday"。

## `/ag-ui`：AG-UI Protocol兼容接口

`AgentScope Runtime` 通过适配器模式支持了[`AG-UI Protocol`](https://docs.ag-ui.com/introduction)，基于 `@app.query` 装饰器构建的Agent API，会自动适配为AG-UI Protocol的请求体格式。

### AG-UI 请求体格式

HTTP API 中，POST `/ag-ui` 的 body 即 RunAgentInput。

```json
{
  "threadId": "thread_123",
  "runId": "run_456",
  "parentRunId": "run_000",
  "state": {},
  "messages": [
    {
      "id": "msg_1",
      "role": "user",
      "content": "你好，请介绍一下你自己"
    }
  ],
  "tools": [],
  "context": [],
  "forwardedProps": {}
}
```

#### 字段说明

- **`threadId`**（必需）：会话线程ID，用于标识一个对话会话
- **`runId`**（必需）：本次运行ID，每次请求应使用唯一的ID
- **`messages`**（必需）：消息列表，支持多种消息类型：
  - `role: "user"`：用户消息
  - `role: "assistant"`：助手消息（可包含文本或工具调用）
  - `role: "system"`：系统消息
  - `role: "tool"`：工具执行结果消息
- **`tools`**（可选）：可用工具列表
- **`context`**（可选）：上下文信息
- **`state`**（可选）：状态信息
- **`forwardedProps`**（可选）：转发属性

#### API响应

服务端返回 SSE（Server-Sent Events）格式的流式响应，每个事件以 `data:` 开头，包含 JSON 格式的事件数据。目前适配器支持的事件类型包括：

#### 事件类型

| 事件类型 | 说明 | 示例字段 |
|---------|------|---------|
| `run_started` | 运行开始 | `thread_id`, `run_id` |
| `text_message_start` | 文本消息开始 | `message_id` |
| `text_message_content` | 文本消息增量内容 | `message_id`, `delta` |
| `text_message_end` | 文本消息结束 | `message_id` |
| `tool_call_start` | 工具调用开始 | `tool_call_id`, `tool_call_name` |
| `tool_call_args` | 工具调用参数 | `tool_call_id`, `delta` |
| `tool_call_end` | 工具调用结束 | `tool_call_id` |
| `tool_call_result` | 工具执行结果 | `tool_call_id`, `content` |
| `run_finished` | 运行完成 | `thread_id`, `run_id` |
| `run_error` | 运行错误 | `run_id`, `message`, `code` |

#### 调用示例

```python
import aiohttp
import json

async def call_ag_ui_endpoint():
    url = "http://localhost:8080/ag-ui"
    payload = {
        "threadId": "thread_1234",
        "runId": "run_4567",
        "messages": [
            {
                "id": "msg_1",
                "role": "user",
                "content": "北京今天的天气如何"
            }
        ]
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload) as resp:
            assert resp.status == 200
            assert resp.headers["Content-Type"].startswith("text/event-stream")

            async for chunk, _ in resp.content.iter_chunks():
                if not chunk:
                    continue

                line = chunk.decode("utf-8").strip()
                if not line.startswith("data:"):
                    continue
                print(line + "\n")



```

返回示例:

```
data: {"type": "RUN_STARTED", "thread_id": "thread_1234", "run_id": "run_4567"}

data: {"type": "TOOL_CALL_START", "tool_call_id": "call_c51915f8d0ab4c6aac85e1", "tool_call_name": "get_weather", "message_id": "msg_57562f7d-e96d-4de9-8899-1334fc101e23_0"}

data: {"type": "TOOL_CALL_ARGS", "tool_call_id": "call_c51915f8d0ab4c6aac85e1", "delta": "{\"location\": \"北京\"}"}

data: {"type": "TOOL_CALL_END", "tool_call_id": "call_c51915f8d0ab4c6aac85e1"}

data: {"type": "TOOL_CALL_RESULT", "message_id": "msg_0ca9a23b-0674-496b-91c8-5bd699945e70_0", "tool_call_id": "call_c51915f8d0ab4c6aac85e1", "content": "[{\"type\": \"text\", \"text\": \"The weather in 北京 is sunny with a temperature of 25°C.\"}]", "role": "tool"}

data: {"type": "TEXT_MESSAGE_START", "message_id": "msg_8debb51f-3226-4f1a-a573-5f80db132f80_0", "role": "assistant"}

data: {"type": "TEXT_MESSAGE_CONTENT", "message_id": "msg_8debb51f-3226-4f1a-a573-5f80db132f80_0", "delta": "北京"}

data: {"type": "TEXT_MESSAGE_CONTENT", "message_id": "msg_8debb51f-3226-4f1a-a573-5f80db132f80_0", "delta": "今天的天气是"}

data: {"type": "TEXT_MESSAGE_CONTENT", "message_id": "msg_8debb51f-3226-4f1a-a573-5f80db132f80_0", "delta": "晴朗，"}

data: {"type": "TEXT_MESSAGE_CONTENT", "message_id": "msg_8debb51f-3226-4f1a-a573-5f80db132f80_0", "delta": "气温为25"}

data: {"type": "TEXT_MESSAGE_CONTENT", "message_id": "msg_8debb51f-3226-4f1a-a573-5f80db132f80_0", "delta": "°C。"}

data: {"type": "TEXT_MESSAGE_END", "message_id": "msg_8debb51f-3226-4f1a-a573-5f80db132f80_0"}

data: {"type": "RUN_FINISHED", "thread_id": "thread_1234", "run_id": "run_4567"}
```

#### 前端集成

基于 `CopilotKit` 可以快速基于已有的 AG-UI Protocol API 构建 Agent 应用，详细可以参考 `CopilotKit` 的[文档](https://docs.copilotkit.ai/)。

## 常见排查

- **无法连接**：确认服务仍在运行、端口未被占用，并检查客户端是否访问了正确的主机（容器或远程部署时尤为重要）。
- **解析失败**：SSE 帧需要逐行处理；如出现 keep-alive 空行或半截 JSON，请加上容错逻辑。
- **不记得上下文**：检查是否在所有请求中传入相同的 `session_id`，以及 `state/session` 服务是否在 `init_func` 中正确 `start()`。
