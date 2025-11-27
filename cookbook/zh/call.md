# 智能体应用API调用

当 `AgentApp` 成功部署并监听 `127.0.0.1:8090` 后，可以通过流式接口和 OpenAI 兼容接口完成推理调用。

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

该接口完全复用了 Responses API 的返回格式，测试用例 `test_openai_compatible_mode` 也验证了模型会自报家门为 “Friday”。

## 常见排查

- **无法连接**：确认服务仍在运行、端口未被占用，并检查客户端是否访问了正确的主机（容器或远程部署时尤为重要）。
- **解析失败**：SSE 帧需要逐行处理；如出现 keep-alive 空行或半截 JSON，请加上容错逻辑。
- **不记得上下文**：检查是否在所有请求中传入相同的 `session_id`，以及 `state/session` 服务是否在 `init_func` 中正确 `start()`。

结合以上示例，即可快速完成对已部署 Agent 服务的调用与验证。