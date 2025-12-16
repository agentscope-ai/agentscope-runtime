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

# Session History Service

## Overview

The **Session History Service** is used to manage user conversation sessions, providing agents with a structured way to process conversation history and store messages during multi-turn dialogues.
Each session has a unique `session_id` and contains a complete list of messages (either `Message` objects or their dictionary representations) from the start of the session to the current moment.

Typical functions of the Session History Service during agent execution include:

- **Create a session**: When a user initiates a conversation for the first time, create a session for them.
- **Read a session**: Retrieve existing history during the conversation to maintain contextual continuity.
- **Append messages**: Both messages from the agent and the user are appended to the session’s storage.
- **List sessions**: View all sessions belonging to a specific user.
- **Delete a session**: Remove a session according to business needs.

The differences between various implementations of the Session History Service mainly involve **storage location**, **persistence**, **scalability**, and **production readiness**.

```{note}
In most cases, **it is not recommended to call low-level Session History Service classes directly in business code** (such as `InMemorySessionHistoryService`, `RedisSessionHistoryService`, etc.).
It’s better to use **adapters**, because they can:
- Hide implementation details and allow transparent switching of storage types
- Have lifecycle managed uniformly by the Runner/Engine
- Ensure reusability and decoupling across frameworks
```

## Using an Adapter in AgentScope

In the **AgentScope** framework, we use the `AgentScopeSessionHistoryMemory` adapter to bind the underlying Session History Service as the agent’s `Memory` module:

```{code-cell}
from agentscope_runtime.engine.services.session_history import InMemorySessionHistoryService
from agentscope_runtime.adapters.agentscope.memory import AgentScopeSessionHistoryMemory

# Select backend implementation (InMemory here for local testing)
session_history_service = InMemorySessionHistoryService()

# Wrap with adapter and bind to Memory module
memory = AgentScopeSessionHistoryMemory(
    service=session_history_service,
    session_id="TestSession",
    user_id="User1",
)

# The agent can now directly use `memory` to store and access session history
```

## Available Backend Implementation Types

Although you don’t need to worry about low-level calls when using an adapter, you still need to know the characteristics of available implementations for configuration and selection:

| Service Type                        | Import Path                                                  | Storage Location            | Persistent?     | Production Ready? | Features / Pros & Cons                                       | Suitable Scenarios                                       |
| ----------------------------------- | ------------------------------------------------------------ | --------------------------- | --------------- | ----------------- | ------------------------------------------------------------ | -------------------------------------------------------- |
| **InMemorySessionHistoryService**   | `from agentscope_runtime.engine.services.session_history import InMemorySessionHistoryService` | In-process memory           | ❌ No            | ❌ No              | Fast, no dependencies, data lost on exit                     | Development, debugging, unit tests                       |
| **RedisSessionHistoryService**      | `from agentscope_runtime.engine.services.session_history import RedisSessionHistoryService` | Redis in-memory database    | ✅ Yes (RDB/AOF) | ✅ Yes             | Fast, clustering support, cross-process sharing; requires Redis maintenance | High-performance production, distributed session sharing |
| **TablestoreSessionHistoryService** | `from agentscope_runtime.engine.services.session_history import TablestoreSessionHistoryService` | Alibaba Cloud Tablestore DB | ✅ Yes           | ✅ Yes             | Massive storage, high availability, complex indexing; requires cloud service | Enterprise-grade production, long-term archives          |

## Switching Between Implementations

One advantage of the adapter pattern is that you can switch storage backends simply by replacing the `service` instance without changing any business logic:

```{code-cell}
from agentscope_runtime.engine.services.session_history import RedisSessionHistoryService
from agentscope_runtime.adapters.agentscope.memory import AgentScopeSessionHistoryMemory

# Switch to Redis storage
session_history_service = RedisSessionHistoryService(redis_url="redis://localhost:6379/0")

memory = AgentScopeSessionHistoryMemory(
    service=session_history_service,
    session_id="ProdSession",
    user_id="UserABC",
)

# No changes needed in the Agent’s code
```

Example: switching from InMemory to Tablestore:

```{code-cell}
from agentscope_runtime.engine.services.session_history import TablestoreSessionHistoryService
from tablestore import AsyncOTSClient

client = AsyncOTSClient(
    "https://<endpoint>", "<access_key_id>", "<secret>", "<instance_name>"
)
session_history_service = TablestoreSessionHistoryService(tablestore_client=client)

memory = AgentScopeSessionHistoryMemory(
    service=session_history_service,
    session_id="EnterpriseSession",
    user_id="CorpUser",
)
```

## Recommendations for Selection

- **Development / Prototyping**: `InMemorySessionHistoryService`
- **Production with high-performance shared sessions**: `RedisSessionHistoryService` (can be combined with clustering and persistence mechanisms)
- **Enterprise-grade production & massive data storage**: `TablestoreSessionHistoryService` (requires Alibaba Cloud account and resources)

## Summary

- The Session History Service is the core component that enables agents to maintain contextual memory.
- It’s recommended to use it via **adapters** (such as `AgentScopeSessionHistoryMemory`) to ensure decoupling from business logic.
- Choose the backend implementation based on data volume, persistence requirements, and infrastructure conditions.
- Adapters make it extremely easy to swap storage backends without modifying agent logic.
