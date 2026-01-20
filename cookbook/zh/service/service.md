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

- **沙箱管理**
- **智能体状态管理**

所有服务都实现了统一的抽象接口 `ServiceWithLifecycleManager`（生命周期管理模式），提供标准方法：

- `start()`：启动服务
- `stop()`：停止服务
- `health()`：检查服务健康状态

## 为什么要通过适配器使用服务？

- **解耦**：智能体框架不用直接感知底层服务实现
- **跨框架复用**：相同的服务可以接入不同的智能体框架
- **统一生命周期**：Runner/Engine 统一启动和关闭所有服务
- **增强可维护性**：更换服务实现（如切换为数据库存储）时，无需修改智能体业务代码

## 可用服务及适配器用法

### 1. 沙箱服务（SandboxService）

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

### 2. StateService

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

## ServiceFactory：统一的服务创建模式

在实际使用中，同一种服务（如 Sandbox、State）可能会有多种实现后端，例如内存版、Redis、数据库版等。
为了让服务的创建更灵活、可配置，AgentScope Runtime 提供了一个通用的 **服务工厂基类** `ServiceFactory`：

- **统一注册**多种后端构造方法（`register_backend`）
- **支持环境变量配置服务参数**，通过 `<PREFIX>BACKEND` 决定使用哪个后端
- **支持 `kwargs` 覆盖环境变量配置**（优先级：kwargs > 环境变量）
- **自动过滤无效参数**（仅传递构造函数能接收的参数）
- **异步创建实例**，适合需要 `start()` 异步初始化的服务
- **镜像复用优势**：同一运行镜像下，可通过改变环境变量快速切换不同后端实现，无需重新构建镜像，从而便于部署和测试

### 创建流程示例

```{code-cell}
# 以状态服务为例
from agentscope_runtime.engine.services.agent_state import StateServiceFactory

# 使用环境变量配置
# export STATE_BACKEND=redis
# export STATE_REDIS_REDIS_URL="redis://localhost:6379/5"
service = await StateServiceFactory.create()

# 使用 kwargs 覆盖环境变量
service = await StateServiceFactory.create(
    backend_type="redis",
    redis_url="redis://otherhost:6379/1"
)

# 注册自定义后端
from my_backend import PostgresStateService
StateServiceFactory.register_backend("postgres", PostgresStateService)
service = await StateServiceFactory.create(backend_type="postgres")
```

### 常用`ServiceFactory`与默认后端

| ServiceFactory 子类     | 管理的 Service 类型 | 环境变量前缀 | 默认后端    | 已注册的默认后端类型 |
| ----------------------- | ------------------- | ------------ | ----------- | -------------------- |
| `StateServiceFactory`   | `StateService`      | `STATE_`     | `in_memory` | `in_memory`、`redis` |
| `SandboxServiceFactory` | `SandboxService`    | `SANDBOX_`   | `default`   | `default`            |

### 使用提示

- 选择后端：通过设置`<PREFIX>BACKEND`环境变量选择实现

  例如：

  ```bash
  export STATE_BACKEND=redis
  export STATE_REDIS_REDIS_URL="redis://localhost:6379/5"
  ```

- **参数优先级**：`kwargs` > 环境变量

- **自定义后端**：使用 `.register_backend("name", constructor)` 注册新实现
