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

# 会话历史服务

## 概述

**会话历史服务**用于管理用户的对话会话，为智能体在多轮对话中提供处理对话历史和消息存储的结构化方式。每个会话（Session）都有一个唯一的 `session_id`，包含该会话从开始到当前的全部消息列表（消息对象 `Message` 或其字典表示）。

在智能体运行过程中，会话历史服务的典型作用包括：

- **新建会话**：在用户首次发起对话时，为其创建一个会话。
- **读取会话**：在对话过程中获取已有的历史记录，保证上下文连贯。
- **追加消息**：智能体或用户发送的消息都会追加到会话的存储中。
- **列出会话**：查看某个用户的所有会话。
- **删除会话**：根据业务需求清理某个会话。

会话历史服务在不同实现中，差异主要体现在**存储位置**、**是否持久化**、**可扩展性**以及**生产可用性**。

```{note}
在大多数情况下，**不建议在业务代码中直接调用底层会话历史服务类**（如 `InMemorySessionHistoryService`、`RedisSessionHistoryService` 等）。
更推荐通过 **适配器（adapter）** 的方式使用，这样可以：
- 屏蔽底层实现细节，业务无感知切换存储类型
- 统一由 Runner/Engine 管理生命周期
- 保证跨框架复用与解耦
```

## 在 AgentScope 中使用 Adapter

在 **AgentScope** 框架中，我们使用 `AgentScopeSessionHistoryMemory` 适配器，将底层会话历史服务绑定为智能体的 `Memory` 模块：

```{code-cell}
from agentscope_runtime.engine.services.session_history import InMemorySessionHistoryService
from agentscope_runtime.adapters.agentscope.memory import AgentScopeSessionHistoryMemory

# 选择后端实现（此例为 InMemory，方便本地测试）
session_history_service = InMemorySessionHistoryService()

# 用 adapter 包装，绑定到 Memory 模块
memory = AgentScopeSessionHistoryMemory(
    service=session_history_service,
    session_id="TestSession",
    user_id="User1",
)

# 之后在 Agent 内即可直接使用 memory 存取会话历史
```

## 可选的后端实现类型

虽然通过适配器使用时无需关心底层调用，但为了配置和选型，需要了解可用实现类型的特点：

| 服务类型                            | 导入路径                                                     | 存储位置                  | 持久化          | 生产可用性 | 特点 & 优缺点                            | 适用场景                       |
| ----------------------------------- | ------------------------------------------------------------ | ------------------------- | --------------- | ---------- | ---------------------------------------- | ------------------------------ |
| **InMemorySessionHistoryService**   | `from agentscope_runtime.engine.services.session_history import InMemorySessionHistoryService` | 进程内存                  | ❌ 否            | ❌          | 快速、无依赖，退出即丢失                 | 开发调试、单元测试             |
| **RedisSessionHistoryService**      | `from agentscope_runtime.engine.services.session_history import RedisSessionHistoryService` | Redis 内存数据库          | ✅ 是（RDB/AOF） | ✅          | 快速、支持集群、跨进程共享；需运维 Redis | 高性能生产部署、分布式会话共享 |
| **TablestoreSessionHistoryService** | `from agentscope_runtime.engine.services.session_history import TablestoreSessionHistoryService` | 阿里云 Tablestore云数据库 | ✅ 是            | ✅          | 海量存储、高可用、复杂索引查询；需云服务 | 企业级生产、长期历史存档       |

## 切换不同实现的方法

adapter 的好处是，你只需替换传入的 `service` 实例，就能切换存储后端，而不用修改业务逻辑：

```{code-cell}
from agentscope_runtime.engine.services.session_history import RedisSessionHistoryService
from agentscope_runtime.adapters.agentscope.memory import AgentScopeSessionHistoryMemory

# 切换为 Redis 存储
session_history_service = RedisSessionHistoryService(redis_url="redis://localhost:6379/0")

memory = AgentScopeSessionHistoryMemory(
    service=session_history_service,
    session_id="ProdSession",
    user_id="UserABC",
)

# Agent 中代码无需变动
```

例如，将 InMemory 切换为 Tablestore：

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

## 选型建议

- **开发调试/快速原型**：`InMemorySessionHistoryService`
- **生产环境中高性能共享会话**：`RedisSessionHistoryService`（可配合 Redis 集群和持久化机制）
- **企业级生产 & 海量数据存储**：`TablestoreSessionHistoryService`（需要阿里云账号与资源）

## 小结

- 会话历史服务是智能体保持上下文记忆的核心组件
- 推荐通过 **适配器**（如 `AgentScopeSessionHistoryMemory`）来使用，实现与业务逻辑解耦
- 选型时根据数据量、持久化要求和运维条件选择后端实现
- adapter 让存储后端的替换变得非常简单，无需修改智能体逻辑
