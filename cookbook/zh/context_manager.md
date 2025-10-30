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

# 上下文管理器 (Context Manager)

## 概述

上下文管理器提供了一种方便的方式来管理上下文生命周期。 它包含：

- 一组上下文服务（会话历史、记忆）
- 一个`ContextComposer`来编排历史和记忆更新

## 服务 (Services)

上下文管理器中的`services` 是上下文所需的服务。 例如，如果你想使用上下文管理器来管理会话历史，你需要将 `SessionHistoryService` 添加到服务列表中。

我们提供了一些基本的内置服务供你使用，你也可以创建自己的服务。

以下是内置服务：

### SessionHistoryService

`SessionHistoryService` 是管理会话历史的基础类。 它包含以下方法：

- `create_session`：创建新会话
- `get_session`：获取会话
- `delete_session`：删除会话
- `list_sessions`：列出所有会话
- `append_message`：向历史中添加消息

由于`SessionHistoryService`是基础类，请使用具体的实现。 例如，我们提供了 `InMemorySessionHistoryService` 来在内存中存储历史。详细信息请参见 {ref}`这里 <session-history-service-zh>`

### MemoryService

`MemoryService`是管理记忆的基础类。 在Agent 中，记忆储终端用户之前的对话。 例如，终端用户可能在之前的对话中提到他们的姓名。 记忆服务会存储这些信息，以便智能体在下次对话中使用。

 `MemoryService` 包含以下方法：

- `add_memory`：向记忆服务添加记忆
- `search_memory`：从记忆服务中搜索记忆
- `delete_memory`：从记忆服务中删除记忆
- `list_memory`：列出所有记忆

与 `SessionHistoryService`一样，优先使用具体实现，如`InMemoryMemoryService`。详细信息请参见{ref}`这里 <memory-service-zh>`

### RAGService
`RAGService` 是一个基本的类，用于提供检索增强生成（RAG）功能。当最终用户提出请求时，代理可能需要从知识库中检索相关信息。知识库可以是数据库或文档集合。`RAGService` 包含以下方法：
- `retrieve`：从知识库中检索相关信息。

`LangChainRAGService` 是 `RAGService` 的具体实现，它使用 LangChain 来检索相关信息。可以通过以下方式初始化：
- `vectorstore`：要索引的向量存储。具体来说，它可以是 LangChain 的 `VectorStore` 实例。
- `embedding`：用于索引的嵌入模型。

阅读 {ref}`RAGService <rag-service-zh>` 获取更多信息。

## 上下文管理器的生命周期

上下文管理器可以通过两种方式初始化：

### 直接初始化实例

最简单的方式是直接初始化实例。

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

# 使用管理器
async with context_manager as services:
    session = await services.compose_session(user_id="u1", session_id="s1")
    await services.compose_context(session, request_input=[])
```

### 使用异步工厂助手

我们提供了一个工厂函数来创建上下文管理器。

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

 `ContextComposer` 是用于组合上下文的类。 它将在上下文管理器创建上下文时被调用。`ContextComposer` 包含一个静态方法：

- `compose`: 组合上下文

它提供了一个顺序组合方法，可以被子类重写。

在初始化时向 `ContextManager` 传递自定义组合器类。

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

## 向上下文添加输出

```{code-cell}
from agentscope_runtime.engine.services.context_manager import create_context_manager

async with create_context_manager() as manager:
    session = await manager.compose_session(user_id="u1", session_id="s1")
    await manager.append(session, event_output=[])
