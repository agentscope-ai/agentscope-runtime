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

# Simple Deployment

`AgentApp` is the all-in-one application service wrapper in **AgentScope Runtime**.
It provides the HTTP service framework for your agent logic and can expose it as an API with features such as:

- **Streaming responses (SSE)** for real-time output
- Built-in **health-check** endpoints
- **Lifecycle hooks** (`@app.init` / `@app.shutdown`) for startup and cleanup logic
- Optional **Celery** asynchronous task queues
- Deployment to local or remote targets

**Important**:
In the current version, `AgentApp` does not automatically include a `/process` endpoint.
You must explicitly register a request handler using decorators (e.g., `@app.query(...)`) before your service can process incoming requests.

The sections below dive into each capability with concrete examples.

------

## Initialization and Basic Run

**What it does**

Creates a minimal `AgentApp` instance and starts a FastAPI-based HTTP service skeleton.
In its initial state, the service only provides:

- Welcome page `/`
- Health check `/health`
- Readiness probe `/readiness`
- Liveness probe `/liveness`

**Note**:

- By default, no `/process` or other business endpoints are exposed.
- You **must** register at least one handler using decorators such as `@app.query(...)` or `@app.task(...)` before the service can process requests.
- Handlers can be regular or async functions, and may support streaming output via async generators.

**Example**

```{code-cell}
from agentscope_runtime.engine import AgentApp

agent_app = AgentApp(
    app_name="Friday",
    app_description="A helpful assistant",
)

agent_app.run(host="127.0.0.1", port=8090)
```

------

## A2A Extension Field Configuration

**What it does**

Extend the configuration of the agent's A2A (Agent-to-Agent) protocol information and runtime-related fields through the `a2a_config` parameter.

**Key parameter**

- `a2a_config`: Optional parameter, supports `AgentCardWithRuntimeConfig` object.

**Configuration content**

`a2a_config` supports configuring two types of fields:

1. **AgentCard protocol fields**: Passed through the `agent_card` field, containing skills, transport protocols, input/output modes, etc.
2. **Runtime fields**: Top-level fields, containing service registration and discovery (Registry), timeout settings, service endpoints, etc.

**Example**

```{code-cell}
from agentscope_runtime.engine import AgentApp
from agentscope_runtime.engine.deployers.adapter.a2a import (
    AgentCardWithRuntimeConfig,
)

agent_app = AgentApp(
    app_name="MyAgent",
    app_description="My agent description",
    a2a_config=AgentCardWithRuntimeConfig(
        agent_card={
            "name": "MyAgent",
            "description": "My agent description",
            "skills": [...],  # Agent skills list
            "default_input_modes": ["text"],
            "default_output_modes": ["text"],
            # ... other protocol fields
        },
        registry=[...],  # Service registration and discovery
        task_timeout=120,  # Task timeout settings
        # ... other configuration fields
    ),
)
```

**Detailed documentation**

For complete field descriptions, configuration methods, and usage examples, please refer to the {doc}`a2a_registry` documentation.

------

## Streaming Output (SSE)

**Purpose**

Stream partial outputs to clients in real time—perfect for chat, coding, or any incremental generation scenario.

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
data: {"sequence_number":1,"object":"response","status":"in_progress", ... }
data: {"sequence_number":2,"object":"message","status":"in_progress", ... }
data: {"sequence_number":3,"object":"content","status":"in_progress","text":"Hello" }
data: {"sequence_number":4,"object":"content","status":"in_progress","text":" World!" }
data: {"sequence_number":5,"object":"message","status":"completed","text":"Hello World!" }
data: {"sequence_number":6,"object":"response","status":"completed", ... }
```

------

## Lifecycle Hooks

**Purpose**

Execute custom logic before startup and after shutdown—handy for loading models, opening connections, or releasing resources.

### Method 1: Pass Callables as Parameters

**Key Parameters**

- `before_start`: invoked before the API server starts
- `after_finish`: invoked when the server stops

```{code-cell}
async def init_resources(app, **kwargs):
    print("🚀 Service launching, initializing resources...")

async def cleanup_resources(app, **kwargs):
    print("🛑 Service stopping, cleaning up resources...")

