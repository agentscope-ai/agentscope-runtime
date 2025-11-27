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

`AgentApp` is the all-in-one agent service wrapper in **AgentScope Runtime**. Any agent that matches its interface can be exposed as an API service supporting:

- Streaming responses (SSE)
- Health-check endpoints
- Lifecycle hooks (`before_start` / `after_finish`)
- Celery asynchronous task queues
- Deployments to local or remote targets

The sections below dive into each capability with concrete examples.

------

## Initialization and Basic Run

**What it does**

Starts an HTTP API service that wraps your agent, listens on the configured port, and serves the primary handler (default `/process`).

**Example**

```{code-cell}
from agentscope_runtime.engine import AgentApp
from agentscope_runtime.engine.agents.agentscope_agent import AgentScopeAgent
from agentscope.model import OpenAIChatModel
from agentscope.agent import ReActAgent

# Build an Agent
agent = AgentScopeAgent(
    name="Friday",
    model=OpenAIChatModel(
        "gpt-4",
        api_key="YOUR_OPENAI_KEY",
    ),
    agent_config={"sys_prompt": "You are a helpful assistant."},
    agent_builder=ReActAgent,
)

# Create and launch AgentApp
app = AgentApp(agent=agent, endpoint_path="/process", response_type="sse", stream=True)
app.run(host="0.0.0.0", port=8090)
```

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
data: {"sequence_number":2,"object":"content","status":"in_progress","text":"Hello" }
data: {"sequence_number":3,"object":"content","status":"in_progress","text":" world!" }
data: {"sequence_number":4,"object":"message","status":"completed","text":"Hello world!" }
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

Decorators are more flexible and keep the logic close to the app definition:

```{code-cell}
from agentscope_runtime.engine import AgentApp
from agentscope_runtime.engine.services.agent_state import InMemoryStateService
from agentscope_runtime.engine.services.session_history import InMemorySessionHistoryService

app = AgentApp(
    app_name="Friday",
    app_description="A helpful assistant",
)

@app.init
async def init_func(self):
    """Initialize service resources"""
    self.state_service = InMemoryStateService()
    self.session_service = InMemorySessionHistoryService()

    await self.state_service.start()
    await self.session_service.start()
    print("✅ Service initialized")

@app.shutdown
async def shutdown_func(self):
    """Release service resources"""
    await self.state_service.stop()
    await self.session_service.stop()
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

## Middleware Extensions

**Purpose**

Inject logic before or after handling each request—for logging, auth, rate limiting, etc.

```{code-cell}
@app.middleware("http")
async def custom_logger(request, call_next):
    print(f"Request: {request.method} {request.url}")
    response = await call_next(request)
    return response
```

AgentApp ships with:

- Request logging middleware
- Built-in CORS support

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
from agentscope_runtime.adapters.agentscope.memory import AgentScopeSessionHistoryMemory

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
        memory=AgentScopeSessionHistoryMemory(
            service=self.session_service,
            session_id=session_id,
            user_id=user_id,
        ),
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
from agentscope_runtime.adapters.agentscope.memory import AgentScopeSessionHistoryMemory
from agentscope_runtime.engine.services.agent_state import InMemoryStateService
from agentscope_runtime.engine.services.session_history import InMemorySessionHistoryService

app = AgentApp(
    app_name="Friday",
    app_description="A helpful assistant with state management",
)

@app.init
async def init_func(self):
    """Start state and session services"""
    self.state_service = InMemoryStateService()
    self.session_service = InMemorySessionHistoryService()
    await self.state_service.start()
    await self.session_service.start()

@app.shutdown
async def shutdown_func(self):
    """Tear down services"""
    await self.state_service.stop()
    await self.session_service.stop()

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
        memory=AgentScopeSessionHistoryMemory(
            service=self.session_service,
            session_id=session_id,
            user_id=user_id,
        ),
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

### Comparison with the `agent` Parameter Approach

| Feature | Pre-built `agent` Parameter | Custom `@app.query` |
|---------|----------------------------|---------------------|
| Flexibility | Lower—uses a provided agent implementation | Full control over every step |
| State Management | Automatic | Manual but far more customizable |
| Suitable Scenarios | Simple, quick setups | Complex workflows needing fine-grained control |
| Multi-framework Support | Limited | Plug in any supported framework |

------

## Deploy Locally or Remotely

Use the unified `deploy()` method to ship the same app to different environments:

```{code-cell}
from agentscope_runtime.engine.deployers import LocalDeployManager

await app.deploy(LocalDeployManager(host="0.0.0.0", port=8091))
```

See {doc}`advanced_deployment` for additional deployers (Kubernetes, ModelStudio, AgentRun, etc.) and more configuration tips.
