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

`AgentApp` is the all-in-one application service wrapper in **AgentScope Runtime**. It provides an HTTP service framework for your agent logic and exposes it as an API.
In the current version, `AgentApp` **directly inherits from `FastAPI`**, allowing it to maintain high flexibility while deeply integrating advanced features specific to Agent business logic. Its core features include:

- **Full FastAPI Ecosystem Compatibility**: Supports native route registration (GET/POST, etc.), middleware extensions, and standard lifecycle management.
- **Streaming responses (SSE)** for real-time output.
- **Task Interrupt Management**: Provides a task interruption mechanism based on distributed backends (e.g., Redis), supporting precise control over long-running tasks.
- Built-in **health-check** endpoints.
- Optional **Celery** asynchronous task queues.
- Deployment to local or remote targets.

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

## Lifecycle Management (Lifespan)

**Purpose**

Loading models, initializing database connections before the app starts, or releasing resources upon shutdown are common requirements for production environments.

### Method 1: Pass Callables as Parameters (Simple Logic)

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

### Method 2: Use Lifespan Functions (Recommended)

This is the modern approach recommended by **AgentScope Runtime**. Thanks to its inheritance from `FastAPI`, `AgentApp` supports standard `lifespan` management, which offers the following advantages:

1. **Native FastAPI Experience** — **This method is identical to the standard FastAPI implementation.** If you are familiar with FastAPI development, you can apply native programming patterns seamlessly, significantly reducing learning costs.
2. **Structured Management** — Startup and cleanup logic are concentrated in a single function, separated by `yield`, making the logic more compact.
3. **State Sharing** — Resources can be attached to `app.state` during the startup phase and accessed via `app.state` throughout the application lifecycle (including request handlers).
4. **Built-in Compatibility** — Even with a custom `lifespan`, `AgentApp` internally coordinates the preparation of the Runner, the mounting of protocol adapters, and the lifecycle of interruption services.

```{code-cell}
from contextlib import asynccontextmanager
from fastapi import FastAPI
from agentscope.session import RedisSession
from agentscope_runtime.engine import AgentApp

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup Phase
    import fakeredis

    fake_redis = fakeredis.aioredis.FakeRedis(
        decode_responses=True
    )
    # NOTE: This FakeRedis instance is for development/testing only.
    # In production, replace it with your own Redis client/connection
    # (e.g., aioredis.Redis).
    app.state.session = RedisSession(
        connection_pool=fake_redis.connection_pool
    )
    print("✅ Service initialized")
    try:
        # yield transfers control to AgentApp
        yield
    finally:
        # Cleanup Phase
        print("✅ Resources released")

# Pass the defined lifespan to AgentApp
app = AgentApp(
    app_name="Friday",
    app_description="A helpful assistant",
    lifespan=lifespan,
)
```

**Key Notes**

- **Function Signature**: The `lifespan` function must accept a `FastAPI` instance as a parameter and be decorated with `@asynccontextmanager`.
- **Execution Order**: `AgentApp` handles scheduling internally. It first executes internal framework logic, then your defined `lifespan` startup logic, and finally reverses the cleanup logic when the service stops.
- **Deprecation Notice**: Please note that the `@app.init` and `@app.shutdown` decorators from older versions are now deprecated. Please migrate to the `lifespan` pattern for better stability.

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
    lifespan=lifespan,
)

@app.query(framework="agentscope")
async def query_func(
    self,
    msgs,
    request: AgentRequest = None,
    **kwargs,
):
    session_id = request.session_id
    user_id = request.user_id

    toolkit = Toolkit()
    toolkit.register_tool_function(execute_python_code)

    agent = ReActAgent(
        name="Friday",
        model=DashScopeChatModel(
            "qwen-turbo",
            api_key=os.getenv("DASHSCOPE_API_KEY"),
            stream=True,
        ),
        sys_prompt="You're a helpful assistant named Friday.",
        toolkit=toolkit,
        memory=InMemoryMemory(),
        formatter=DashScopeChatFormatter(),
    )
    agent.set_console_output_enabled(enabled=False)

    # Access session via app.state
    await app.state.session.load_session_state(
        session_id=session_id,
        user_id=user_id,
        agent=agent,
    )

    async for msg, last in stream_printing_messages(
        agents=[agent],
        coroutine_task=agent(msgs),
    ):
        yield msg, last

    await app.state.session.save_session_state(
        session_id=session_id,
        user_id=user_id,
        agent=agent,
    )
