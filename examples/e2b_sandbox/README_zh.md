# E2B Desktop Sandbox 文档

## 概述

E2bSandBox 是基于 E2B 云桌面服务构建的 GUI 沙箱环境，允许用户远程控制云上的桌面环境。

## 功能特性

### E2B 桌面沙箱 (E2bSandBox)

- **环境类型**: 云桌面环境
- **提供商**: E2B Desktop
- **安全等级**: 高
- **接入方式**: E2B Desktop Python SDK 调用

## 支持的操作

### 桌面控制工具

- click: 点击屏幕坐标
- right_click: 右键点击
- type_text: 输入文本
- press_key: 按键
- launch_app: 启动应用程序
- click_and_type: 点击并输入文本

### 命令行工具

- run_shell_command: 运行 shell 命令

### 系统工具

- screenshot: 截图

## 集成到 Agentscope-Runtime

E2B Desktop Sandbox 已经被集成到 Agentscope-Runtime 中，提供了与 Docker 沙箱类似的使用体验。

## E2B Sandbox 集成进 Agentscope-Runtime：

目前，Agentscope-Runtime 的沙箱容器基于 docker 实现，云上容器基于 k8s 实现；E2B Sandbox 集成进 AgentScope-Runtime，能够给使用 Agentscope-Runtime 提供另外一种云上沙箱环境的选择，可以使用除了 docker 容器沙箱之外，也可以选择使用e2b沙箱；

### 核心思路：

核心思路是把 E2B Sandbox 封装成 Sandbox 集成进 AgentScope-Runtime，作为另外一种云沙箱的选择；
由于 E2B Sandbox 并不依赖容器，所以创建 CloudSandbox 基类继承 Sandbox 类，这样就使得 Agentscope-Runtime 能够同时支持传统容器沙箱和云原生沙箱，在使用上与传统容器沙箱尽量保持一致；

### 1. 核心架构集成

- **新增沙箱类型**: `SandboxType.E2B` 枚举，用于创建 E2B Sandbox，支持动态枚举扩展；
- **CloudSandbox 基类**: 抽象基类，为云服务沙箱提供统一接口，不依赖容器管理，直接通过云 API 通信，可以支持不同云提供商扩展；
- **E2bSandBox 实现**: 继承自 CloudSandbox，直接通过 E2b sdk 访问云端沙箱，实现完整的工具映射和错误处理；
- **SandboxService 支持**: 保持与原有 sandbox_service 调用方式的兼容性，特殊处理 E2b 沙箱类型，资源清理；

### 2. 类层次结构

```
Sandbox (基类)
└── CloudSandbox (云沙箱基类)
    └── E2bSandBox (E2B桌面实现)
```

### 3. 文件结构

```
src/agentscope_runtime/sandbox/
├── enums.py                          # 新增 AGENTBAY 枚举
├── box/
│   ├── cloud/
│   │   ├── __init__.py               # 新增
│   │   └── cloud_sandbox.py         # 新增 CloudSandbox 基类
│   └── e2b/
│       ├── __init__.py               # 新增
│       └── e2b_sandbox.py       # 新增 E2bSandBox 实现
└── __init__.py                       # 更新导出
```


### 4. 服务层集成

- **注册机制**：使用 `@SandboxRegistry.register` 装饰器注册
- **服务集成**：在 `SandboxService` 中特殊处理 E2B 类型
- **兼容性**：保持与现有沙箱接口的完全兼容
- **生命周期管理**: 支持创建、连接、释放 云资源

## 如何使用

### 1. 设置环境变量

根据 E2B 官方文档配置相应的认证信息。
##### 1.1.1 E2B 开通
    访问E2B官网注册并获取，然后配置到E2B_API_KEY
    https://e2b.dev

编辑当前目录下的.env.template文件或者设置环境变量

```bash
# E2B API Key
export E2B_API_KEY=
# docker 运行环境 $home 替换为用户主目录,直接使用云沙箱的方式下无需配置，unix:///$home/.colima/default/docker.sock
export DOCKER_HOST=''

```

依赖安装

```bash
# 安装核心依赖
pip install agentscope-runtime

# 安装拓展
pip install "agentscope-runtime[ext]"
```


### 2. 直接使用 E2B 桌面沙箱

```python
from agentscope_runtime.sandbox.box.e2b.e2b_sandbox import E2bSandBox

sandbox = E2bSandBox()

# 运行shell命令
result = sandbox.call_tool("run_shell_command", {"command": "echo Hello World"})
print(result["output"])

# 截图
result_screenshot = sandbox.call_tool(
                "screenshot",
                {"file_path": f"{os.getcwd()}/screenshot.png"},
            )
print(f"screenshot result: {result_screenshot}")
```
### 3. 通过 SandboxService 使用

```python
from agentscope_runtime.sandbox.enums import SandboxType
from agentscope_runtime.engine.services.sandbox import SandboxService

sandbox_service = SandboxService()
sandboxes = sandbox_service.connect(
    session_id="session1",
    user_id="user1",
    sandbox_types=[SandboxType.E2B]
)
```
## 配置参数

### E2B 桌面沙箱配置

| 参数 | 类型 | 描述 |
|------|------|------|
| timeout | int | 操作超时时间(秒)，默认600 |
| command_timeout | int | 命令执行超时时间(秒)，默认60 |

## 注意事项

1. 使用前需要确保已注册并配置好 E2B 服务
2. 需要正确配置相应的环境变量
3. E2B 服务会产生相应的资源费用
```


## 运行演示 demo

```bash
# 沙箱演示
python examples/e2b_sandbox/e2b_sandbox_demo.py
```
