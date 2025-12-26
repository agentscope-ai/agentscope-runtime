# AgentApp API Invocation

Once an `AgentApp` is deployed and listening on `127.0.0.1:8090`, you can issue inference calls via the streaming endpoint, the OpenAI-compatible endpoint, and the AG-UI endpoint.

## Prerequisites

- The `AgentApp` is running (the demo agent is named Friday in examples).
- Model credentials (for example `DASHSCOPE_API_KEY`) are configured in the environment.
- Prefer HTTP clients that support async SSE, such as `aiohttp` or `httpx`.

## `/process`: SSE Streaming Endpoint

### Request Body

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
  "session_id": "optional, reuse for the same session",
  "user_id": "optional, helps differentiate users"
}
```

- `input` follows the Agentscope message schema and can hold multiple messages and rich content.
- `session_id` is used to enable services like `StateService` and `SessionHistoryService` to record context, support multi‑turn memory, and persist the agent’s state.
- `user_id` defaults to empty; supply it if you need per-account accounting.

### Parsing the Stream

The server responds with Server-Sent Events, each line starting with `data: {...}` and ending with `data: [DONE]`. The snippet below (taken from `test_process_endpoint_stream_async`) demonstrates how to parse incremental text:

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
        # Accumulate or display text here
```

### Multi-turn Example

The following example shows how to reuse `session_id` across multiple requests to achieve effects such as “remembering the user’s name.”

1. First call: `"My name is Alice."`
2. Second call: `"What is my name?"`

The SSE stream will mention “Alice”, confirming that the session state is in effect.

```python
session_id = "123456"

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

## `/compatible-mode/v1/responses`: OpenAI-Compatible Endpoint

If your system already uses the official OpenAI SDK, simply point it to this endpoint for near drop-in compatibility:

```python
from openai import OpenAI

client = OpenAI(base_url="http://127.0.0.1:8090/compatible-mode/v1")
resp = client.responses.create(
    model="any_name",
    input="Who are you?",
)
print(resp.response["output"][0]["content"][0]["text"])
```

The endpoint reuses the Responses API schema. The `test_openai_compatible_mode` test also confirms that the model replies with its agent name "Friday".

## `/ag-ui`: AG-UI Protocol Compatible Endpoint

`AgentScope Runtime` supports the [`AG-UI Protocol`](https://docs.ag-ui.com/introduction) through an adapter pattern. Agent APIs built with the `@app.query` decorator are automatically adapted to the AG-UI Protocol request format.

### AG-UI Request Body Format

In the HTTP API, the body of POST `/ag-ui` is a RunAgentInput.

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
      "content": "Hello, please introduce yourself"
    }
  ],
  "tools": [],
  "context": [],
  "forwardedProps": {}
}
```

#### Field Descriptions

- **`threadId`** (required): Conversation thread ID, used to identify a dialogue session
- **`runId`** (required): Current run ID, should use a unique ID for each request
- **`messages`** (required): Message list, supporting multiple message types:
  - `role: "user"`: User message
  - `role: "assistant"`: Assistant message (can include text or tool calls)
  - `role: "system"`: System message
  - `role: "tool"`: Tool execution result message
- **`tools`** (optional): Available tool list
- **`context`** (optional): Context information
- **`state`** (optional): State information
- **`forwardedProps`** (optional): Forwarded properties

#### API Response

The server returns SSE (Server-Sent Events) format streaming responses, with each event starting with `data:` and containing JSON format event data. Currently supported event types include:

#### Event Types

| Event Type | Description | Example Fields |
|---------|------|---------|
| `run_started` | Run started | `thread_id`, `run_id` |
| `text_message_start` | Text message started | `message_id` |
| `text_message_content` | Text message incremental content | `message_id`, `delta` |
| `text_message_end` | Text message ended | `message_id` |
| `tool_call_start` | Tool call started | `tool_call_id`, `tool_call_name` |
| `tool_call_args` | Tool call arguments | `tool_call_id`, `delta` |
| `tool_call_end` | Tool call ended | `tool_call_id` |
| `tool_call_result` | Tool execution result | `tool_call_id`, `content` |
| `run_finished` | Run completed | `thread_id`, `run_id` |
| `run_error` | Run error | `run_id`, `message`, `code` |

#### Usage Example

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
                "content": "What's the weather like in Beijing today?"
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

Response example:

```json
data: {"type": "RUN_STARTED", "thread_id": "thread_1234", "run_id": "run_4567"}

data: {"type": "TOOL_CALL_START", "tool_call_id": "call_c51915f8d0ab4c6aac85e1", "tool_call_name": "get_weather", "message_id": "msg_57562f7d-e96d-4de9-8899-1334fc101e23_0"}

data: {"type": "TOOL_CALL_ARGS", "tool_call_id": "call_c51915f8d0ab4c6aac85e1", "delta": "{\"location\": \"Beijing\"}"}

data: {"type": "TOOL_CALL_END", "tool_call_id": "call_c51915f8d0ab4c6aac85e1"}

data: {"type": "TOOL_CALL_RESULT", "message_id": "msg_0ca9a23b-0674-496b-91c8-5bd699945e70_0", "tool_call_id": "call_c51915f8d0ab4c6aac85e1", "content": "[{\"type\": \"text\", \"text\": \"The weather in Beijing is sunny with a temperature of 25°C.\"}]", "role": "tool"}

data: {"type": "TEXT_MESSAGE_START", "message_id": "msg_8debb51f-3226-4f1a-a573-5f80db132f80_0", "role": "assistant"}

data: {"type": "TEXT_MESSAGE_CONTENT", "message_id": "msg_8debb51f-3226-4f1a-a573-5f80db132f80_0", "delta": "The weather"}

data: {"type": "TEXT_MESSAGE_CONTENT", "message_id": "msg_8debb51f-3226-4f1a-a573-5f80db132f80_0", "delta": " in Beijing today"}

data: {"type": "TEXT_MESSAGE_CONTENT", "message_id": "msg_8debb51f-3226-4f1a-a573-5f80db132f80_0", "delta": " is sunny,"}

data: {"type": "TEXT_MESSAGE_CONTENT", "message_id": "msg_8debb51f-3226-4f1a-a573-5f80db132f80_0", "delta": " with a temperature of 25"}

data: {"type": "TEXT_MESSAGE_CONTENT", "message_id": "msg_8debb51f-3226-4f1a-a573-5f80db132f80_0", "delta": "°C."}

data: {"type": "TEXT_MESSAGE_END", "message_id": "msg_8debb51f-3226-4f1a-a573-5f80db132f80_0"}

data: {"type": "RUN_FINISHED", "thread_id": "thread_1234", "run_id": "run_4567"}

```

#### Frontend Integration

Using `CopilotKit`, you can quickly build Agent applications based on existing AG-UI Protocol APIs. For details, refer to the `CopilotKit` [documentation](https://docs.copilotkit.ai/).

## Troubleshooting

- **Cannot connect**: Ensure the service is running, the port is free, and the client targets the correct host (especially in containers or remote deployments).
- **Parsing errors**: SSE frames must be processed line by line; tolerate keep-alive blank lines or partial JSON chunks.
- **Context not retained**: Confirm every request includes the same `session_id`, and that the `state/session` services are properly started within `init_func`.

With the examples above, you can quickly validate and consume a deployed Agent service.