```

### Key Characteristics

1. **Framework Flexibility**: `framework` accepts `"agentscope"`, `"autogen"`, `"agno"`, `"langgraph"`, etc.
2. **Function Signature**:
   - `self`: the Runner instance bound to the AgentApp.
   - `msgs`: incoming messages
   - `request`: `AgentRequest` with `session_id`, `user_id`, etc.
   - `**kwargs`: extend as needed
3. **Streaming Friendly**: Handlers can be async generators that yield `(msg, last)` pairs.
4. **Stateful**: Access `app.state.state_service` to load/store custom state.
5. **Session Memory**: Use `app.state.session_service` to keep chat history per user/session.

### Comparison with the V0 version`agent` Parameter Approach

| Feature | Pre-built `agent` Parameter | Custom `@app.query` |
|---------|----------------------------|---------------------|
| Flexibility | Lower—uses a provided agent implementation | Full control over every step |
| State Management | Automatic | Manual but far more customizable |
| Suitable Scenarios | Simple, quick setups | Complex workflows needing fine-grained control |
| Multi-framework Support | Limited | Plug in any supported framework |

------

## Custom Endpoint Definition

You can extend the functional interfaces of AgentApp in two ways. Since `AgentApp` directly inherits from `FastAPI`, it not only retains the native flexibility of a Web framework but also provides enhanced tools optimized for Agent business scenarios (such as streaming output and object serialization).

### 1. Native FastAPI Routes

This is the most flexible approach. You can use standard FastAPI decorators (such as `@app.get`, `@app.post`, etc.) to define any business interface.

**Use Cases**:
- When you need full control over the `Response` object, status codes, or headers.
- Defining simple Web console interfaces or monitoring interfaces outside of health checks.

**Example**:

```python
app = AgentApp()

@app.get("/info")
async def get_info():
    """Interface defined using native FastAPI"""
    return {
        "app name": app.app_name,
        "app description": app.app_description,
        "custom_metadata": "v1.0.0"
    }

@app.post("/update_config")
async def update_config(data: dict):
    """Standard POST request handling"""
    # Your business logic
    return {"status": "updated"}
```

Client calls:

```bash
curl -X GET http://localhost:8090/info
curl -X POST http://localhost:8090/update_config \
  -H "Content-Type: application/json" \
  -d '{"config_key": "max_tokens", "value": 512}'
```
---

### 2. `@app.endpoint` Convenience Decorator

`AgentApp` provides a specialized `@app.endpoint` decorator. It wraps FastAPI's route registration under the hood, specifically optimized for Agent response scenarios.

**Core Advantages**:

1. Multiple return modes— Supports:

   - Regular sync/async functions returning JSON
   - Generators (sync or async) returning **streaming data** over SSE

2. Automatic parameter parsing— Endpoints can accept:

   - URL query parameters
   - JSON bodies mapped to Pydantic models
   - `fastapi.Request` objects
   - `AgentRequest` objects (convenient for accessing unified session/user info)

3. **Error handling** — Exceptions raised in streaming generators are automatically wrapped into SSE error events and sent to the client.

**Example**:

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
curl -N -X POST http://localhost:8090/stream_numbers
```

### Differences and Selection

| Feature | Native FastAPI (`@app.post`, etc.) | Convenience Decorator (`@app.endpoint`) |
| :--- | :--- | :--- |
| **Streaming** | Requires manual `StreamingResponse` and SSE formatting | **Automatically** identifies generators and converts to SSE |
| **Serialization** | Relies on FastAPI's built-in serialization | Enhanced deep serialization (supports complex types) |
| **Error Handling** | Requires manual Middleware or Exception Handlers | Provides **automatic error encapsulation** for streaming |
| **Flexibility** | **Very High**, supports all native configurations | **High**, focuses on Agent response standards |

**Recommendation**:
- If your interface needs to return **Agent reasoning processes or streaming data**, prioritize `@app.endpoint`.
- If your interface follows **standard Web business logic** (e.g., config management, status queries), using native FastAPI is suggested.

------

## Task Interrupt Management

In long-chain reasoning or complex Agent interaction scenarios, users may need to stop a running task mid-way. Currently, `AgentApp` leverages interruption backends (e.g., Redis) to provide precise control over task status, including:

- **Distributed Support**: Via a Redis backend, interrupt signals can be sent from any node in a cluster to stop a task running on another node.
- **Status Synchronization**: Automatically manages task states (RUNNING, STOPPED, FINISHED, ERROR) to prevent concurrency conflicts within the same Session.
- **Graceful Cancellation**: Utilizes Python's `asyncio` cancellation mechanism, allowing developers to execute cleanup logic (such as saving the Agent's current state) after catching `CancelledError`.

### Configuring the Interrupt Backend

`AgentApp` supports three backend configurations:

1. **Local Mode (Default)**: If no config is provided, it uses `LocalInterruptBackend`, suitable for single-machine runs.
2. **Redis Mode (Recommended)**: Configured via `interrupt_redis_url`, suitable for distributed deployments.
3. **Custom Backend**: Pass an instance inherited from `BaseInterruptBackend` via the `interrupt_backend` parameter.

**Example**:

```python
app = AgentApp(
    app_name="InterruptibleAgent",
    # Enable distributed interrupt support
    interrupt_redis_url="redis://localhost",
)
```

### Writing Interrupt-Aware Handlers

In a handler decorated by `@app.query`, when an external interrupt is triggered, the executing coroutine will raise an `asyncio.CancelledError`. Developers should catch this exception to implement state saving and other features.

Note: When catching an interrupt signal in your handler, it is essential to manually call `agent.interrupt()`. This ensures that underlying model calls or complex loops are correctly truncated. While `AgentApp` cancels the outer asynchronous task flow, the underlying Agent might still be performing a blocking call or complex loop. Calling `agent.interrupt()` is a best practice to ensure the reasoning chain is gracefully stopped and accurate state data is generated for subsequent recovery.

**Example Usage**

```python
@agent_app.query(framework="agentscope")
async def query_func(
    self,
    msgs,
    request: AgentRequest = None,
    **kwargs
):
    # Prepare Agent
    agent = ReActAgent(name="Friday", ...)

    # Load historical state (useful for recovery after interruption)
    await agent_app.state.session.load_session_state(
        session_id=request.session_id,
        user_id=request.user_id,
        agent=agent,
    )

    try:
        # AgentApp injects interrupt listening logic outside this generator
        # When agent_app.stop_chat is called, a CancelledError will be raised here
        async for msg, last in stream_printing_messages(...):
            yield msg, last

    except asyncio.CancelledError:
        # Core logic: Respond to interrupt signal
        print(f"Detected task {request.session_id} manually interrupted")

        # Important: Manually stop the underlying Agent task
        await agent.interrupt()

        # Must re-raise the exception to let the system mark status as STOPPED
        raise

    finally:
        # Save agent state whether task was interrupted or finished normally
        await agent_app.state.session.save_session_state(
            session_id=request.session_id,
            user_id=request.user_id,
            agent=agent,
        )
```


### Triggering Interrupt Signals

You can define a custom route and call the `agent_app.stop_chat` method within it to trigger an interrupt.

**Example**:
```python
@agent_app.post("/stop")
async def stop_task(request: AgentRequest):
    # Send interrupt signal to specific user_id and session_id
    await agent_app.stop_chat(
        user_id=request.user_id,
        session_id=request.session_id
    )
    return {"status": "ok"}
```

**Execution**:

Users simply send a request containing the `user_id` and `session_id` to the `/stop` endpoint to cancel the corresponding running task:
```bash
curl -X POST "http://localhost:8090/stop" \
  -H "Content-Type: application/json" \
  -d '{
    "input": [],
    "session_id": "Target Session ID",
    "user_id": "Target User ID"
  }'
```

## Full Example: AgentApp with State Management and Interruption

The following example demonstrates how to integrate the above features to build an Agent service with state recovery and task interruption capabilities.

### Complete Code

