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

# 服务

## 概述

AgentScope Runtime 中的服务为智能体执行提供基本功能，包括会话历史管理、记忆存储、沙箱管理和状态管理。所有服务都实现了 `ServiceWithLifecycleManager` 接口，该接口提供标准的生命周期管理方法：`start()`、`stop()` 和 `health()`。

## 服务接口

所有服务必须实现 `ServiceWithLifecycleManager` 接口：

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

### 服务生命周期

服务遵循标准的生命周期模式：

```{code-cell}
import asyncio
from agentscope_runtime.engine.services.memory import InMemoryMemoryService

async def main():
    # 创建服务
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

## 可用服务

### SessionHistoryService

`SessionHistoryService` 管理用户的对话会话，提供处理对话历史和消息存储的结构化方式。每个会话包含一个对话的历史记录，并通过其ID唯一标识。

#### 服务概述

会话服务为会话管理提供了抽象接口，具体实现如`InMemorySessionHistoryService`。

```{code-cell}
from agentscope_runtime.engine.services.session_history import InMemorySessionHistoryService
from agentscope_runtime.engine.schemas.session import Session

# 创建会话历史服务实例
session_history_service = InMemorySessionHistoryService()
```

#### 核心功能

- `create_session`：创建新会话
- `get_session`：获取会话
- `delete_session`：删除会话
- `list_sessions`：列出所有会话
- `append_message`：向历史中添加消息

详细信息请参见 {ref}`这里 <session-history-service-zh>`

### MemoryService

`MemoryService` 管理长期记忆存储。在Agent 中，记忆储存终端用户之前的对话。 例如，终端用户可能在之前的对话中提到他们的姓名。 记忆服务会存储这些信息，以便智能体在下次对话中使用。

#### 服务概述

记忆服务为记忆管理提供了抽象接口，具体实现如 `InMemoryMemoryService`。

```{code-cell}
from agentscope_runtime.engine.services.memory import InMemoryMemoryService

# 创建并启动记忆服务
memory_service = InMemoryMemoryService()
```

#### 核心功能

- `add_memory`：向记忆服务添加记忆
- `search_memory`：从记忆服务中搜索记忆
- `delete_memory`：从记忆服务中删除记忆
- `list_memory`：列出所有记忆

详细信息请参见{ref}`这里 <memory-service-zh>`

### SandboxService

**沙箱服务** 管理并为不同用户和会话提供沙箱化工具执行环境的访问。沙箱通过会话ID和用户ID的复合键组织，为每个用户会话提供隔离的执行上下文。

#### 服务概述

沙箱服务为沙箱管理提供统一接口，支持不同类型的沙箱，如代码执行、文件操作和其他专用沙箱。

```{code-cell}
from agentscope_runtime.engine.services.sandbox import SandboxService

# 创建并启动沙箱服务
sandbox_service = SandboxService()

# 或使用远程沙箱服务
# sandbox_service = SandboxService(
#     base_url="http://sandbox-server:8000",
#     bearer_token="your-auth-token"
# )
```

#### 核心功能

##### 连接沙盒

`connect`方法允许您连接到特定用户会话的沙盒：

```{code-cell}
# 连接特定的沙盒类型
session_id = "session1"
user_id = "user1"
sandbox_types = ["browser", "filesystem"]

sandboxes = sandbox_service.connect(
    session_id=session_id,
    user_id=user_id,
    env_types=sandbox_types
)
```

##### 使用工具自动配置

服务可以根据所使用的工具自动确定所需的沙盒类型：

```{code-cell}
# 使用工具连接（自动检测沙盒类型）
from agentscope_runtime.sandbox.tools.filesystem import read_file
from agentscope_runtime.sandbox.tools.browser import browser_navigate

tools = [read_file, browser_navigate]
sandboxes = sandbox_service.connect(session_id=session_id,
    user_id=user_id,
    tools=tools
)

# 服务将自动创建filesystem和browser沙盒
print(f"配置了 {len(sandboxes)}个沙盒")
```

##### 沙盒重用

服务高效地为同一用户会话重用现有沙盒：

```{code-cell}
# 第一次连接创建新沙盒
sandboxes1 = sandbox_service.connect(session_id, user_id, env_types=["base"])

# 第二次连接重用现有沙盒
sandboxes2 = sandbox_service.connect(session_id, user_id, env_types=["base"])

# sandboxes1和sandboxes2引用相同的沙盒实例
assert len(sandboxes1) == len(sandboxes2)
```

##### 释放沙盒

当不再需要沙盒时释放它们以释放资源：

```{code-cell}
# 释放特定用户会话的沙盒
success = sandbox_service.release(session_id, user_id)
print(f"Release successful: {success}")

# 沙盒将被自动清理
```

#### 服务生命周期

沙盒服务遵循标准的生命周期模式：

```{code-cell}
# 启动服务
await sandbox_service.start()

# 检查服务健康状态
is_healthy = await sandbox_service.health()

