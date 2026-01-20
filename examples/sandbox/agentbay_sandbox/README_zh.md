# AgentBay SDK 集成进 Agentscope-Runtime 调研方案

## AgentBay 是什么：

AgentBay 是一个阿里云上的 GUI 沙箱环境。
AgentBay 能够提供 Code Space、Browser Use、Computer Use、Mobile Use 四种沙箱环境。提供 MCP Server 和 AgentBay SDK 的方式接入，目前 AgentBay SDK 已开源。
AgentBay SDK 开源地址: [AgentBay SDK 开源地址](https://github.com/aliyun/wuying-agentbay-sdk)
AgentBay 云产品地址: [AgentBay 云产品地址](https://www.aliyun.com/product/agentbay)

## AgentBay 能力

- **新增沙箱类型**: Code Space、Browser Use、Computer Use、Mobile Use
- **接入方式**: MCP Server 和 AgentBay SDK；

### 镜像类型支持

- `linux_latest` - Linux 环境
- `windows_latest` - Windows 环境
- `browser_latest` - 浏览器自动化环境
- `code_latest` - 代码执行环境
- `mobile_latest` - 移动端环境

### 支持的工具操作

- **基础操作**：`run_shell_command`, `run_ipython_cell`, `screenshot`
- **文件操作**：`read_file`, `write_file`, `list_directory`, `create_directory`, `move_file`, `delete_file`
- **浏览器操作**：`browser_navigate`, `browser_click`, `browser_input` (browser_latest 镜像)

## AgentBay 集成进 Agentscope-Runtime：

目前，Agentscope-Runtime 的沙箱容器基于 docker 实现，云上容器基于 k8s 实现；AgentBay 集成进 AgentScope-Runtime，能够给使用 Agentscope-Runtime 提供另外一种云上沙箱环境的选择，可以使用除了 docker 容器沙箱之外，也可以选择使用 AgentBay 的 GUI 沙箱；

### 核心思路：

AgentBay 这个云产品是对标国外 e2b、daytona 等云沙箱产品做的，使用 api_key 就开箱即用，无需部署；
核心思路是把 AgentBay 封装成 AgentBay Sandbox 集成进 AgentScope-Runtime，作为另外一种云沙箱的选择，其实 e2b 也可以复用这套逻辑；
由于 AgentBay Sandbox 并不依赖容器，所以创建 CloudSandbox 基类继承 Sandbox 类，这样就使得 Agentscope-Runtime 能够同时支持传统容器沙箱和云原生沙箱，在使用上与传统容器沙箱尽量保持一致；

### 1. 核心架构集成

- **新增沙箱类型**: `SandboxType.AGENTBAY` 枚举，用于创建 Agentbay Sandbox，支持动态枚举扩展；
- **CloudSandbox 基类**: 抽象基类，为云服务沙箱提供统一接口，不依赖容器管理，直接通过云 API 通信，可以支持不同云提供商扩展；
- **AgentbaySandbox 实现**: 继承自 CloudSandbox，直接通过 AgentBay API 访问云端沙箱，实现完整的工具映射和错误处理；
- **SandboxService 支持**: 保持与原有 sandbox_service 调用方式的兼容性，特殊处理 AgentBay 沙箱类型，支持会话管理和资源清理；

### 2. 类层次结构

```
Sandbox (基类)
└── CloudSandbox (云沙箱基类)
    └── AgentbaySandbox (AgentBay 实现)
```

### 3. 文件结构

```
src/agentscope_runtime/sandbox/
├── enums.py                          # 新增 AGENTBAY 枚举
├── box/
│   ├── cloud/
│   │   ├── __init__.py               # 新增
│   │   └── cloud_sandbox.py         # 新增 CloudSandbox 基类
│   └── agentbay/
│       ├── __init__.py               # 新增
│       └── agentbay_sandbox.py       # 新增 AgentbaySandbox 实现
└── __init__.py                       # 更新导出
```

### 4. 服务层集成

- **注册机制**：使用 `@SandboxRegistry.register` 装饰器注册
- **服务集成**：在 `SandboxService` 中特殊处理 AgentBay 类型
- **兼容性**：保持与现有沙箱接口的完全兼容
- **生命周期管理**: 支持创建、连接、释放 AgentBay 会话

## AgentBay Sandbox 如何使用

### 0. 设置环境变量

```bash
pip install "agentscope-runtime[ext]"
export AGENTBAY_API_KEY='your_agentbay_api_key'
export DASHSCOPE_API_KEY='your_dashscope_api_key' # 可选
```

### 1. 直接使用

```python
from agentscope_runtime.sandbox import AgentbaySandbox

sandbox = AgentbaySandbox(
    api_key="your_api_key",
    image_id="linux_latest"
)

result = sandbox.call_tool("run_shell_command", {"command": "echo 'Hello'"})
```

### 2. 通过 SandboxService

```python
from agentscope_runtime.sandbox.enums import SandboxType
from agentscope_runtime.engine.services.sandbox import SandboxService

sandbox_service = SandboxService(bearer_token="your_api_key")
sandboxes = sandbox_service.connect(
    session_id="session1",
    user_id="user1",
    sandbox_types=[SandboxType.AGENTBAY]
)
```

## 运行演示 demo

```bash
# agentbay 沙箱演示
python examples/agentbay_sandbox/agentbay_sandbox_demo.py

# 模型调用sandbox 演示
python examples/agentbay_sandbox/agentscope_use_agentbay_sandbox.py

```
