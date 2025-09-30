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

# Context Manager

## Overview
Context Manager provides a convenient way to manage the context lifecycle.
It consists of:

- a set of context services (session history, memory)
- a `ContextComposer` to orchestrate history and memory updates

## Services
The `services` in context manager are those that are required for the context.
For example, if you want to use the context manager to manage the session history, you need to add the `SessionHistoryService` to the services list.

We provide some basic built-in services for you to use.
And you can also create your own services.

Here are the built-in services:

### SessionHistoryService

`SessionHistoryService` is a base class to manage the session history.
It contains the following methods

- `create_session`: create a new session
- `get_session`: get a session
- `delete_session`: delete a session
- `list_sessions`: list all sessions
- `append_message`: append a message to the history

Since the `SessionHistoryService` is a base class, use a concrete implementation instead.
For example, we provide an `InMemorySessionHistoryService` to store history in memory. For details, see {ref}`here <session-history-service>`

### MemoryService

The `MemoryService` is a basic class to manage the memory.
In Agent, memory stores previous conversation of an end-user.
For example, an end-user may mention their name in a previous conversation.
The memory service will store it so that the agent can use it in the next conversation.

The `MemoryService` contains the following methods:
- `add_memory`: add a memory to the memory service
- `search_memory`: search a memory from the memory service
- `delete_memory`: delete a memory from the memory service
- `list_memory`: list all memories

Like `SessionHistoryService`, prefer using a concrete implementation such as `InMemoryMemoryService`. For details, see {ref}`here <memory-service>`

### RAGService

The `RAGService` is a basic class to provide retrieval augmented generation (RAG) capabilities.
When asked by an end-user, the agent may need to retrieve relevant information from the knowledge base.
The knowledge base can be a database or a collection of documents.
The `RAGService` contains the following methods:
- `retrieve`: retrieve relevant information from the knowledge base.

The `LangChainRAGService` is a concrete implementation of `RAGService` that uses LangChain to retrieve relevant information.
It can be initialized by:
- `vectorstore` the vectorstore to be indexed. Specifically, it can be a `VectorStore` instance of LangChain.
- `embedding` the embedding model to be used for indexing.

Read more about RAGService {ref}`here <rag-service>`

## Life-cycle of a context manager
The context manager can be initialized by two ways:

### Initialize an instance directly
The simplest way is to initialize an instance directly.
```{code-cell}
from agentscope_runtime.engine.services.context_manager import ContextManager
from agentscope_runtime.engine.services.session_history_service import InMemorySessionHistoryService
from agentscope_runtime.engine.services.memory_service import InMemoryMemoryService

session_history_service = InMemorySessionHistoryService()
memory_service = InMemoryMemoryService()
context_manager = ContextManager(
    session_history_service=session_history_service,
    memory_service=memory_service
)

# use the manager
async with context_manager as services:
    session = await services.compose_session(user_id="u1", session_id="s1")
    await services.compose_context(session, request_input=[])
```

### Use the async factory helper
We provide a factory function to create a context manager.
```{code-cell}
from agentscope_runtime.engine.services.context_manager import create_context_manager
from agentscope_runtime.engine.services.session_history_service import InMemorySessionHistoryService
from agentscope_runtime.engine.services.memory_service import InMemoryMemoryService

async with create_context_manager(
    session_history_service=InMemorySessionHistoryService(),
    memory_service=InMemoryMemoryService(),
) as manager:
    session = await manager.compose_session(user_id="u1", session_id="s1")
    await manager.compose_context(session, request_input=[])
```

## ContextComposer
The `ContextComposer` is a class to compose the context.
It will be called by the context manager when the context is created.
The `ContextComposer` contains a static method:
- `compose`: compose the context

It provides a sequential composition method and can be overridden by subclasses.

Pass a custom composer class to `ContextManager` when initializing.

```{code-cell}
from agentscope_runtime.engine.services.context_manager import ContextManager, ContextComposer
from agentscope_runtime.engine.services.session_history_service import InMemorySessionHistoryService
from agentscope_runtime.engine.services.memory_service import InMemoryMemoryService

async with ContextManager(
    session_history_service=InMemorySessionHistoryService(),
    memory_service=InMemoryMemoryService(),
    context_composer_cls=ContextComposer,
) as manager:
    session = await manager.compose_session(user_id="u1", session_id="s1")
    await manager.compose_context(session, request_input=[])
```

## Appending outputs to context

```{code-cell}
from agentscope_runtime.engine.services.context_manager import create_context_manager

async with create_context_manager() as manager:
    session = await manager.compose_session(user_id="u1", session_id="s1")
    await manager.append(session, event_output=[])
```