#停止服务（释放所有沙盒）
await sandbox_service.stop()
```

详细信息请参见 {doc}`sandbox` 。

### StateService

`StateService` 管理智能体状态存储。它按 user_id、session_id 和 round_id 组织存储和管理智能体状态。支持保存、检索、列出和删除状态。

#### 服务概述

状态服务为状态管理提供抽象接口，具体实现如 `InMemoryStateService`。

```{code-cell}
from agentscope_runtime.engine.services.agent_state.state_service import InMemoryStateService

# 创建并启动状态服务
state_service = InMemoryStateService()
```

#### 核心功能

- `save_state`：为特定用户/会话保存序列化状态数据
- `export_state`：检索用户/会话的序列化状态数据

## 可用的记忆服务

|            记忆类型            | 导入语句                                                                                               |                     说明                     |
|:--------------------------:|----------------------------------------------------------------------------------------------------|:------------------------------------------:|
|   InMemoryMemoryService    | `from agentscope_runtime.engine.services.memory import InMemoryMemoryService`              |                                            |
|     RedisMemoryService     | `from agentscope_runtime.engine.services.memory import RedisMemoryService`           |                                            |
| ReMe.PersonalMemoryService | `from reme_ai.service.personal_memory_service import PersonalMemoryService`                        | [用户指南](https://github.com/modelscope/ReMe) |
|   ReMe.TaskMemoryService   | `from reme_ai.service.task_memory_service import TaskMemoryService`                                | [用户指南](https://github.com/modelscope/ReMe) |
| Mem0MemoryService | `from agentscope_runtime.engine.services.memory import Mem0MemoryService`             |                   |
| TablestoreMemoryService | `from agentscope_runtime.engine.services.memory import TablestoreMemoryService` |        通过[tablestore-for-agent-memory](https://github.com/aliyun/alibabacloud-tablestore-for-agent-memory/blob/main/python/docs/knowledge_store_tutorial.ipynb)开发实现                                              |

### 描述
- **InMemoryMemoryService**: 一种内存内记忆服务，无持久化存储。
- **RedisMemoryService**: 利用 Redis 实现持久化存储的记忆服务。
- **ReMe.PersonalMemoryService**: ReMe 的个性化记忆服务（原名 MemoryScope），支持生成、检索和共享定制化记忆。依托LLM、VectorStore，构建具备智能、上下文感知与时序感知的完整记忆系统，可无缝配置与部署强大的 AI 智能体。
- **ReMe.TaskMemoryService**: ReMe 的任务导向型记忆服务，帮助您高效管理与调度任务相关记忆，提升任务执行的准确性与效率。依托LLM，支持在多样化任务场景中灵活创建、检索、更新与删除记忆，助您轻松构建并扩展强大的基于智能体的任务系统。
- **Mem0MemoryService**: 基于 mem0 平台的智能记忆服务，提供长期记忆存储与管理功能。支持异步操作，可自动提取、存储和检索对话中的关键信息，为 AI 智能体提供上下文感知的记忆能力。适用于需要持久化记忆的复杂对话场景和智能体应用。(具体可参考 [mem0 平台文档](https://docs.mem0.ai/platform/quickstart))
- **TablestoreMemoryService**: 基于阿里云表格存储的记忆服务（Tablestore 为海量结构化数据提供 Serverless 表存储服务，并为物联网（IoT）场景深度优化提供一站式 IoTstore 解决方案。它适用于海量账单、即时消息（IM）、物联网（IoT）、车联网、风控和推荐等场景中的结构化数据存储，提供海量数据的低成本存储、毫秒级在线数据查询检索和灵活的数据分析能力）, 通过[tablestore-for-agent-memory](https://github.com/aliyun/alibabacloud-tablestore-for-agent-memory/blob/main/python/docs/knowledge_store_tutorial.ipynb)开发实现。使用示例：
```python
from agentscope_runtime.engine.services.memory import TablestoreMemoryService
from agentscope_runtime.engine.services.utils.tablestore_service_utils import create_tablestore_client
from agentscope_runtime.engine.services.memory.tablestore_memory_service import SearchStrategy

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

### 会话对象结构

每个会话由具有以下结构的`Session` 对象表示：

```{code-cell}
from agentscope_runtime.engine.schemas.session import Session
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
from agentscope_runtime.engine.services.session_history import InMemorySessionHistoryService

async def main():
    # 创建并启动会话历史服务
    session_history_service = InMemorySessionHistoryService()
    await session_history_service.start()

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

    await session_history_service.stop()

await main()
```

#### 检索会话

`get_session`方法通过用户ID和会话ID检索特定会话：

```{code-cell}
import asyncio
from agentscope_runtime.engine.services.session_history import InMemorySessionHistoryService

async def main():
    session_history_service = InMemorySessionHistoryService()
    await session_history_service.start()

    user_id = "u1"
    # 检索现有会话（在内存实现中如果不存在会自动创建）
    retrieved_session = await session_history_service.get_session(user_id, "s1")
    assert retrieved_session is not None

    await session_history_service.stop()

await main()
```

