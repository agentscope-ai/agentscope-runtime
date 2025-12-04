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

# Services

## Overview

Services provide the foundational capabilities that AgentScope Runtime needs to execute agents, including session-history management, memory storage, sandbox management, and state management. Every service implements the `ServiceWithLifecycleManager` interface, which standardizes the lifecycle methods: `start()`, `stop()`, and `health()`.

## Service Interface

All services must implement `ServiceWithLifecycleManager`:

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

### Service Lifecycle

Services follow a standard lifecycle:

```{code-cell}
import asyncio
from agentscope_runtime.engine.services.memory import InMemoryMemoryService

async def main():
    # Create the service
    memory_service = InMemoryMemoryService()

    # Start the service
    await memory_service.start()

    # Check health status
    is_healthy = await memory_service.health()
    print(f"Service health status: {is_healthy}")

    # Stop the service
    await memory_service.stop()

await main()
```

## Available Services

### SessionHistoryService

`SessionHistoryService` manages user conversations and offers structured helpers for storing history and messages. Each session represents the full dialog of a conversation and is uniquely identified by its ID.

#### Service Overview

The session-history service exposes an abstract interface. A simple implementation is `InMemorySessionHistoryService`.

```{code-cell}
from agentscope_runtime.engine.services.session_history import InMemorySessionHistoryService
from agentscope_runtime.engine.schemas.session import Session

# Create a session-history service instance
session_history_service = InMemorySessionHistoryService()
```

#### Core Capabilities

- `create_session`: create a new session
- `get_session`: fetch a session
- `delete_session`: delete a session
- `list_sessions`: list all sessions
- `append_message`: append messages to a history

See {ref}`Session history details <session-history-service>` for more.

### MemoryService

`MemoryService` manages long-term memory. In agent scenarios, memory stores what end users mentioned in previous conversations—such as a user introducing themselves. The service persists this information so an agent can reuse it later.

#### Service Overview

The memory service provides an abstract interface. `InMemoryMemoryService` is the reference implementation.

```{code-cell}
from agentscope_runtime.engine.services.memory import InMemoryMemoryService

# Create and start a memory service
memory_service = InMemoryMemoryService()
```

#### Core Capabilities

- `add_memory`: add memories to the service
- `search_memory`: search memories
- `delete_memory`: delete memories
- `list_memory`: list memories

See {ref}`Memory service details <memory-service>` for a deep dive.

### SandboxService

**SandboxService** manages sandboxed environments and grants controlled access to tool-execution contexts. Sandboxes are keyed by the `(session_id, user_id)` pair and guarantee isolation per user session.

#### Service Overview

SandboxService unifies management across sandbox types, such as browser automation, file systems, and custom executors.

```{code-cell}
from agentscope_runtime.engine.services.sandbox import SandboxService

# Create a sandbox service
sandbox_service = SandboxService()

# Or connect to a remote sandbox cluster
# sandbox_service = SandboxService(
#     base_url="http://sandbox-server:8000",
#     bearer_token="your-auth-token"
# )
```

#### Core Capabilities

##### Connect to Sandboxes

Use `connect` to attach to the sandbox resources required by a user session:

```{code-cell}
# Connect to specific sandbox types
session_id = "session1"
user_id = "user1"
sandbox_types = ["browser", "filesystem"]

sandboxes = sandbox_service.connect(
    session_id=session_id,
    user_id=user_id,
    env_types=sandbox_types
)
```

##### Auto-configure via Tools

SandboxService can infer the required sandbox types from the tools you plan to use:

```{code-cell}
# Connect using tool definitions (automatic sandbox type inference)
from agentscope_runtime.sandbox.tools.filesystem import read_file
from agentscope_runtime.sandbox.tools.browser import browser_navigate

tools = [read_file, browser_navigate]
sandboxes = sandbox_service.connect(
    session_id=session_id,
    user_id=user_id,
    tools=tools,
)

# The service automatically provisions filesystem and browser sandboxes
print(f"Configured {len(sandboxes)} sandboxes")
```

##### Sandbox Reuse

Existing sandboxes are reused efficiently within the same user session:

```{code-cell}
# First call creates new sandboxes
sandboxes1 = sandbox_service.connect(session_id, user_id, env_types=["base"])

# Subsequent calls reuse them
sandboxes2 = sandbox_service.connect(session_id, user_id, env_types=["base"])

# sandboxes1 and sandboxes2 reference the same underlying instances
assert len(sandboxes1) == len(sandboxes2)
```

##### Release Sandboxes

Release sandboxes when they are no longer needed to free resources:

```{code-cell}
# Release sandboxes for a session
success = sandbox_service.release(session_id, user_id)
print(f"Release successful: {success}")

# Sandboxes are cleaned up automatically
```