app = AgentApp(
    agent=agent,
    before_start=init_resources,
    after_finish=cleanup_resources
)
```

### Method 2: Use Decorators (Recommended)

In addition to passing hook functions via constructor parameters, you can also register lifecycle hooks using decorators.
This approach has the following advantages:

1. **More flexible and intuitive** — The lifecycle logic is placed directly alongside the application definition, making the structure clearer and code more readable.
2. **Shared member variables** — Functions defined with decorators receive `self`, allowing access to the attributes and services of the `AgentApp` instance (for example, state services or session services started in `@app.init`), enabling convenient sharing and reuse of resources across different lifecycle stages or request handlers.

```{code-cell}
from agentscope_runtime.engine import AgentApp
from agentscope_runtime.engine.services.agent_state import InMemoryStateService

app = AgentApp(
    app_name="Friday",
    app_description="A helpful assistant",
)

@app.init
async def init_func(self):
    """Initialize service resources"""
    self.state_service = InMemoryStateService()

    await self.state_service.start()
    print("✅ Service initialized")

@app.shutdown
async def shutdown_func(self):
    """Release service resources"""
    await self.state_service.stop()
    print("✅ Resources released")
```

**Decorator Notes**

- `@app.init`: runs before the service starts
- `@app.shutdown`: runs as the service stops
- Decorated functions receive `self`, so they can access the `AgentApp` instance
- Works with sync or async functions

------

## Health Check Endpoints

**Purpose**

Expose readiness probes automatically for containers or clusters.

**Endpoints**

- `GET /health`: returns status and timestamp
- `GET /readiness`: readiness probe
- `GET /liveness`: liveness probe
- `GET /`: welcome message

```bash
curl http://localhost:8090/health
curl http://localhost:8090/readiness
curl http://localhost:8090/liveness
curl http://localhost:8090/
```

------

## Celery Asynchronous Task Queue (Optional)

**Purpose**

Offload long-running background tasks so HTTP handlers return immediately.

**Key Parameters**

- `broker_url="redis://localhost:6379/0"`
- `backend_url="redis://localhost:6379/0"`

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

Submit a task:

```bash
curl -X POST http://localhost:8090/longjob -H "Content-Type: application/json" -d '{"x": 5}'
```

Response:

```bash
{"task_id": "abc123"}
```

Fetch the result:

```bash
curl http://localhost:8090/longjob/abc123
```

------

## Custom Query Handling

**Purpose**

Use `@app.query()` to fully control request handling—ideal when you need custom state, multi-turn logic, or different frameworks.

### Basic Usage

```{code-cell}
from agentscope_runtime.engine import AgentApp
from agentscope_runtime.engine.schemas.agent_schemas import AgentRequest
from agentscope.agent import ReActAgent
from agentscope.model import DashScopeChatModel
from agentscope.pipeline import stream_printing_messages
from agentscope.memory import InMemoryMemory

app = AgentApp(
    app_name="Friday",
    app_description="A helpful assistant",
)

@app.query(framework="agentscope")
async def query_func(
    self,
    msgs,
    request: AgentRequest = None,
    **kwargs,
):
    """Custom query handler"""
    session_id = request.session_id
    user_id = request.user_id

    # Load session state
    state = await self.state_service.export_state(
        session_id=session_id,
        user_id=user_id,
    )

    # Build agent
    agent = ReActAgent(
        name="Friday",
        model=DashScopeChatModel(
            "qwen-turbo",
            api_key=os.getenv("DASHSCOPE_API_KEY"),
            stream=True,
        ),
        sys_prompt="You're a helpful assistant named Friday.",
        memory=InMemoryMemory(),
    )

    # Restore state if present
    if state:
        agent.load_state_dict(state)

    # Stream responses
    async for msg, last in stream_printing_messages(
        agents=[agent],
        coroutine_task=agent(msgs),
    ):
        yield msg, last

    # Persist state
    state = agent.state_dict()
    await self.state_service.save_state(
        user_id=user_id,
        session_id=session_id,
        state=state,
    )
```

### Key Characteristics

1. **Framework Flexibility**: `framework` accepts `"agentscope"`, `"autogen"`, `"agno"`, `"langgraph"`, etc.
2. **Function Signature**:
   - `self`: the AgentApp instance (access services, configs, etc.)
   - `msgs`: incoming messages
   - `request`: `AgentRequest` with `session_id`, `user_id`, etc.
   - `**kwargs`: extend as needed
3. **Streaming Friendly**: Handlers can be async generators that yield `(msg, last)` pairs.
4. **Stateful**: Access `self.state_service` to load/store custom state.
5. **Session Memory**: Use `self.session_service` to keep chat history per user/session.

### Full Example with State Management

```{code-cell}
import os
from agentscope_runtime.engine import AgentApp
from agentscope_runtime.engine.schemas.agent_schemas import AgentRequest
from agentscope.agent import ReActAgent
from agentscope.model import DashScopeChatModel
from agentscope.tool import Toolkit, execute_python_code
from agentscope.pipeline import stream_printing_messages
from agentscope.memory import InMemoryMemory
from agentscope_runtime.engine.services.agent_state import InMemoryStateService