## Available Memory Services
|         MemoryType         | Import                                                                                             |                       Note                       |
|:--------------------------:|----------------------------------------------------------------------------------------------------|:------------------------------------------------:|
|   InMemoryMemoryService    | `from agentscope_runtime.engine.services.memory_service import InMemoryMemoryService`              |                                                  |
|     RedisMemoryService     | `from agentscope_runtime.engine.services.redis_memory_service import RedisMemoryService`           |                                                  |
| ReMe.PersonalMemoryService | `from reme_ai.service.personal_memory_service import PersonalMemoryService`                        | [User Guide](https://github.com/modelscope/ReMe) |
|   ReMe.TaskMemoryService   | `from reme_ai.service.task_memory_service import TaskMemoryService`                                | [User Guide](https://github.com/modelscope/ReMe) |
| Mem0MemoryService | `from agentscope_runtime.engine.services.mem0_memory_service import Mem0MemoryService`             |                   |
| TablestoreMemoryService | `from agentscope_runtime.engine.services.tablestore_memory_service import TablestoreMemoryService` |        develop by [tablestore-for-agent-memory](https://github.com/aliyun/alibabacloud-tablestore-for-agent-memory/blob/main/python/docs/knowledge_store_tutorial.ipynb)                          |

### Description
- **InMemoryMemoryService**: An in-memory memory service without persistent storage.
- **RedisMemoryService**: A memory service leveraging Redis for persistent storage.
- **ReMe.PersonalMemoryService**: ReMe's personalized memory service (formerly MemoryScope) empowers you to generate, retrieve, and share customized memories. Leveraging advanced LLM, embedding, and vector store technologies, it builds a comprehensive memory system with intelligent, context- and time-aware memory management—seamlessly enabling you to configure and deploy powerful AI agents.
- **ReMe.TaskMemoryService**: ReMe's task-oriented memory service helps you efficiently manage and schedule task-related memories, enhancing both the accuracy and efficiency of task execution. Powered by LLM capabilities, it supports flexible creation, retrieval, update, and deletion of memories across diverse task scenarios—enabling you to effortlessly build and scale robust agent-based task systems.
- **Mem0MemoryService**: An intelligent memory service powered by the mem0 platform, providing long-term memory storage and management capabilities. Supports asynchronous operations and automatically extracts, stores, and retrieves key information from conversations, enabling context-aware memory for AI agents. Ideal for complex conversational scenarios and agent applications requiring persistent memory. (For more details, see [mem0 platform documentation](https://docs.mem0.ai/platform/quickstart))
- **TablestoreMemoryService**: A memory service based on aliyun tablestore (Tablestore provides Serverless table storage services for massive structured data, and provides a one-stop IoTstore solution for deep optimization of IoT scenarios. It is suitable for structured data storage in scenarios such as massive bills, IM messages, IoT, Internet of Vehicles, risk control, and recommendations, and provides low-cost storage of massive data, millisecond-level online data query and retrieval, and flexible data analysis capabilities), develop by [tablestore-for-agent-memory](https://github.com/aliyun/alibabacloud-tablestore-for-agent-memory/blob/main/python/docs/knowledge_store_tutorial.ipynb). Example:
```python
from agentscope_runtime.engine.services.tablestore_memory_service import TablestoreMemoryService
from agentscope_runtime.engine.services.utils.tablestore_service_utils import create_tablestore_client
from agentscope_runtime.engine.services.tablestore_memory_service import SearchStrategy

# create tablestore memory service, default search strategy is full text
tablestore_memory_service = TablestoreMemoryService(
    tablestore_client=create_tablestore_client(
        end_point="your_endpoint",
        instance_name="your_instance_name",
        access_key_id="your_access_key_id",
        access_key_secret="your_access_key_secret",
    ),
)

# Create a tablestore memory service based on vector retrieval, with DashScopeEmbeddings() as the default embedding model
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

## Details about Session History Service

The Session History Service manages conversation sessions for users, providing a structured way to handle conversation history and message storage. Each session contains the history of a conversation and is uniquely identified by its ID.

### Service Overview

The Session Service provides an abstract interface for session management with concrete implementations like `InMemorySessionHistoryService`.

```{code-cell}
from agentscope_runtime.engine.services.session_history_service import InMemorySessionHistoryService, Session

# Create a session service instance
session_history_service = InMemorySessionHistoryService()
```

### Session Object Structure

Each session is represented by a `Session` object with the following structure:

```{code-cell}
from agentscope_runtime.engine.services.session_history_service import Session
from agentscope_runtime.engine.schemas.agent_schemas import Message, TextContent, Role

# Session object structure
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

### Core Functionality

#### Creating Sessions

The `create_session` method creates new conversation sessions for users:

```{code-cell}
import asyncio


async def main():
    # Create a session with auto-generated ID
    user_id = "test_user"
    session = await session_history_service.create_session(user_id)
    print(f"Created session: {session.id}")
    print(f"User ID: {session.user_id}")
    print(f"Messages count: {len(session.messages)}")

    # Create a session with custom ID
    custom_session = await session_history_service.create_session(
        user_id,
        session_id="my_custom_session_id",
    )
    print(f"Custom session ID: {custom_session.id}")


await main()
```

#### Retrieving Sessions

The `get_session` method retrieves specific sessions by user ID and session ID:

```{code-cell}
import asyncio


async def main():
    user_id = "u1"
    # Retrieve an existing session (auto-creates if not exists in in-memory impl)
    retrieved_session = await session_history_service.get_session(user_id, "s1")
    assert retrieved_session is not None


await main()
```

#### Listing Sessions

The `list_sessions` method provides a list of all sessions for a user:

```{code-cell}
import asyncio


async def main():
    user_id = "u_list"
    # Create multiple sessions
    session1 = await session_history_service.create_session(user_id)
    session2 = await session_history_service.create_session(user_id)

    # List all sessions (without message history for efficiency)
    listed_sessions = await session_history_service.list_sessions(user_id)
    assert len(listed_sessions) >= 2

    # Returned sessions don't include message history
    for s in listed_sessions:
        assert s.messages == [], "History should be empty in list view"


await main()
```

#### Appending Messages

The `append_message` method adds messages to session history and supports multiple message formats:

##### Using Dictionary Format

```{code-cell}
import asyncio
from agentscope_runtime.engine.schemas.agent_schemas import Message, TextContent


async def main():
    user_id = "u_append"
    # Create a session and add messages (dict format is also accepted)
    session = await session_history_service.create_session(user_id)

    # Append a single message (Message object)
    message1 = Message(role="user", content=[TextContent(type="text", text="Hello, world!")])
    await session_history_service.append_message(session, message1)

    # Verify message was added
    assert len(session.messages) == 1

    # Append multiple messages at once (mixed formats)
    messages3 = [
        {"role": "user", "content": [{"type": "text", "text": "How are you?"}]},
        Message(role="assistant", content=[TextContent(type="text", text="I am fine, thank you.")]),
    ]
    await session_history_service.append_message(session, messages3)

    # Verify all messages were added
    assert len(session.messages) == 3


await main()
```

##### Using Built-in Message Format

```{code-cell}
from agentscope_runtime.engine.schemas.agent_schemas import Message, TextContent, MessageType, Role

# Create a session
session = await session_history_service.create_session(user_id)

# Add a single message using built-in Message format
message1 = Message(
    type=MessageType.MESSAGE,
    role=Role.USER,
    content=[TextContent(type="text", text="Hello, world!")]
)
await session_history_service.append_message(session, message1)

# Verify the message was added
assert len(session.messages) == 1
# Session stores actual Message objects in memory for the in-memory impl
assert session.messages[0].role == "user"
assert session.messages[0].content[0].text == "Hello, world!"

# Add assistant reply message
message2 = Message(
    type=MessageType.MESSAGE,
    role=Role.ASSISTANT,
    content=[TextContent(type="text", text="Hi there! How can I help you?")]
)
await session_history_service.append_message(session, message2)

# Add multiple built-in Message format messages at once
messages3 = [
    Message(
        type=MessageType.MESSAGE,
        role=Role.USER,
        content=[TextContent(type="text", text="What's the weather like?")]
    ),
    Message(
        type=MessageType.MESSAGE,
        role=Role.ASSISTANT,
        content=[TextContent(type="text", text="I don't have access to real-time weather data.")]
    )
]
await session_history_service.append_message(session, messages3)

# Verify all messages were added
assert len(session.messages) == 4
```

##### Mixed Format Support

```{code-cell}
# Session service supports mixing dictionary and Message objects
session = await session_history_service.create_session(user_id)

# Add dictionary format message
dict_message = {"role": "user", "content": "Hello"}
await session_history_service.append_message(session, dict_message)

# Add Message object
message_obj = Message(
    type=MessageType.MESSAGE,
    role=Role.ASSISTANT,
    content=[TextContent(type="text", text="Hello! How can I assist you?")]
)
await session_history_service.append_message(session, message_obj)

# Verify messages were added correctly
assert len(session.messages) == 2
assert session.messages[0]["role"] == "user"  # Dictionary format
assert session.messages[1]["role"] == "assistant"  # Message object converted to dictionary format
```

#### Deleting Sessions

The `delete_session` method removes specific sessions:

```{code-cell}
# Create and then delete a session
session_to_delete = await session_history_service.create_session(user_id)
session_id = session_to_delete.id

# Verify session exists
assert await session_history_service.get_session(user_id, session_id) is not None

# Delete the session
await session_history_service.delete_session(user_id, session_id)

# Verify session is deleted
assert await session_history_service.get_session(user_id, session_id) is None

# Deleting non-existent sessions doesn't raise errors
await session_history_service.delete_session(user_id, "non_existent_id")
```

### Service Lifecycle

The Session Service follows a simple lifecycle pattern:

```{code-cell}
# Start the service (optional for InMemorySessionHistoryService)
await session_history_service.start()

# Check service health
is_healthy = await session_history_service.health()

# Stop the service (optional for InMemorySessionHistoryService)
await session_history_service.stop()
```

### Implementation Details

The `InMemorySessionHistoryService` stores data in a nested dictionary structure:

+ Top level: `{user_id: {session_id: Session}}`
+ Each Session object contains id, user_id, and messages list
+ Session IDs are auto-generated using UUID if not provided
+ Empty or whitespace-only session IDs are replaced with auto-generated IDs

`TablestoreSessionHistoryService` stores data in aliyun tablestore, example：
```python
from agentscope_runtime.engine.services.tablestore_session_history_service import TablestoreSessionHistoryService
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
For production use, consider implementing persistent storage by extending the `SessionHistoryService` abstract base class to support databases or file systems.
```

(memory-service)=

## Details about Memory Service

The Memory Service is designed to store and retrieve long-term memory from databases or in-memory storage.
Memory is organized by user ID at the top level, with the message list serving as the elemental values stored in different locations. Additionally, messages can be grouped by session ID.

### Service Overview

The Memory Service provides an abstract interface for memory management with concrete implementations like `InMemoryMemoryService`.
The following is an example to initialize an in-memory service:

```{code-cell}
from agentscope_runtime.engine.services.memory_service import InMemoryMemoryService

# Create and start the memory service
memory_service = InMemoryMemoryService()
```

### Core Functionality

#### Adding Memory

The `add_memory` method allows you to store messages for a specific user, optionally providing a session ID:

```{code-cell}
import asyncio
from agentscope_runtime.engine.services.memory_service import InMemoryMemoryService
from agentscope_runtime.engine.schemas.agent_schemas import Message, TextContent

# Add memory without a session ID
user_id = "user1"
messages = [
        Message(
            role="user",
            content=[TextContent(type="text", text="hello world")]
        )
    ]
await memory_service.add_memory(user_id, messages)

```

#### Searching Memory

The `search_memory` method searches for messages based on content keywords:

In the `in-memory` memory service, a simple keyword search algorithm is implemented
to related content based on the query from historical messages.
Other complicated search algorithms could be used to replace the simple method by implementing or overriding the class.

User could use message as a query to search for related content.

```{code-cell}
search_query = [
    Message(
        role="user",
        content=[TextContent(type="text", text="hello")]
    )
]
retrieved = await memory_service.search_memory(user_id, search_query)
```


#### Listing Memory

list memory method provide a paginated interface for listing memory shown below,

```{code-cell}
# List memory with pagination
memory_list = await memory_service.list_memory(
    user_id,
    filters={"page_size": 10, "page_num": 1}
)
```

#### Deleting Memory

Users can delete memory for specific sessions or entire users:

```{code-cell}
# Delete memory for specific session
await memory_service.delete_memory(user_id, session_id)

# Delete all memory for user
await memory_service.delete_memory(user_id)
```


### Service Lifecycle

#### Managing Lifecycle through ContextManager

When using ContextManager, memory service lifecycle is automatically managed:

```{code-cell}
import asyncio
from agentscope_runtime.engine.services.context_manager import create_context_manager
from agentscope_runtime.engine.services.memory_service import InMemoryMemoryService

async def main():
    async with create_context_manager() as context_manager:
        # Register memory service - automatically started
        context_manager.register(InMemoryMemoryService, name="memory")

        # Service is automatically started and ready to use
        memory_service = context_manager.memory

        # Check service health status
        health_status = await context_manager.health_check()
        print(f"Memory service health status: {health_status['memory']}")

        # Use service...

    # When exiting context, service automatically stops and cleans up

await main()
```

#### Service Lifecycle Management

The Memory Service follows a standard lifecycle pattern and can be managed through `start()`, `stop()`, `health()`:

```{code-cell}
import asyncio
from agentscope_runtime.engine.services.memory_service import InMemoryMemoryService

async def main():
    # Create memory service
    memory_service = InMemoryMemoryService()

    # Start service
    await memory_service.start()

    # Check service health
    is_healthy = await memory_service.health()
    print(f"Service health status: {is_healthy}")

    # Stop service
    await memory_service.stop()

await main()
```


#### Implementation Details

The `InMemoryMemoryService` stores data in a dictionary structure:

+ Top level: `{user_id: {session_id: [messages]}}`
+ Default session ID is used when no session is specified
+ Keyword-based search is case-insensitive
+ Messages are stored in chronological order within each session

```{note}
For more advanced memory implementations, consider extending the `MemoryService` abstract base class to support persistent storage or vector databases.
```
