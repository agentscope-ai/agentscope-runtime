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

# Services and Adapters

## Overview

In **AgentScope Runtime**, **Services** (`Service`) provide core capabilities to the agent execution environment, including:

- **Sandbox management**
- **Agent state management**

All services implement a unified abstract interface called `ServiceWithLifecycleManager` (lifecycle management pattern), which provides standard methods:

- `start()` — Start the service
- `stop()` — Stop the service
- `health()` — Check the health status of the service

## Why Use Services via Adapters?

- **Decoupling**: Agent frameworks don’t need to know the implementation details of underlying services.
- **Cross-framework reuse**: The same service can be integrated into different agent frameworks.
- **Unified lifecycle**: Runner/Engine starts and stops all services in a coordinated manner.
- **Better maintainability**: You can swap service implementations (e.g., switch to database storage) without changing agent business logic.

## Available Services and How to Use Their Adapters

### 1. Sandbox Service (`SandboxService`)

**Sandbox Services** manage and provide sandboxed tool execution environments for different users and sessions.
Sandboxes are organized using a composite key of session ID and user ID, giving each user session an isolated execution environment.

#### Usage in AgentScope

In AgentScope, bind methods from the Sandbox Service to the `ToolKit` module via the `sandbox_tool_adapter`:

```{code-cell}
from agentscope_runtime.engine.services.sandbox import SandboxService

sandboxes = sandbox_service.connect(
    session_id=session_id,
    user_id=user_id,
    sandbox_types=["browser"],
)

toolkit = Toolkit()
for tool in [
    sandboxes[0].browser_navigate,
    sandboxes[0].browser_take_screenshot,
]:
    toolkit.register_tool_function(sandbox_tool_adapter(tool))
```

For more service types and detailed usage, see {doc}`sandbox`.

### 2. State Service (`StateService`)

Allows saving and retrieving the agent's serializable state, preserving context across multiple turns—or even across sessions.

#### Usage in AgentScope

In AgentScope, you don’t need an adapter — directly call `StateService`’s `export_state` and `save_state`:

```{code-cell}
from agentscope_runtime.engine.services.agent_state import InMemoryStateService

state_service = InMemoryStateService()
state = await state_service.export_state(session_id, user_id)
agent.load_state_dict(state)

await state_service.save_state(session_id, user_id, state=agent.state_dict())
```

For more service types and detailed usage, see {doc}`state`.

## Service Interface

All services must implement the `ServiceWithLifecycleManager` abstract class, for example:

```{code-cell}
from agentscope_runtime.engine.services.base import ServiceWithLifecycleManager

class MockService(ServiceWithLifecycleManager):
    def __init__(self, name: str):
        self.name = name
        self.started = False
        self.stopped = False

    async def start(self):
        self.started = True

    async def stop(self):
        self.stopped = True

    async def health(self) -> bool:
        return self.started and not self.stopped
```

Lifecycle Pattern Example:

```{code-cell}
import asyncio
from agentscope_runtime.engine.services.memory import InMemoryMemoryService

async def main():
    memory_service = InMemoryMemoryService()

    await memory_service.start()
    print("Health:", await memory_service.health())

    await memory_service.stop()
```

## ServiceFactory：Unified Service Creation Pattern

In practice, the same type of service (such as `Sandbox`, `State`) may have multiple backend implementations — for example, in-memory, Redis, or database-based.

To make service creation more flexible and configurable, **AgentScope Runtime** provides a general **service factory base class** `ServiceFactory` which supports:

- **Unified registration** of multiple backend constructors (`register_backend`)
- **Environment variable configuration** of service parameters, with `<PREFIX>BACKEND` determining which backend to use
- **`kwargs` overriding** of environment variable configurations (priority: `kwargs` > environment variables)
- **Automatic filtering of invalid parameters** (only parameters accepted by the constructor are passed)
- **Asynchronous instance creation**, suited for services requiring asynchronous initialization via `start()`
- **Image reuse benefit**: within the same runtime image, you can switch backend implementations simply by changing environment variables, without rebuilding the image — making deployment and testing easier

### Example Creation Process

```{code-cell}
# Example: State Service
from agentscope_runtime.engine.services.agent_state import StateServiceFactory

# Use environment variable configuration
# export STATE_BACKEND=redis
# export STATE_REDIS_REDIS_URL="redis://localhost:6379/5"
service = await StateServiceFactory.create()

# Use kwargs to override environment variables
service = await StateServiceFactory.create(
    backend_type="redis",
    redis_url="redis://otherhost:6379/1"
)

# Register a custom backend
from my_backend import PostgresStateService
StateServiceFactory.register_backend("postgres", PostgresStateService)
service = await StateServiceFactory.create(backend_type="postgres")
```

### Common `ServiceFactory` and Default Backends

| ServiceFactory Subclass | Managed Service Type | Environment Variable Prefix | Default Backend | Registered Default Backend Types |
| ----------------------- | -------------------- | --------------------------- | --------------- | -------------------------------- |
| `StateServiceFactory`   | `StateService`       | `STATE_`                    | `in_memory`     | `in_memory`, `redis`             |
| `SandboxServiceFactory` | `SandboxService`     | `SANDBOX_`                  | `default`       | `default`                        |

### Usage Tips

- **Choosing a backend**: Set the `<PREFIX>BACKEND` environment variable to select the implementation

  Example:

  ```bash
  export STATE_BACKEND=redis
  export STATE_REDIS_REDIS_URL="redis://localhost:6379/5"
  ```

- **Parameter priority**: `kwargs` > environment variables

- **Custom backend**: Use `.register_backend("name", constructor)` to register a new implementation
