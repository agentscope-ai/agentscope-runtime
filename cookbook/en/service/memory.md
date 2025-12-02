---
jupytext:
  formats: md:myst
  text_representation:
    extension: .md
    format_name: myst
    format_version: 0.13
    jupytext_version: 1.11.5
kernelspec:
  display_name: Python 3.10
  language: python
  name: python3
---

# Memory Service

## Overview

The **Memory Service** is used to manage an agent’s **long-term memory** — storing, retrieving, and managing user conversations and other related information so that the agent can reference knowledge, provide personalized responses, or track tasks over multiple interactions.

The difference from the **Session History Service** is:

- The Session History Service mainly stores **short-term context** (recent conversation turns)
- The Memory Service stores **long-term, cross-session** information, such as user preferences, long-term task plans, or a knowledge base

The core interface of the Memory Service defines four key functions:

- **Add memory**: Store a batch of messages or information in the memory storage
- **Search memory**: Filter relevant information based on the current user query or contextual content
- **List memories**: Support paginated traversal of all memory items for a user
- **Delete memory**: Clear all memory associated with a specified session or user

Similar to the Session History Service, the Memory Service also has multiple backend implementations supporting different storage methods and production requirements.

```{note}
It is recommended to always use the **adapter** to access the Memory Service rather than calling the underlying implementation directly in business logic.
This allows you to:
- Switch storage types without code changes
- Have lifecycle management handled by the framework
- Decouple from business logic
```

## Using the Adapter in AgentScope

In the **AgentScope** framework, you can wrap a backend `MemoryService` with `AgentScopeLongTermMemory` (or other memory adapters) to expose it to the agent’s **LongTermMemory** module:

```{code-cell}
from agentscope_runtime.engine.services.memory import InMemoryMemoryService
from agentscope_runtime.adapters.agentscope.long_term_memory import AgentScopeLongTermMemory

# Choose a backend implementation (InMemory here for local testing)
memory_service = InMemoryMemoryService()

# Wrap with adapter and bind to LongTermMemory module
long_term_memory = AgentScopeLongTermMemory(
    service=memory_service,
    session_id="Test Session",
    user_id="User1",
)

# The Agent can now directly use long_term_memory for cross-session, long-term storage
```

## Available Backend Implementations

While you don’t need to care about the underlying calls when using adapters, it’s important for configuration and selection to understand the characteristics of available implementations:

| Service Type                  | Import Path                                                  | Storage Location         | Persistent?     | Production-ready | Features & Pros/Cons                                         | Suitable Scenarios                                         |
| ----------------------------- | ------------------------------------------------------------ | ------------------------ | --------------- | ---------------- | ------------------------------------------------------------ | ---------------------------------------------------------- |
| **InMemoryMemoryService**     | `from agentscope_runtime.engine.services.memory import InMemoryMemoryService` | Process memory           | ❌ No            | ❌                | Fast, no dependencies; lost when process exits               | Development, debugging, unit testing                       |
| **RedisMemoryService**        | `from agentscope_runtime.engine.services.memory import RedisMemoryService` | Redis in-memory database | ✅ Yes (RDB/AOF) | ✅                | High performance, cross-process sharing, clustering; requires Redis ops | High-performance production, distributed shared memory     |
| **TablestoreMemoryService**   | `from agentscope_runtime.engine.services.memory import TablestoreMemoryService` | Alibaba Cloud Tablestore | ✅ Yes           | ✅                | Massive storage, full-text/vector search, high availability; requires cloud resources | Enterprise-grade production, long-term knowledge archiving |
| **Mem0MemoryService**         | `from agentscope_runtime.engine.services.memory import Mem0MemoryService` | mem0.ai cloud service    | ✅ Yes           | ✅                | Built-in AI semantic memory, external API; requires API key  | Semantic long-term memory, intelligent matching            |
| **ReMePersonalMemoryService** | `from agentscope_runtime.engine.services.memory import ReMePersonalMemoryService` | ReMe cloud service       | ✅ Yes           | ✅                | Long-term personal info storage; requires API key            | Personalized AI, user profiles                             |
| **ReMeTaskMemoryService**     | `from agentscope_runtime.engine.services.memory import ReMeTaskMemoryService` | ReMe cloud service       | ✅ Yes           | ✅                | Task-oriented memory storage; requires API key               | Long-term task management AI                               |

## Switching Between Implementations

Adapters make it very simple to switch storage backends — just replace the `service` instance.

### Example: Switch to Redis

```{code-cell}
from agentscope_runtime.engine.services.memory import RedisMemoryService
from agentscope_runtime.adapters.agentscope.long_term_memory import AgentScopeLongTermMemory

redis_service = RedisMemoryService(redis_url="redis://localhost:6379/0")

long_term_memory = AgentScopeLongTermMemory(
    service=redis_service,
    session_id="ProdSession",
    user_id="UserABC",
)
```

### Example: Switch to Tablestore

```{code-cell}
from agentscope_runtime.engine.services.memory import TablestoreMemoryService
from tablestore import AsyncOTSClient

client = AsyncOTSClient(
    "https://<endpoint>", "<access_key_id>", "<secret>", "<instance_name>"
)
tablestore_service = TablestoreMemoryService(tablestore_client=client)

long_term_memory = AgentScopeLongTermMemory(
    service=tablestore_service,
    session_id="EnterpriseSession",
    user_id="CorpUser",
)
```

## Recommendations

- **Development / Prototyping** → `InMemoryMemoryService`
- **Production with high-performance shared memory** → `RedisMemoryService`
- **Enterprise-grade & large-scale long-term storage** → `TablestoreMemoryService`
- **Semantic query intelligent memory** → `Mem0MemoryService`
- **Tasks management or personalization-focused agents** → `ReMePersonalMemoryService` / `ReMeTaskMemoryService`

------

## Summary

- The Memory Service is the core component for **cross-session, long-term knowledge storage**
- Using the `AgentScopeLongTermMemory` adapter allows business logic decoupling
- Multiple backend implementations can be chosen and switched flexibly based on scenarios
