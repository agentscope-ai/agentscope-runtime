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

# Deep Dive into AgentApp

`AgentApp` is a complete agent service wrapper in **AgentScope Runtime**.
It can turn any agent that follows the interface into an API service, supporting:

- Streaming output (SSE)
- Health check endpoints
- Lifecycle hooks (`before_start` / `after_finish`)
- Celery asynchronous task queues
- Deployment to local or remote environments

Below is a detailed explanation of each feature with usage examples.

------

## Initialization and Basic Run

**Function**
Launch an HTTP API service containing the Agent, listening on the specified port, and providing the main processing endpoint (default `/process`).

**Example Usage**

```{code-cell}
from agentscope_runtime.engine import AgentApp
from agentscope_runtime.engine.agents.agentscope_agent import AgentScopeAgent
from agentscope.model import OpenAIChatModel
from agentscope.agent import ReActAgent

# Create Agent
agent = AgentScopeAgent(
    name="Friday",
    model=OpenAIChatModel(
        "gpt-4",
        api_key="YOUR_OPENAI_KEY",
    ),
    agent_config={"sys_prompt": "You are a helpful assistant."},
    agent_builder=ReActAgent,
)

# Create and run AgentApp
app = AgentApp(agent=agent, endpoint_path="/process", response_type="sse", stream=True)
app.run(host="0.0.0.0", port=8090)
```

------

## Streaming Output (SSE)

- **Function**
  Allows the client to receive generated results in real-time (suitable for chat, code generation, and other step-by-step output scenarios).

  **Key Parameters**

  - `response_type="sse"`
  - `stream=True`

**Client Example**

```bash
curl -N \
  -X POST "http://localhost:8090/process" \
  -H "Content-Type: application/json" \
  -d '{
    "input": [
      { "role": "user", "content": [{ "type": "text", "text": "Hello Friday" }] }
    ]
  }'
```

**Response Format**

```bash
data: {"sequence_number":0,"object":"response","status":"created", ... }
data: {"sequence_number":2,"object":"content","status":"in_progress","text":"Hello" }
data: {"sequence_number":3,"object":"content","status":"in_progress","text":" world!" }
data: {"sequence_number":4,"object":"message","status":"completed","text":"Hello world!" }
```

------

## Lifecycle Hooks

**Function**
Run custom logic before the application starts and after it stops — for example, loading models or closing connections.

**Key Parameters**

- `before_start`: runs before the API service starts
- `after_finish`: runs when the API service is shutting down

**Example Usage**

```{code-cell}
async def init_resources(app, **kwargs):
    print("🚀 Service starting, initializing resources...")

async def cleanup_resources(app, **kwargs):
    print("🛑 Service stopping, releasing resources...")

app = AgentApp(
    agent=agent,
    before_start=init_resources,
    after_finish=cleanup_resources
)
```

------

## Health Check Endpoints

**Function**
Automatically provides health probe endpoints for container or cluster deployment.

**Endpoints**

- `GET /health`: returns status and timestamp
- `GET /readiness`: checks readiness
- `GET /liveness`: checks liveness
- `GET /`: welcome message

**Example**

```bash
curl http://localhost:8090/health
curl http://localhost:8090/readiness
curl http://localhost:8090/liveness
curl http://localhost:8090/
```

------

## Middleware Extensions

**Function**
Run additional logic when requests enter or complete (e.g., logging, authentication, rate limiting).

**Example**

```{code-cell}
@app.middleware("http")
async def custom_logger(request, call_next):
    print(f"Received request: {request.method} {request.url}")
    response = await call_next(request)
    return response
```

- Built-in in AgentApp:
  - Request logging middleware
  - CORS (Cross-Origin Resource Sharing) support

------

## Celery Asynchronous Task Queue (Optional)

**Function**
Supports long-running background tasks without blocking the main HTTP thread.

**Key Parameters**

- `broker_url="redis://localhost:6379/0"`
- `backend_url="redis://localhost:6379/0"`

**Example Usage**

```{code-cell}
app = AgentApp(
    agent=agent,
    broker_url="redis://localhost:6379/0",
    backend_url="redis://localhost:6379/0"
)

@app.task("/longjob", queue="celery")
def heavy_computation(data):
    return {"result": data["x"] ** 2}
```

Request:

```bash
curl -X POST http://localhost:8090/longjob -H "Content-Type: application/json" -d '{"x": 5}'
```

Returns Task ID:

```bash
{"task_id": "abc123"}
```

Fetch result:

```bash
curl http://localhost:8090/longjob/abc123
```

------

## Local or Remote Deployment

**Function**
Deploy to different runtime environments via the unified `deploy()` method.

**Example Usage**

```{code-cell}
from agentscope_runtime.engine.deployers import LocalDeployManager

await app.deploy(LocalDeployManager(host="0.0.0.0", port=8091))
```
