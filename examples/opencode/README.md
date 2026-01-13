# OpenCode AgentApp Example

This example shows how to connect AgentApp to an OpenCode server and forward
requests with `framework="opencode"` to the `/session/{id}/prompt_async`
endpoint.

## Prerequisites

- OpenCode server is running:

```bash
opencode serve --port 1234 --mdns --cors http://127.0.0.1:8080 --cors http://localhost:8080
```

## Run

```bash
python examples/opencode/run_opencode_agent.py
```

Use curl in another terminal:

```bash
curl -s -N -H 'Content-Type: application/json' \
  -d '{"input":[{"role":"user","type":"message","content":[{"type":"text","text":"hello"}]}]}' \
  http://127.0.0.1:8080/process
```

By default it connects to `http://127.0.0.1:1234` and uses
`/tmp/opencode-tmp` as the directory.

## Optional environment variables

```bash
export OPENCODE_BASE_URL=http://127.0.0.1:1234
export OPENCODE_DIRECTORY=/tmp/opencode-tmp
export OPENCODE_AGENT=build
export OPENCODE_MODEL_PROVIDER=nvidia
export OPENCODE_MODEL_ID=deepseek-ai/deepseek-v3.1-terminus
export OPENCODE_ONLY_PART_UPDATED=true
```

> Note: `OPENCODE_MODEL_PROVIDER` and `OPENCODE_MODEL_ID` must be set
> together to include the `model` field in the request. This example uses
> `prompt_async` by default and relies on SSE events only (no blocking sync
> response). Set `OPENCODE_ONLY_PART_UPDATED=true` to only emit
> `message.part.updated` events.
