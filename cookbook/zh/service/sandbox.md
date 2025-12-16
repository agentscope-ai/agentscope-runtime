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

# 沙箱服务

## 概述

**沙箱服务**用于为不同用户和会话提供隔离的**工具执行环境**（sandbox），让智能体可以在受控的安全环境中使用工具（如浏览器、代码执行器等）。关于沙箱，请参考{doc}`../sandbox/sandbox`

在智能体运行过程中，沙箱服务的典型作用包括：

- **创建执行环境**：为一个新的用户/会话生成对应的沙箱实例（如浏览器沙箱）。
- **连接已有环境**：在对话多轮执行过程中，智能体连接到之前的沙箱继续操作。
- **工具调用**：提供可调用的方法（如 `browser_navigate`、`browser_take_screenshot` 等），可在 Agent 内注册为工具。
- **释放环境**：会话结束或需求变化时，释放对应环境资源。
- **多类型支持**：支持不同类型的沙箱（`BASE`、`BROWSER`、`CODE`、`AGENTBAY` 等）。

沙箱服务在不同实现中，差异主要体现在：
**运行模式**（嵌入式/远程）、**支持的类型**、**管理方式**以及**可扩展性**。

```{note}
在业务代码中，不建议直接编写沙箱服务与 `SandboxManager` 的底层管理逻辑。

更推荐 **通过适配器（adapter）把沙箱方法绑定到智能体框架的工具模块**：
- 屏蔽底层沙箱 API 细节
- 由 Runner/Engine 统一管理生命周期
- 保证切换运行模式或沙箱类型时不影响业务逻辑
```

## 在 AgentScope 中使用 Adapter

在 **AgentScope** 框架中，我们可用 `sandbox_tool_adapter` 将沙箱方法包装成 **工具函数**，并注册到 Agent 的 `Toolkit` 中：

```{code-cell}
from agentscope_runtime.engine.services.sandbox import SandboxService
from agentscope_runtime.adapters.agentscope.tools import sandbox_tool_adapter
from agentscope import Toolkit

# 1. 启动服务（通常由 Runner/Engine 托管）
sandbox_service = SandboxService()
await sandbox_service.start()

# 2. 连接或创建沙箱（此处创建浏览器类型）
sandboxes = sandbox_service.connect(
    session_id="TestSession",
    user_id="User1",
    sandbox_types=["browser"],
)

# 3. 获取工具方法并注册到 Agent 的 Toolkit
toolkit = Toolkit()
for tool in [
    sandboxes[0].browser_navigate,
    sandboxes[0].browser_take_screenshot,
]:
    toolkit.register_tool_function(sandbox_tool_adapter(tool))

# 此后，Agent 即可调用这些工具在沙箱中进行安全操作
```

## 可选运行模式与类型

### 1. **嵌入式模式（Embedded Mode）**

- **特点**：沙箱管理器与 AgentScope Runtime 在同一进程中运行。
- **配置**：`base_url=None`
- **优点**：部署简单，无需外部 API；适合本地开发和单机测试。
- **缺点**：进程退出则环境释放；不适合分布式部署。

### 2. **远程 API 模式**

- **特点**：通过沙箱管理 API（`SandboxManager`）连接远程沙箱实例。
- **配置**：`base_url="http://host:port"`, `bearer_token="..."`
- **优点**：可跨进程/跨机器共享环境，支持分布式扩展。
- **缺点**：需要部署和运维远程沙箱管理服务。

### 支持的沙箱类型

| 类型值       | 功能描述                     | 常见用途示例                              |
| ------------ | ---------------------------- | ----------------------------------------- |
| `DUMMY`      | 空实现/占位沙箱              | 测试流程，模拟沙箱接口但不执行实际操作    |
| `BASE`       | 基础沙箱环境                 | 通用工具运行环境                          |
| `BROWSER`    | 浏览器沙箱                   | 网页导航、截图、数据抓取                  |
| `FILESYSTEM` | 文件系统沙箱                 | 在安全隔离的文件系统中读写文件            |
| `GUI`        | 图形界面沙箱                 | 与 GUI 应用交互（点击、输入、截屏）       |
| `MOBILE`     | 移动设备仿真沙箱             | 模拟手机应用操作、触控交互                |
| `APPWORLD`   | 应用世界仿真沙箱             | 在虚拟环境中模拟跨应用交互                |
| `BFCL`       | BFCL（特定业务领域执行环境） | 运行业务流程脚本（具体取决于实现）        |
| `AGENTBAY`   | AgentBay会话型沙箱           | 专用于多Agent协作或复杂任务编排的持久环境 |

## 切换运行模式示例

### **嵌入式模式（适合开发测试）**

```{code-cell}
sandbox_service = SandboxService(base_url=None)  # 本地模式
await sandbox_service.start()

sandboxes = sandbox_service.connect(
    session_id="DevSession",
    sandbox_types=["browser"]
)
```

### **远程模式（适合生产部署）**

```{code-cell}
sandbox_service = SandboxService(
    base_url="https://sandbox-manager.com",
    bearer_token="YOUR_AUTH_TOKEN"
)
await sandbox_service.start()

sandboxes = sandbox_service.connect(
    session_id="ProdSession",
    user_id="UserABC",
    sandbox_types=["browser", "code"]
)
```

### 释放环境

会话结束时显式释放资源：

```{code-cell}
sandbox_service.release(session_id="ProdSession", user_id="UserABC")
```

```{note}
AGENTBAY 类型的沙箱会在对象销毁时自动清理。
```

## 选型建议

- 快速原型 / 单机开发调试：
  - 嵌入式模式 (`base_url=None`)
  - 选用 `BROWSER`/`CODE` 类型按需创建
- 生产环境 / 多用户分布式：
  - 远程 API 模式（需部署 `SandboxManager` 服务）
  - 考虑集群和认证机制（`bearer_token`）
- 安全或隔离要求高的场景：
  - 为不同用户会话创建独立沙箱
  - 使用 `release()` 及时释放资源

## 小结

- **SandboxService** 是管理沙箱执行环境的核心组件，支持多类型环境。
- 推荐通过 **适配器**（`sandbox_tool_adapter`）将沙箱方法注册到工具模块，避免直接操作底层 API。
- 可选 **嵌入式模式**（简单，单机）或 **远程模式**（可扩展，生产级）。
- 生命周期由 Runner/Engine 管理，确保启动、健康检查与释放一致。
- 切换模式或类型只需更换服务初始化参数，不影响 Agent 业务逻辑。