```{code-cell}
import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from agentscope.agent import ReActAgent
from agentscope.model import DashScopeChatModel
from agentscope.formatter import DashScopeChatFormatter
from agentscope.tool import Toolkit, execute_python_code
from agentscope.pipeline import stream_printing_messages
from agentscope.memory import InMemoryMemory
from agentscope.session import RedisSession

from agentscope_runtime.engine import AgentApp
from agentscope_runtime.engine.schemas.agent_schemas import AgentRequest

# 1. Define Lifecycle
@asynccontextmanager
async def lifespan(app: FastAPI):
    import fakeredis

    fake_redis = fakeredis.aioredis.FakeRedis(
        decode_responses=True
    )
    # NOTE: This FakeRedis instance is for development/testing only.
    # In production, replace it with your own Redis client/connection
    # (e.g., aioredis.Redis)
    app.state.session = RedisSession(
        connection_pool=fake_redis.connection_pool
    )
    try:
        yield
    finally:
        print("AgentApp is shutting down...")

# 2. Create AgentApp
agent_app = AgentApp(
    app_name="Friday",
    app_description="A helpful assistant",
    lifespan=lifespan,

    # Note: Using local interrupt backend as no redis url is provided.
    # To support distributed interrupts, add:
    # interrupt_redis_url="redis://localhost",
)

# 3. Define Request Handling Logic
@agent_app.query(framework="agentscope")
async def query_func(
    self,
    msgs,
    request: AgentRequest = None,
    **kwargs,
):
    session_id = request.session_id
    user_id = request.user_id

    toolkit = Toolkit()
    toolkit.register_tool_function(execute_python_code)

    agent = ReActAgent(
        name="Friday",
        model=DashScopeChatModel(
            "qwen-turbo",
            api_key=os.getenv("DASHSCOPE_API_KEY"),
            stream=True,
        ),
        sys_prompt="You're a helpful assistant named Friday.",
        toolkit=toolkit,
        memory=InMemoryMemory(),
        formatter=DashScopeChatFormatter(),
    )
    agent.set_console_output_enabled(enabled=True)

    # Load agent state
    await agent_app.state.session.load_session_state(
        session_id=session_id,
        user_id=user_id,
        agent=agent,
    )

    try:
        async for msg, last in stream_printing_messages(
            agents=[agent],
            coroutine_task=agent(msgs),
        ):
            yield msg, last

    except asyncio.CancelledError:
        # Interruption logic
        print(f"Task {session_id} was manually interrupted.")

        # Manually interrupt the agent to fully stop underlying execution
        await agent.interrupt()

        # Re-raise to mark status as STOPPED
        raise

    finally:
        # Save agent state
        await agent_app.state.session.save_session_state(
            session_id=session_id,
            user_id=user_id,
            agent=agent,
        )

# 4. Register Interrupt Route
@agent_app.post("/stop")
async def stop_task(request: AgentRequest):
    await agent_app.stop_chat(
        user_id=request.user_id,
        session_id=request.session_id,
    )
    return {
        "status": "success",
        "message": "Interrupt signal broadcasted.",
    }

# 5. Run Application
agent_app.run(host="127.0.0.1", port=8090)
```
### Interruption Feature Test Example

To test the interruption feature, you can use two terminal windows: one to start a long-running task and another to send the interrupt signal.

**1. Start a long-running task**

In the first terminal, send a complex request (e.g., asking the Agent to write a long story) and specify `session_id` and `user_id`. Using the `-N` parameter will allow you to see the streaming output in real-time.

```bash
# Terminal 1: Initiate inference request
curl -N \
  -X POST "http://localhost:8090/process" \
  -H "Content-Type: application/json" \
  -d '{
    "input": [
      {
        "role": "user",
        "content": [
          {
            "type": "text",
            "text": "Please write a very long and detailed story about a robot named Friday exploring a distant galaxy."
          }
        ]
      }
    ],
    "session_id": "ss-123",
    "user_id": "uu-123"
  }'
```

**2. Send an interrupt signal**

While the task is running (Terminal 1 is still printing), open a second terminal and send the interrupt request. **Note: the `session_id` and `user_id` must match the previous request.**

```bash
# Terminal 2: Trigger interrupt
curl -X POST "http://localhost:8090/stop" \
  -H "Content-Type: application/json" \
  -d '{
    "input": [],
    "session_id": "ss-123",
    "user_id": "uu-123"
  }'
```

**Expected Result**

*   **Terminal 2**: Will immediately return `{"status": "success", "message": "Interrupt signal broadcasted."}`.
*   **Terminal 1**: Streaming output will stop immediately, and the HTTP connection will close. If you caught `asyncio.CancelledError`, you will see your custom log (e.g., "Task ss-123 was manually interrupted.") in the server logs.


## Deploy Locally or Remotely

Use the unified `deploy()` method to ship the same app to different environments:

```{code-cell}
from agentscope_runtime.engine.deployers import LocalDeployManager

await app.deploy(LocalDeployManager(host="0.0.0.0", port=8091))
```

See {doc}`advanced_deployment` for additional deployers (Kubernetes, ModelStudio, AgentRun, etc.) and more configuration tips.

AgentScope Runtime provides serverless deployment options, including deploying agents to ModelStudio(FC) and AgentRun.
See {doc}`advanced_deployment` for more configuration details about ModelStudio and AgentRun.