# OpenCode AgentApp Example

This example shows how to connect AgentApp to an OpenCode server and forward
requests with `framework="opencode"` to the `/session/{id}/prompt_async`
endpoint.

## Prerequisites

- OpenCode server is running:

```bash
mkdir /tmp/opencode-tmp
cd /tmp/opencode-tmp
opencode serve --port 1234 --mdns --cors http://127.0.0.1:8080 --cors http://localhost:8080 # --mdns --cors is not necessary
```

## Run

```bash
python examples/opencode/run_opencode_agent.py # listen on port 8080
```

By default it connects to `http://127.0.0.1:1234` and uses
`/tmp/opencode-tmp` as the directory.

Use curl in another terminal:

```bash
curl -s -N -H 'Content-Type: application/json' \
  -d '{"input":[{"role":"user","type":"message","content":[{"type":"text","text":"hello"}]}]}' \
  http://127.0.0.1:8080/process
```

## Optional environment variables in this example

```bash
export OPENCODE_BASE_URL=http://127.0.0.1:1234
export OPENCODE_DIRECTORY=/tmp/opencode-tmp
export OPENCODE_AGENT=build
export OPENCODE_MODEL_PROVIDER=nvidia
export OPENCODE_MODEL_ID=deepseek-ai/deepseek-v3.1-terminus
export OPENCODE_ONLY_PART_UPDATED=true
export OPENCODE_INCLUDE_SUBAGENTS=true
```

> Note: `OPENCODE_MODEL_PROVIDER` and `OPENCODE_MODEL_ID` must be set
> together to include the `model` field in the request. This example uses
> `prompt_async` by default and relies on SSE events only (no blocking sync
> response). Set `OPENCODE_ONLY_PART_UPDATED=true` to only emit
> `message.part.updated` events.

## Subagent sessions

OpenCode forks subagents as child sessions. A child session has its own
`sessionID`, and `parentID` points to the parent session ID.

To observe subagent output:

- Subscribe to `/global/event` and watch for `session.created`/`session.updated`
  events where `info.parentID` matches your parent session.
- Or call `GET /session/{sessionID}/children` to list child sessions.
- Filter SSE events by `sessionID` depending on whether you want parent-only
  output or to include subagent sessions.
- When parsing `/global/event`, unwrap the `payload` field first (the event
  `type` and `properties` live under `payload`).
- For agent names, prefer `message.updated`:
  `properties.info.agent` is the canonical agent name for that `messageID`.
  `message.part.updated` does not always include agent info, so cache the
  name from `message.updated` and apply it to subsequent parts for the same
  message.

If you want the AgentApp example to emit subagent events, you can expand the
session filter in `examples/opencode/run_opencode_agent.py` to track child
sessions and allow them through:

```python
async with client.stream(
    "GET",
    f"{BASE_URL}/global/event",
) as resp:
```

```python
INCLUDE_SUBAGENTS = os.getenv("OPENCODE_INCLUDE_SUBAGENTS", "").lower() in {
    "1",
    "true",
    "yes",
}

allowed_session_ids = {session_id}

if INCLUDE_SUBAGENTS and event_type in ("session.created", "session.updated"):
    info = props.get("info") if isinstance(props, dict) else None
    if isinstance(info, dict) and info.get("parentID") == session_id:
        child_id = info.get("id")
        if child_id:
            allowed_session_ids.add(child_id)

event_session_id = _event_session_id(event_type, props)
if INCLUDE_SUBAGENTS:
    if event_session_id and event_session_id not in allowed_session_ids:
        continue
else:
    if event_session_id and event_session_id != session_id:
        continue
```

Example OpenCode events (truncated):

```json
{"type":"session.created","properties":{"info":{"id":"ses_CHILD","parentID":"ses_PARENT"}}}
```

Example AgentScope runtime output when a subagent responds:

```json
{"object":"message","status":"completed","role":"assistant","content":[{"type":"text","text":"Hello! How can I help you today?"}],"metadata":{"opencode":{"session_id":"ses_CHILD","message_id":"msg_...","part_id":"prt_...","part_type":"text"},"original_name":"build","agent_name":"build"}}
```
