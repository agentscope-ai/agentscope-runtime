# AgentApp API Invocation

Once an `AgentApp` is deployed and listening on `127.0.0.1:8090`, you can issue inference calls via the streaming endpoint or the OpenAI-compatible endpoint.

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

The endpoint reuses the Responses API schema. The `test_openai_compatible_mode` test also confirms that the model replies with its agent name “Friday”.

## Troubleshooting

- **Cannot connect**: Ensure the service is running, the port is free, and the client targets the correct host (especially in containers or remote deployments).
- **Parsing errors**: SSE frames must be processed line by line; tolerate keep-alive blank lines or partial JSON chunks.
- **Context not retained**: Confirm every request includes the same `session_id`, and that the `state/session` services are properly started within `init_func`.

With the examples above, you can quickly validate and consume a deployed Agent service.