#### Service Lifecycle

SandboxService follows the standard lifecycle:

```{code-cell}
# Start the service
await sandbox_service.start()

# Check health
is_healthy = await sandbox_service.health()

# Stop the service (releases all sandboxes)
await sandbox_service.stop()
```

See {doc}`sandbox` for details.

### StateService

`StateService` stores agent state per `user_id`, `session_id`, and `round_id`. It supports saving, retrieving, listing, and deleting serialized state snapshots.

#### Service Overview

StateService exposes an abstract interface; `InMemoryStateService` is the reference implementation.

```{code-cell}
from agentscope_runtime.engine.services.agent_state.state_service import InMemoryStateService

# Create and start the state service
state_service = InMemoryStateService()
```

#### Core Capabilities

- `save_state`: store serialized state for a given user/session
- `export_state`: retrieve serialized state data

## Available Memory Services

| Memory Type | Import Statement | Description |
|:-----------:|:-----------------|:------------|
| InMemoryMemoryService | `from agentscope_runtime.engine.services.memory import InMemoryMemoryService` | Ephemeral in-memory storage. |
| RedisMemoryService | `from agentscope_runtime.engine.services.memory import RedisMemoryService` | Redis-backed persistent storage. |
| ReMe.PersonalMemoryService | `from reme_ai.service.personal_memory_service import PersonalMemoryService` | [User guide](https://github.com/modelscope/ReMe). |
| ReMe.TaskMemoryService | `from reme_ai.service.task_memory_service import TaskMemoryService` | [User guide](https://github.com/modelscope/ReMe). |
| Mem0MemoryService | `from agentscope_runtime.engine.services.memory import Mem0MemoryService` | Mem0-based long-term memory. |
| TablestoreMemoryService | `from agentscope_runtime.engine.services.memory import TablestoreMemoryService` | Backed by [tablestore-for-agent-memory](https://github.com/aliyun/alibabacloud-tablestore-for-agent-memory/blob/main/python/docs/knowledge_store_tutorial.ipynb). |

### Descriptions

- **InMemoryMemoryService**: In-memory memory without persistence.
- **RedisMemoryService**: Redis-backed persistent memory.
- **ReMe.PersonalMemoryService**: ReMe’s personalized memory (formerly MemoryScope). It can generate, retrieve, and share tailored memories using LLMs plus vector stores, enabling agents with context and temporal awareness.
- **ReMe.TaskMemoryService**: ReMe’s task-oriented memory that helps orchestrate task-related knowledge. Built on LLMs, it supports flexible CRUD operations for complex task pipelines.
- **Mem0MemoryService**: A Mem0-based intelligent memory service offering long-term storage and retrieval. It supports async operations and automatically extracts critical information from conversations. See the [Mem0 docs](https://docs.mem0.ai/platform/quickstart).
- **TablestoreMemoryService**: A memory service built on Alibaba Cloud Tablestore, a serverless tabular storage optimized for large-scale structured data (IoT, IM, billing, etc.). The Runtime integration relies on [tablestore-for-agent-memory](https://github.com/aliyun/alibabacloud-tablestore-for-agent-memory/blob/main/python/docs/knowledge_store_tutorial.ipynb). Example:

```python
from agentscope_runtime.engine.services.memory import TablestoreMemoryService
from agentscope_runtime.engine.services.utils.tablestore_service_utils import create_tablestore_client
from agentscope_runtime.engine.services.memory.tablestore_memory_service import SearchStrategy

# Full-text search (default)
tablestore_memory_service = TablestoreMemoryService(
    tablestore_client=create_tablestore_client(
        end_point="your_endpoint",
        instance_name="your_instance_name",
        access_key_id="your_access_key_id",
        access_key_secret="your_access_key_secret",
    ),
)

# Vector-search mode (uses DashScopeEmbeddings() by default)
tablestore_memory_service = TablestoreMemoryService(
    tablestore_client=create_tablestore_client(
        end_point="your_endpoint",
        instance_name="your_instance_name",
        access_key_id="your_access_key_id",
        access_key_secret="your_access_key_secret",
    ),
    search_strategy=SearchStrategy.VECTOR,
)
```

(session-history-service)=

## Session-History Service Details

The session-history service manages user conversations and stores messages in a structured format. Each session is represented by a unique ID.

### Session Object Structure

Each session is represented by a `Session` object:

```{code-cell}
from agentscope_runtime.engine.schemas.session import Session
from agentscope_runtime.engine.schemas.agent_schemas import Message, TextContent, Role

# Session object
session_obj = Session(
    id="session_123",
    user_id="user_456",
    messages=[
        Message(role=Role.USER, content=[TextContent(type="text", text="Hello")]),
        Message(role=Role.ASSISTANT, content=[TextContent(type="text", text="Hi there!")]),
    ],
)

print(f"Session ID: {session_obj.id}")
print(f"User ID: {session_obj.user_id}")
print(f"Message count: {len(session_obj.messages)}")
```

### Core Operations

#### Create Sessions

`create_session` creates a new dialog session:

```{code-cell}
import asyncio
from agentscope_runtime.engine.services.session_history import InMemorySessionHistoryService

async def main():
    # Initialize the service
    session_history_service = InMemorySessionHistoryService()
    await session_history_service.start()
    
    # Create a session with an auto-generated ID
    user_id = "test_user"
    session = await session_history_service.create_session(user_id)
    print(f"Created session: {session.id}")
    print(f"User ID: {session.user_id}")
    print(f"Messages count: {len(session.messages)}")

    # Create a session with a custom ID
    custom_session = await session_history_service.create_session(
        user_id,
        session_id="my_custom_session_id",
    )
    print(f"Custom session ID: {custom_session.id}")
    
    await session_history_service.stop()

await main()
```

#### Retrieve Sessions

`get_session` fetches a session by user ID and session ID:

```{code-cell}
import asyncio
from agentscope_runtime.engine.services.session_history import InMemorySessionHistoryService

async def main():
    session_history_service = InMemorySessionHistoryService()
    await session_history_service.start()
    
    user_id = "u1"
    # In the in-memory implementation, missing sessions are created automatically
    retrieved_session = await session_history_service.get_session(user_id, "s1")
    assert retrieved_session is not None
    
    await session_history_service.stop()

await main()
```

#### List Sessions

`list_sessions` enumerates all sessions for a user:

```{code-cell}
import asyncio
from agentscope_runtime.engine.services.session_history import InMemorySessionHistoryService

async def main():
    session_history_service = InMemorySessionHistoryService()
    await session_history_service.start()
    
    user_id = "u_list"
    # Create a few sessions
    session1 = await session_history_service.create_session(user_id)
    session2 = await session_history_service.create_session(user_id)

    # List sessions (history omitted for efficiency)
    listed_sessions = await session_history_service.list_sessions(user_id)
    assert len(listed_sessions) >= 2

    for s in listed_sessions:
        assert s.messages == [], "History is intentionally omitted in list view"
    
    await session_history_service.stop()

await main()
```

#### Append Messages

`append_message` adds messages to the history and accepts both objects and dicts.

##### Dictionary Format

```{code-cell}
import asyncio
from agentscope_runtime.engine.services.session_history import InMemorySessionHistoryService
from agentscope_runtime.engine.schemas.agent_schemas import Message, TextContent

async def main():
    session_history_service = InMemorySessionHistoryService()
    await session_history_service.start()
    
    user_id = "u_append"
    session = await session_history_service.create_session(user_id)

    # Append a single Message
    message1 = Message(role="user", content=[TextContent(type="text", text="Hello, world!")])
    await session_history_service.append_message(session, message1)

    assert len(session.messages) == 1

    # Append multiple messages (mixed formats)
    messages3 = [
        {"role": "user", "content": [{"type": "text", "text": "How are you?"}]},
        Message(role="assistant", content=[TextContent(type="text", text="I am fine, thank you.")]),
    ]
    await session_history_service.append_message(session, messages3)

    assert len(session.messages) == 3
    
    await session_history_service.stop()

await main()
```

#### Delete Sessions

`delete_session` removes a session:

```{code-cell}
import asyncio
from agentscope_runtime.engine.services.session_history import InMemorySessionHistoryService

async def main():
    session_history_service = InMemorySessionHistoryService()
    await session_history_service.start()
    
    user_id = "test_user"
    session_to_delete = await session_history_service.create_session(user_id)
    session_id = session_to_delete.id

    assert await session_history_service.get_session(user_id, session_id) is not None

    await session_history_service.delete_session(user_id, session_id)

    assert await session_history_service.get_session(user_id, session_id) is None

    # No error if the session does not exist
    await session_history_service.delete_session(user_id, "non_existent_id")
    
    await session_history_service.stop()

await main()
```

### Lifecycle

Session-history services follow the standard lifecycle:

```{code-cell}
# Start (optional for InMemorySessionHistoryService)
await session_history_service.start()

# Health check
is_healthy = await session_history_service.health()

# Stop (optional for InMemorySessionHistoryService)
await session_history_service.stop()
```

### Implementation Notes

`InMemorySessionHistoryService` stores data in nested dictionaries:

- Top-level: `{user_id: {session_id: Session}}`
- Each `Session` contains `id`, `user_id`, and `messages`
- If no session ID is provided, a UUID is generated
- Empty or whitespace-only IDs are replaced automatically

`TablestoreSessionHistoryService` persists data in Alibaba Cloud Tablestore:

```python
from agentscope_runtime.engine.services.session_history import TablestoreSessionHistoryService
from agentscope_runtime.engine.services.utils.tablestore_service_utils import create_tablestore_client

tablestore_session_history_service = TablestoreSessionHistoryService(
    tablestore_client=create_tablestore_client(
        end_point="your_endpoint",
        instance_name="your_instance_name",
        access_key_id="your_access_key_id",
        access_key_secret="your_access_key_secret",
    ),
)
```

```{note}
For production, consider extending the `SessionHistoryService` abstract base class to back it with databases or file systems.
```

(memory-service)=

## Memory Service Details

The memory service stores and retrieves long-term memory from databases or in-memory stores. Memories are grouped by user at the top level, optionally subdivided by session IDs.

### Core Operations

#### Add Memory

`add_memory` stores messages for a user, optionally under a session:

```{code-cell}
import asyncio
from agentscope_runtime.engine.services.memory import InMemoryMemoryService
from agentscope_runtime.engine.schemas.agent_schemas import Message, TextContent

async def main():
    memory_service = InMemoryMemoryService()
    await memory_service.start()
    
    user_id = "user1"
    messages = [
        Message(
            role="user",
            content=[TextContent(type="text", text="hello world")]
        )
    ]
    await memory_service.add_memory(user_id, messages)
    
    await memory_service.stop()

await main()
```

#### Search Memory

`search_memory` performs keyword-based search on stored messages. The in-memory implementation ships with a simple keyword search; you can replace it with more advanced algorithms.

```{code-cell}
import asyncio
from agentscope_runtime.engine.services.memory import InMemoryMemoryService
from agentscope_runtime.engine.schemas.agent_schemas import Message, TextContent

async def main():
    memory_service = InMemoryMemoryService()
    await memory_service.start()
    
    user_id = "user1"
    messages = [
        Message(
            role="user",
            content=[TextContent(type="text", text="hello world")]
        )
    ]
    await memory_service.add_memory(user_id, messages)
    
    search_query = [
        Message(
            role="user",
            content=[TextContent(type="text", text="hello")]
        )
    ]
    retrieved = await memory_service.search_memory(user_id, search_query)
    
    await memory_service.stop()

await main()
```

#### List Memory

`list_memory` exposes a paginated listing API:

```{code-cell}
import asyncio
from agentscope_runtime.engine.services.memory import InMemoryMemoryService
from agentscope_runtime.engine.schemas.agent_schemas import Message, TextContent

async def main():
    memory_service = InMemoryMemoryService()
    await memory_service.start()
    
    user_id = "user1"
    messages = [
        Message(
            role="user",
            content=[TextContent(type="text", text="hello world")]
        )
    ]
    await memory_service.add_memory(user_id, messages)
    
    memory_list = await memory_service.list_memory(
        user_id,
        filters={"page_size": 10, "page_num": 1}
    )
    
    await memory_service.stop()

await main()
```

#### Delete Memory

Users can delete memory for a specific session or the entire user:

```{code-cell}
import asyncio
from agentscope_runtime.engine.services.memory import InMemoryMemoryService
from agentscope_runtime.engine.schemas.agent_schemas import Message, TextContent

async def main():
    memory_service = InMemoryMemoryService()
    await memory_service.start()
    
    user_id = "user1"
    session_id = "session1"
    
    messages = [
        Message(
            role="user",
            content=[TextContent(type="text", text="hello world")]
        )
    ]
    await memory_service.add_memory(user_id, messages, session_id=session_id)
    
    # Delete a specific session
    await memory_service.delete_memory(user_id, session_id)

    # Or delete everything for the user
    await memory_service.delete_memory(user_id)
    
    await memory_service.stop()

await main()
```

### Service Lifecycle

#### Lifecycle Management

Memory services share the same lifecycle helpers:

```{code-cell}
import asyncio
from agentscope_runtime.engine.services.memory import InMemoryMemoryService

async def main():
    memory_service = InMemoryMemoryService()

    await memory_service.start()

    is_healthy = await memory_service.health()
    print(f"Service health status: {is_healthy}")

    await memory_service.stop()

await main()
```

#### Implementation Notes

`InMemoryMemoryService` stores data using dictionaries:

- Top-level: `{user_id: {session_id: [messages]}}`
- A default session ID is used when none is provided
- Keyword search is case-insensitive
- Messages remain ordered chronologically per session

```{note}
For advanced needs, extend the `MemoryService` abstract base class to add persistence or vector-database backends.
```