```

## 可用的记忆服务
|            记忆类型            | 导入语句                                                                                               |                     说明                     |
|:--------------------------:|----------------------------------------------------------------------------------------------------|:------------------------------------------:|
|   InMemoryMemoryService    | `from agentscope_runtime.engine.services.memory_service import InMemoryMemoryService`              |                                            |
|     RedisMemoryService     | `from agentscope_runtime.engine.services.redis_memory_service import RedisMemoryService`           |                                            |
| ReMe.PersonalMemoryService | `from reme_ai.service.personal_memory_service import PersonalMemoryService`                        | [用户指南](https://github.com/modelscope/ReMe) |
|   ReMe.TaskMemoryService   | `from reme_ai.service.task_memory_service import TaskMemoryService`                                | [用户指南](https://github.com/modelscope/ReMe) |
| Mem0MemoryService | `from agentscope_runtime.engine.services.mem0_memory_service import Mem0MemoryService`             |                   |
| TablestoreMemoryService | `from agentscope_runtime.engine.services.tablestore_memory_service import TablestoreMemoryService` |        通过[tablestore-for-agent-memory](https://github.com/aliyun/alibabacloud-tablestore-for-agent-memory/blob/main/python/docs/knowledge_store_tutorial.ipynb)开发实现                                              |

### 描述
- **InMemoryMemoryService**: 一种内存内记忆服务，无持久化存储。
- **RedisMemoryService**: 利用 Redis 实现持久化存储的记忆服务。
- **ReMe.PersonalMemoryService**: ReMe 的个性化记忆服务（原名 MemoryScope），支持生成、检索和共享定制化记忆。依托LLM、VectorStore，构建具备智能、上下文感知与时序感知的完整记忆系统，可无缝配置与部署强大的 AI 智能体。
- **ReMe.TaskMemoryService**: ReMe 的任务导向型记忆服务，帮助您高效管理与调度任务相关记忆，提升任务执行的准确性与效率。依托LLM，支持在多样化任务场景中灵活创建、检索、更新与删除记忆，助您轻松构建并扩展强大的基于智能体的任务系统。
- **Mem0MemoryService**: 基于 mem0 平台的智能记忆服务，提供长期记忆存储与管理功能。支持异步操作，可自动提取、存储和检索对话中的关键信息，为 AI 智能体提供上下文感知的记忆能力。适用于需要持久化记忆的复杂对话场景和智能体应用。(具体可参考 [mem0 平台文档](https://docs.mem0.ai/platform/quickstart))
- **TablestoreMemoryService**: 基于阿里云表格存储的记忆服务（Tablestore 为海量结构化数据提供 Serverless 表存储服务，并为物联网（IoT）场景深度优化提供一站式 IoTstore 解决方案。它适用于海量账单、即时消息（IM）、物联网（IoT）、车联网、风控和推荐等场景中的结构化数据存储，提供海量数据的低成本存储、毫秒级在线数据查询检索和灵活的数据分析能力）, 通过[tablestore-for-agent-memory](https://github.com/aliyun/alibabacloud-tablestore-for-agent-memory/blob/main/python/docs/knowledge_store_tutorial.ipynb)开发实现。使用示例：
```python
from agentscope_runtime.engine.services.tablestore_memory_service import TablestoreMemoryService
from agentscope_runtime.engine.services.utils.tablestore_service_utils import create_tablestore_client
from agentscope_runtime.engine.services.tablestore_memory_service import SearchStrategy

# 创建表格存储记忆服务，默认使用全文检索
tablestore_memory_service = TablestoreMemoryService(
    tablestore_client=create_tablestore_client(
        end_point="your_endpoint",
        instance_name="your_instance_name",
        access_key_id="your_access_key_id",
        access_key_secret="your_access_key_secret",
    ),
)

# 创建基于向量检索的表格存储记忆服务，编码模型默认使用DashScopeEmbeddings()
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

(session-history-service-zh)=

## 会话历史服务详细信息

会话历史服务管理用户的对话会话，提供处理对话历史和消息存储的结构化方式。每个会话包含一个对话的历史记录，并通过其ID唯一标识。

### 服务概述

会话服务为会话管理提供了抽象接口，具体实现如`InMemorySessionHistoryService`。

```{code-cell}
from agentscope_runtime.engine.services.session_history_service import InMemorySessionHistoryService, Session

# 创建会话历史服务实例
session_history_service = InMemorySessionHistoryService()
```

### 会话对象结构

每个会话由具有以下结构的`Session` 对象表示：

```{code-cell}
from agentscope_runtime.engine.services.session_history_service import Session
from agentscope_runtime.engine.schemas.agent_schemas import Message, TextContent, Role

# 会话对象结构
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

### 核心功能

#### 创建会话

 `create_session` 方法为用户创建新的对话会话：

```{code-cell}
import asyncio


async def main():
    # 创建带自动生成ID的会话
    user_id = "test_user"
    session = await session_history_service.create_session(user_id)
    print(f"Created session: {session.id}")
    print(f"User ID: {session.user_id}")
    print(f"Messages count: {len(session.messages)}")

    # 创建带自定义ID的会话
    custom_session = await session_history_service.create_session(
        user_id,
        session_id="my_custom_session_id",
    )
    print(f"Custom session ID: {custom_session.id}")


await main()
```

#### 检索会话

`get_session`方法通过用户ID和会话ID检索特定会话：

```{code-cell}
import asyncio


