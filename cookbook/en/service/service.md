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

- **Session history management**
- **Memory storage**
- **Sandbox management**
- **Agent state management**

All services implement a unified abstract interface called `ServiceWithLifecycleManager` (lifecycle management pattern), which provides standard methods:

- `start()` — Start the service
- `stop()` — Stop the service
- `health()` — Check the health status of the service

```{note}
When building agent applications, we typically **do not directly call the low-level methods** of these services.
Instead, we use **framework adapters**:

1. Adapters inject the Runtime’s service objects into the agent framework’s compatible modules.
2. Agents in the framework can seamlessly call Runtime-provided features (such as session memory, tool sandbox, etc.).
3. Adapters ensure the service lifecycle is consistent with the Runner/Engine.
```

## Why Use Services via Adapters?

- **Decoupling**: Agent frameworks don’t need to know the implementation details of underlying services.
- **Cross-framework reuse**: The same service can be integrated into different agent frameworks.
- **Unified lifecycle**: Runner/Engine starts and stops all services in a coordinated manner.
- **Better maintainability**: You can swap service implementations (e.g., switch to database storage) without changing agent business logic.

## Available Services and How to Use Their Adapters

### 1. Session History Service (`SessionHistoryService`)

Manages user–agent conversation sessions, storing and retrieving past session messages.

#### Usage in AgentScope

In the AgentScope framework, bind the session history service to the `Memory` module via the `AgentScopeSessionHistoryMemory` adapter:

```{code-cell}
from agentscope_runtime.engine.services.session_history import InMemorySessionHistoryService
from agentscope_runtime.adapters.agentscope.memory import AgentScopeSessionHistoryMemory

session_service = InMemorySessionHistoryService()

memory = AgentScopeSessionHistoryMemory(
    service=session_service,
    session_id="Test Session",
    user_id="User1",
)
```

For more service types and detailed usage, see {doc}`session_history`.

### 2. Memory Service (`MemoryService`)

The `MemoryService` manages long-term memory storage.
In agents, long-term memory stores information from previous conversations between the end user and the agent — for example, a user might have told the agent their name earlier.
Memory services are generally used to store such information **across sessions** so the agent can use it in future conversations.

#### Usage in AgentScope

In AgentScope, bind the memory service to the `LongTermMemory` module via the `AgentScopeLongTermMemory` adapter:

```{code-cell}
from agentscope_runtime.engine.services.memory import InMemoryMemoryService
from agentscope_runtime.adapters.agentscope.long_term_memory import AgentScopeLongTermMemory

memory_service = InMemoryMemoryService()

long_term_memory = AgentScopeLongTermMemory(
    service=memory_service,
    session_id="Test Session",
    user_id="User1",
)
```

For more service types and detailed usage, see {doc}`memory`.

### 3. Sandbox Service (`SandboxService`)

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

### 4. State Service (`StateService`)

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
