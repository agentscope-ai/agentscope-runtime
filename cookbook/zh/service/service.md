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

# 服务与适配器

## 概述

AgentScope Runtime 中的服务（`Service`）为智能体运行环境提供核心能力，包括：

- **会话历史管理**
- **记忆存储**
- **沙箱管理**
- **智能体状态管理**

所有服务都实现了统一的抽象接口 `ServiceWithLifecycleManager`（生命周期管理模式），提供标准方法：

- `start()`：启动服务
- `stop()`：停止服务
- `health()`：检查服务健康状态

```{note}
在实际编写智能体应用时，我们通常**不会直接操作这些服务的各种底层方法**，而是通过**框架适配器Adapters**来使用。适配器会：

1. 负责把 Runtime 的服务对象注入到智能体框架的兼容模块中
2. 让框架内的 agent 能无缝调用 Runtime 提供的功能（如会话记忆、工具沙箱等）
3. 保证服务生命周期与 Runner/Engine 一致
```

## 为什么要通过适配器使用服务？

- **解耦**：智能体框架不用直接感知底层服务实现
- **跨框架复用**：相同的服务可以接入不同的智能体框架
- **统一生命周期**：Runner/Engine 统一启动和关闭所有服务
- **增强可维护性**：更换服务实现（如切换为数据库存储）时，无需修改智能体业务代码

## 可用服务及适配器用法

### 1. 会话历史服务（SessionHistoryService）

管理用户-智能体的对话会话，存储并检索会话消息历史。

#### AgentScope用法

在 AgentScope 框架中，通过Runtime的`AgentScopeSessionHistoryMemory`适配器来绑定会话历史服务到`Memory`模块：

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

更多可用服务类型与详细的用法请参见{doc}`session_history`。

### 2. 记忆服务（MemoryService）

`MemoryService` 管理长期记忆存储。在Agent 中，记忆储存终端用户之前的对话。 例如，终端用户可能在之前的对话中提到他们的姓名。 记忆服务通常用来**跨会话**的存储这些信息，以便智能体在下次对话中使用。

#### AgentScope用法

在 AgentScope 框架中，通过Runtime的`AgentScopeLongTermMemory`适配器来绑定会话历史服务到`LongTermMemory`模块：

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

更多可用服务类型与详细的用法请参见{doc}`memory`。

### 3. 沙箱服务（SandboxService）

**沙箱服务** 管理并为不同用户和会话提供沙箱化工具执行环境的访问。沙箱通过会话ID和用户ID的复合键组织，为每个用户会话提供隔离的执行环境。

#### AgentScope用法

在 AgentScope 框架中，通过Runtime的`sandbox_tool_adapter`适配器来绑定沙箱服务提供的沙箱的方法到`ToolKit`模块：

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

更多可用服务类型与详细的用法请参见{doc}`sandbox`。

### 4. StateService

存取智能体的可序列化状态，让智能体在多轮会话甚至跨会话间保持上下文。

#### AgentScope用法

在 AgentScope 框架中，无需通过适配器，直接调用`StateService`的`export_state`和`save_state`来保：

```{code-cell}
from agentscope_runtime.engine.services.agent_state import InMemoryStateService

state_service = InMemoryStateService()
state = await state_service.export_state(session_id, user_id)
agent.load_state_dict(state)

await state_service.save_state(session_id, user_id, state=agent.state_dict())
```

更多可用服务类型与详细的用法请参见{doc}`state`。

## 服务的接口

所有服务必须实现 `ServiceWithLifecycleManager` 抽象类，例如：

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

生命周期模式示例：

```{code-cell}
import asyncio
from agentscope_runtime.engine.services.memory import InMemoryMemoryService

async def main():
    memory_service = InMemoryMemoryService()

    await memory_service.start()
    print("Health:", await memory_service.health())

    await memory_service.stop()
```