async def main():
    user_id = "u1"
    # 检索现有会话（在内存实现中如果不存在会自动创建）
    retrieved_session = await session_history_service.get_session(user_id, "s1")
    assert retrieved_session is not None


await main()
```

#### 列出会话

`list_sessions` 方法提供用户的所有会话列表：

```{code-cell}
import asyncio


async def main():
    user_id = "u_list"
    # 创建多个会话
    session1 = await session_history_service.create_session(user_id)
    session2 = await session_history_service.create_session(user_id)

    # 列出所有会话（为了效率不包含消息历史）
    listed_sessions = await session_history_service.list_sessions(user_id)
    assert len(listed_sessions) >= 2

    # 返回的会话不包含消息历史
    for s in listed_sessions:
        assert s.messages == [], "History should be empty in list view"


await main()
```

#### 添加消息

`append_message` 方法向会话历史添加消息，支持多种消息格式：

##### 使用字典格式

```{code-cell}
import asyncio
from agentscope_runtime.engine.schemas.agent_schemas import Message, TextContent


async def main():
    user_id = "u_append"
    # 创建会话并添加消息（也接受字典格式）
    session = await session_history_service.create_session(user_id)

    # 添加单个消息（Message对象）
    message1 = Message(role="user", content=[TextContent(type="text", text="Hello, world!")])
    await session_history_service.append_message(session, message1)

    # 验证消息已添加
    assert len(session.messages) == 1

    # 一次添加多个消息（混合格式）
    messages3 = [
        {"role": "user", "content": [{"type": "text", "text": "How are you?"}]},
        Message(role="assistant", content=[TextContent(type="text", text="I am fine, thank you.")]),
    ]
    await session_history_service.append_message(session, messages3)

    # Verify all messages were added
    assert len(session.messages) == 3


await main()
```

##### 使用内置消息格式

```{code-cell}
from agentscope_runtime.engine.schemas.agent_schemas import Message, TextContent, MessageType, Role

# 创建会话
user_id = "u_append"
session = await session_history_service.create_session(user_id)

# 使用内置Message格式添加单个消息
message1 = Message(
    type=MessageType.MESSAGE,
    role=Role.USER,
    content=[TextContent(type="text", text="Hello, world!")]
)
await session_history_service.append_message(session, message1)

# 验证消息已添加
assert len(session.messages) == 1
# Session stores actual Message objects in memory for the in-memory impl
assert session.messages[0].role == "user"
assert session.messages[0].content[0].text == "Hello, world!"

# 添加助手回复消息
message2 = Message(
    type=MessageType.MESSAGE,
    role=Role.ASSISTANT,
    content=[TextContent(type="text", text="Hi there! How can I help you?")]
)
await session_history_service.append_message(session, message2)

# 一次添加多个内置Message格式消息
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

# 验证所有消息都已添加
assert len(session.messages) == 4
```

##### 混合格式支持

```{code-cell}
# 会话服务支持混合字典和Message对象
session = await session_history_service.create_session(user_id)

# 添加字典格式消息
dict_message = {"role": "user", "content": "Hello"}
await session_history_service.append_message(session, dict_message)

# 添加Message对象
message_obj = Message(
    type=MessageType.MESSAGE,
    role=Role.ASSISTANT,
    content=[TextContent(type="text", text="Hello! How can I assist you?")]
)
await session_history_service.append_message(session, message_obj)

# 验证消息正确添加
assert len(session.messages) == 2
assert session.messages[0]["role"] == "user"  # Dictionary format
assert session.messages[1]["role"] == "assistant"  # Message object converted to dictionary format
```

#### 删除会话

`delete_session`方法删除特定会话：

```{code-cell}
# 创建然后删除会话
session_to_delete = await session_history_service.create_session(user_id)
session_id = session_to_delete.id

# 验证会话存在
assert await session_history_service.get_session(user_id, session_id) is not None

# 删除会话
await session_history_service.delete_session(user_id, session_id)

# 验证会话已删除
assert await session_history_service.get_session(user_id, session_id) is None

# 删除不存在的会话不会引发错误
await session_history_service.delete_session(user_id, "non_existent_id")
```

### 服务生命周期

会话服务遵循简单的生命周期模式：

```{code-cell}
# 启动服务（对于InMemorySessionHistoryService是可选的）
await session_history_service.start()

# 检查服务健康状态
is_healthy = await session_history_service.health()