#### 列出会话

`list_sessions` 方法提供用户的所有会话列表：

```{code-cell}
import asyncio
from agentscope_runtime.engine.services.session_history import InMemorySessionHistoryService

async def main():
    session_history_service = InMemorySessionHistoryService()
    await session_history_service.start()

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

    await session_history_service.stop()

await main()
```

#### 添加消息

`append_message` 方法向会话历史添加消息，支持多种消息格式：

##### 使用字典格式

```{code-cell}
import asyncio
from agentscope_runtime.engine.services.session_history import InMemorySessionHistoryService
from agentscope_runtime.engine.schemas.agent_schemas import Message, TextContent

async def main():
    session_history_service = InMemorySessionHistoryService()
    await session_history_service.start()

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

    await session_history_service.stop()

await main()
```

#### 删除会话

`delete_session`方法删除特定会话：

```{code-cell}
import asyncio
from agentscope_runtime.engine.services.session_history import InMemorySessionHistoryService

async def main():
    session_history_service = InMemorySessionHistoryService()
    await session_history_service.start()

    user_id = "test_user"
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

    await session_history_service.stop()

await main()
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
对于生产使用，请考虑通过扩展`SessionHistoryService`抽象基类来实现持久化存储，以支持数据库或文件系统。
```

(memory-service-zh)=

## 记忆服务详细信息

记忆服务设计用于从数据库或内存存储中存储和检索长期记忆。 记忆在顶层按用户ID组织，消息列表作为存储在不同位置的基本值。此外，消息可以按会话ID分组。

### 核心功能

#### 添加记忆

 `add_memory` 方法允许您为特定用户存储消息，可选择性地提供会话ID：

```{code-cell}
import asyncio
from agentscope_runtime.engine.services.memory import InMemoryMemoryService
from agentscope_runtime.engine.schemas.agent_schemas import Message, TextContent

async def main():
    # 创建并启动记忆服务
    memory_service = InMemoryMemoryService()
    await memory_service.start()

    # 不带会话ID添加记忆
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

#### 搜索记忆

`search_memory`方法基于内容关键词搜索消息：

在内存记忆服务中，实现了一个简单的关键词搜索算法， 基于查询从历史消息中搜索相关内容。 其他复杂的搜索算法可以通过实现或重写类来替换简单方法。

用户可以使用消息作为查询来搜索相关内容。

```{code-cell}
import asyncio
from agentscope_runtime.engine.services.memory import InMemoryMemoryService
from agentscope_runtime.engine.schemas.agent_schemas import Message, TextContent

async def main():
    memory_service = InMemoryMemoryService()
    await memory_service.start()

    user_id = "user1"
    # 先添加一些记忆
    messages = [
        Message(
            role="user",
            content=[TextContent(type="text", text="hello world")]
        )
    ]
    await memory_service.add_memory(user_id, messages)

    # 搜索记忆
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

#### 列出记忆

`list_memory`方法提供了一个分页接口来列出记忆，如下所示：

```{code-cell}
import asyncio
from agentscope_runtime.engine.services.memory import InMemoryMemoryService
from agentscope_runtime.engine.schemas.agent_schemas import Message, TextContent

async def main():
    memory_service = InMemoryMemoryService()
    await memory_service.start()

    user_id = "user1"
    # 先添加一些记忆
    messages = [
        Message(
            role="user",
            content=[TextContent(type="text", text="hello world")]
        )
    ]
    await memory_service.add_memory(user_id, messages)

    # List memory with pagination
    memory_list = await memory_service.list_memory(
        user_id,
        filters={"page_size": 10, "page_num": 1}
    )

    await memory_service.stop()

await main()
```

#### 删除记忆

用户可以删除特定会话或整个用户的记忆：

```{code-cell}
import asyncio
from agentscope_runtime.engine.services.memory import InMemoryMemoryService
from agentscope_runtime.engine.schemas.agent_schemas import Message, TextContent

async def main():
    memory_service = InMemoryMemoryService()
    await memory_service.start()

    user_id = "user1"
    session_id = "session1"

    # 先添加一些记忆
    messages = [
        Message(
            role="user",
            content=[TextContent(type="text", text="hello world")]
        )
    ]
    await memory_service.add_memory(user_id, messages, session_id=session_id)

    # 删除特定会话的记忆
    await memory_service.delete_memory(user_id, session_id)

    # 删除用户的所有记忆
    await memory_service.delete_memory(user_id)

    await memory_service.stop()

await main()
```

### 服务生命周期

#### 服务生命周期管理

记忆服务遵循标准的生命周期模式，可以通过`start()`、`stop()`、`health()` 管理：

```{code-cell}
import asyncio
from agentscope_runtime.engine.services.memory import InMemoryMemoryService

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
