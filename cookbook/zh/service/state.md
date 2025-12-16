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

# 智能体状态服务

## 概述

**智能体状态服务**是用于**存储和管理智能体可序列化状态**的核心组件，它可以让智能体在多轮甚至跨会话的交互中保持上下文信息。
与**会话历史服务**主要保存文本消息不同，**状态服务**更关注保存智能体内部的**结构化可序列化数据**，例如：

- 变量值
- 执行进度
- 工具使用的中间结果
- 环境配置或偏好等

状态服务按照以下维度组织数据：

- `user_id`：区分用户
- `session_id`：区分会话（默认 `"default"`）
- `round_id`：区分会话轮数（可选，如省略则自动生成最新轮数）

在智能体运行过程中的作用：

- **保存状态**（`save_state`）：把某个时刻的智能体状态保存下来
- **恢复状态**（`export_state`）：在下一轮对话或下次会话中恢复之前的状态

```{note}
状态是完全可序列化的 Python dict，通常由智能体的 state_dict() 生成并可直接加载回去 (load_state_dict)，便于封装和跨平台传输。
```

## 在 AgentScope 中的使用方法

与**会话历史服务**不同，**智能体状态服务**在 AgentScope 中通常**无需适配器**。它可以直接调用 `save_state` 和 `export_state` 方法来持久化和加载状态。

```{code-cell}
from agentscope_runtime.engine.services.agent_state import InMemoryStateService

# 初始化服务
state_service = InMemoryStateService()
await state_service.start()

# 假设 agent 有 state_dict 方法
agent_state = agent.state_dict()

# 保存状态（返回 round_id）
round_id = await state_service.save_state(
    user_id="User1",
    session_id="TestSession",
    state=agent_state
)
print(f"State saved in round {round_id}")

# 导出最新状态（或指定 round_id）
loaded_state = await state_service.export_state(
    user_id="User1",
    session_id="TestSession"
)
agent.load_state_dict(loaded_state)

```

## 可选的后端实现类型

与会话历史类似，智能体状态服务也有不同的存储后端实现：

| 服务类型                 | 导入路径                                                     | 存储位置         | 持久化     | 生产可用性 | 特点                                                    | 适用场景                       |
| ------------------------ | ------------------------------------------------------------ | ---------------- | ---------- | ---------- | ------------------------------------------------------- | ------------------------------ |
| **InMemoryStateService** | `from agentscope_runtime.engine.services.agent_state import InMemoryStateService` | 进程内存         | ❌ 无       | ❌          | 简单快速，无需外部依赖，进程结束数据丢失                | 开发调试、单元测试             |
| **RedisStateService**    | `from agentscope_runtime.engine.services.agent_state import RedisStateService` | Redis 内存数据库 | ✅ 可持久化 | ✅          | 支持分布式共享状态，跨进程，Redis 可选持久化（RDB/AOF） | 高性能生产部署、跨进程数据共享 |

## 切换不同实现

由于业务代码对 `StateService` 接口一致，切换后端非常简单，只需替换实例化的类型。

InMemory → Redis：

```{code-cell}
from agentscope_runtime.engine.services.agent_state import RedisStateService

state_service = RedisStateService(redis_url="redis://localhost:6379/0")
await state_service.start()

# 保存状态
await state_service.save_state(user_id="User1", session_id="ProdSession", state=agent.state_dict())

# 导出状态
state = await state_service.export_state(user_id="User1", session_id="ProdSession")
agent.load_state_dict(state)
```

## 选型建议

- **开发阶段、调试或测试**：`InMemoryStateService`，无外部依赖，快速迭代。
- **生产环境、需要跨进程共享状态**：`RedisStateService`，可配合 Redis 持久化和高可用集群。
- **长周期和强一致性、审计**：可考虑自行实现数据库版 `StateService`。

## 小结

- **智能体状态服务**负责保存可序列化的内部状态，区别于会话历史只存消息。
- 支持 `user_id`、`session_id` 和 `round_id` 三维组织数据。
- 在 AgentScope 中通常直接调用，无需适配器。
- 切换存储后端简单，接口定义统一。
- 按需选择 InMemory、Redis 或自行扩展实现。