# 停止服务（对于InMemorySessionHistoryService是可选的）
await session_history_service.stop()
```

### 实现细节

`InMemorySessionHistoryService` 将数据存储在嵌套字典结构中：

+ 顶层: `{user_id: {session_id: Session}}`
+ 每个Session对象包含id、user_id和messages列表
+ 如果未提供会话ID，会使用UUID自动生成
+ 空的或仅包含空格的会话ID会被替换为自动生成的ID

`TablestoreSessionHistoryService`将数据存储在阿里云表格存储，使用示例：
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
对于生产使用，请考虑通过扩展`SessionHistoryService`抽象基类来实现持久化存储，以支持数据库或文件系统。
```

(memory-service-zh)=

## 记忆服务详细信息

记忆服务设计用于从数据库或内存存储中存储和检索长期记忆。 记忆在顶层按用户ID组织，消息列表作为存储在不同位置的基本值。此外，消息可以按会话ID分组。

### 服务概述

记忆服务为记忆管理提供了抽象接口，具体实现如 `InMemoryMemoryService`。 以下是初始化记忆服务的示例：

```{code-cell}
from agentscope_runtime.engine.services.memory_service import InMemoryMemoryService

# 创建并启动记忆服务
memory_service = InMemoryMemoryService()
```

### 核心功能

#### 添加记忆

 `add_memory` 方法允许您为特定用户存储消息，可选择性地提供会话ID：

```{code-cell}
import asyncio
from agentscope_runtime.engine.services.memory_service import InMemoryMemoryService
from agentscope_runtime.engine.schemas.agent_schemas import Message, TextContent

# 不带会话ID添加记忆
user_id = "user1"
messages = [
        Message(
            role="user",
            content=[TextContent(type="text", text="hello world")]
        )
    ]
await memory_service.add_memory(user_id, messages)
```

#### 搜索记忆

`search_memory`方法基于内容关键词搜索消息：

在内存记忆服务中，实现了一个简单的关键词搜索算法， 基于查询从历史消息中搜索相关内容。 其他复杂的搜索算法可以通过实现或重写类来替换简单方法。

用户可以使用消息作为查询来搜索相关内容。

```{code-cell}
search_query = [
    Message(
        role="user",
        content=[TextContent(type="text", text="hello")]
    )
]
retrieved = await memory_service.search_memory(user_id, search_query)
```

#### 列出记忆

`list_memory`方法提供了一个分页接口来列出记忆，如下所示：

```{code-cell}
# List memory with pagination
memory_list = await memory_service.list_memory(
    user_id,
    filters={"page_size": 10, "page_num": 1}
)
```

#### 删除记忆

用户可以删除特定会话或整个用户的记忆：

```{code-cell}
# 删除特定会话的记忆
await memory_service.delete_memory(user_id, session_id)

# 删除用户的所有记忆
await memory_service.delete_memory(user_id)
```

### 服务生命周期

#### 通过ContextManager管理生命周期

使用`ContextManager`时，记忆服务生命周期会自动管理：

```{code-cell}
import asyncio
from agentscope_runtime.engine.services.context_manager import create_context_manager
from agentscope_runtime.engine.services.memory_service import InMemoryMemoryService

async def main():
    async with create_context_manager() as context_manager:
        # 注册记忆服务 - 自动启动
        context_manager.register(InMemoryMemoryService, name="memory")

        # 服务自动启动并准备使用
        memory_service = context_manager.memory

        # 检查服务健康状态
        health_status = await context_manager.health_check()
        print(f"Memory service health status: {health_status['memory']}")

        # 使用服务...

    # 退出上下文时，服务自动停止并清理

await main()
```

#### 服务生命周期管理

记忆服务遵循标准的生命周期模式，可以通过`start()`、`stop()`、`health()` 管理：

```{code-cell}
import asyncio
from agentscope_runtime.engine.services.memory_service import InMemoryMemoryService

async def main():
    # 创建记忆服务
    memory_service = InMemoryMemoryService()

    # 启动服务
    await memory_service.start()

    # 检查服务健康状态
    is_healthy = await memory_service.health()
    print(f"Service health status: {is_healthy}")

    # 停止服务
    await memory_service.stop()

await main()
```

#### 实现细节

`InMemoryMemoryService` 将数据存储在字典结构中：

+ 顶层：`{user_id: {session_id: [messages]}}`
+ 未指定会话时使用默认会话ID
+ 基于关键词的搜索不区分大小写
+ 消息在每个会话中按时间顺序存储

```{note}
对于更高级的记忆实现，请考虑扩展 `MemoryService` 抽象基类以支持持久化存储或向量数据库。
```