app = AgentApp(
    app_name="Friday",
    app_description="A helpful assistant with state management",
)

@app.init
async def init_func(self):
    """Start state and session services"""
    self.state_service = InMemoryStateService()
    await self.state_service.start()

@app.shutdown
async def shutdown_func(self):
    """Tear down services"""
    await self.state_service.stop()

@app.query(framework="agentscope")
async def query_func(
    self,
    msgs,
    request: AgentRequest = None,
    **kwargs,
):
    """Query handler with state persistence"""
    session_id = request.session_id
    user_id = request.user_id

    # Load historical state
    state = await self.state_service.export_state(
        session_id=session_id,
        user_id=user_id,
    )

    # Register tools
    toolkit = Toolkit()
    toolkit.register_tool_function(execute_python_code)

    # Build agent
    agent = ReActAgent(
        name="Friday",
        model=DashScopeChatModel(
            "qwen-turbo",
            api_key=os.getenv("DASHSCOPE_API_KEY"),
            enable_thinking=True,
            stream=True,
        ),
        sys_prompt="You're a helpful assistant named Friday.",
        toolkit=toolkit,
        memory=InMemoryMemory(),
    )
    agent.set_console_output_enabled(enabled=False)

    # Restore state if any
    if state:
        agent.load_state_dict(state)

    # Stream output
    async for msg, last in stream_printing_messages(
        agents=[agent],
        coroutine_task=agent(msgs),
    ):
        yield msg, last

    # Save state
    state = agent.state_dict()
    await self.state_service.save_state(
        user_id=user_id,
        session_id=session_id,
        state=state,
    )

# Launch service
app.run(host="0.0.0.0", port=8090)
```

### Comparison with the V0 version`agent` Parameter Approach

| Feature | Pre-built `agent` Parameter | Custom `@app.query` |
|---------|----------------------------|---------------------|
| Flexibility | Lower—uses a provided agent implementation | Full control over every step |
| State Management | Automatic | Manual but far more customizable |
| Suitable Scenarios | Simple, quick setups | Complex workflows needing fine-grained control |
| Multi-framework Support | Limited | Plug in any supported framework |

------

## Custom Endpoints via `@app.endpoint`

In addition to using `@app.query(...)` for the unified `/process` entry point, `AgentApp` also supports registering arbitrary HTTP endpoints via the `@app.endpoint(...)` decorator.

**Key Features**:

1. **High flexibility** — Define dedicated API paths for different business needs, rather than routing all traffic through `/process`.

2. Multiple return modes— Supports:

   - Regular sync/async functions returning JSON
   - Generators (sync or async) returning **streaming data** over SSE

3. Automatic parameter parsing— Endpoints can accept:

   - URL query parameters
   - JSON bodies mapped to Pydantic models
   - `fastapi.Request` objects
   - `AgentRequest` objects (convenient for accessing unified session/user info)

4. **Error handling** — Exceptions raised in streaming generators are automatically wrapped into SSE error events and sent to the client.

**Example**：

```python
app = AgentApp()

@app.endpoint("/hello")
def hello_endpoint():
    return {"msg": "Hello world"}

@app.endpoint("/stream_numbers")
async def stream_numbers():
    for i in range(5):
        yield f"number: {i}\n"
```

Client calls:

```bash
curl -X POST http://localhost:8090/hello
curl -X POST http://localhost:8090/stream_numbers
```

---

## Deploy Locally or Remotely

Use the unified `deploy()` method to ship the same app to different environments:

```{code-cell}
from agentscope_runtime.engine.deployers import LocalDeployManager

await app.deploy(LocalDeployManager(host="0.0.0.0", port=8091))
```

See {doc}`advanced_deployment` for additional deployers (Kubernetes, ModelStudio, AgentRun, etc.) and more configuration tips.

AgentScope Runtime provides serverless deployment options, including deploying agents to ModelStudio(FC) and AgentRun.
See {doc}`advanced_deployment` for more configuration details about ModelStudio and AgentRun.
