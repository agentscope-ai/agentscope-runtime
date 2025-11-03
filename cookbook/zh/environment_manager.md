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

# 环境管理器（Environment Manager）

## 概述

`EnvironmentManager` 通过 `SandboxService` 提供沙箱化环境与工具的生命周期与访问能力。

默认行为会注入一个 `SandboxService` 实例，用于管理环境的创建、连接与释放。

## 基础用法

```{code-cell}
from agentscope_runtime.engine.services.environment_manager import (
    create_environment_manager,
)
from agentscope_runtime.engine.services.sandbox_service import SandboxService

async def quickstart():
    async with create_environment_manager(
        sandbox_service=SandboxService()
    ) as manager:
        boxes = manager.connect_sandbox(
            session_id="s1",
            user_id="u1",
            env_types=[],
            tools=[],
        )
        # 使用 boxes
        manager.release_sandbox(session_id="s1", user_id="u1")
```

未来，`EnvironmentManager` 将不仅支持 `sandbox_service`，也会扩展到其它与环境交互的服务。

**沙盒服务**旨在管理和提供对不同用户和会话的沙盒化工具执行（详见{doc}`sandbox`）沙盒的访问。沙盒通过会话ID和用户ID的复合键进行组织，为每个用户会话提供隔离的执行上下文。该服务支持多种沙盒类型，并可以根据所使用的工具自动配置所需的沙盒。

## 沙盒服务概述

沙盒服务为沙盒管理提供统一接口，支持不同的沙盒类型，如代码执行、文件操作和其他专用沙盒。以下是初始化沙盒服务的示例：

```{code-cell}
from agentscope_runtime.engine.services.sandbox_service import SandboxService

# 创建并启动沙盒服务
sandbox_service = SandboxService()

# 或者使用远程沙盒服务
# sandbox_service = SandboxService(
#     base_url="http://sandbox-server:8000",
#     bearer_token="your-auth-token"
# )
```

### 核心功能

#### 连接沙盒

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

#### 使用工具自动配置

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

#### 沙盒重用

服务高效地为同一用户会话重用现有沙盒：

```{code-cell}
# 第一次连接创建新沙盒
sandboxes1 = sandbox_service.connect(session_id, user_id, env_types=["base"])

# 第二次连接重用现有沙盒
sandboxes2 = sandbox_service.connect(session_id, user_id, env_types=["base"])

# sandboxes1和sandboxes2引用相同的沙盒实例
assert len(sandboxes1) == len(sandboxes2)
```

#### 释放沙盒

当不再需要沙盒时释放它们以释放资源：

```{code-cell}
# 释放特定用户会话的沙盒
success = sandbox_service.release(session_id, user_id)
print(f"Release successful: {success}")

# 沙盒将被自动清理
```

### 服务生命周期

沙盒服务遵循标准的生命周期模式：

```{code-cell}
# 启动服务
await sandbox_service.start()

# 检查服务健康状态
is_healthy = await sandbox_service.health()

#停止服务（释放所有沙盒）
await sandbox_service.stop()
```
