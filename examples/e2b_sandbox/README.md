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

### 类层次结构

```
Sandbox (基类)
└── CloudSandbox (云沙箱基类)
    └── E2bSandBox (E2B桌面实现)
```
### 注册信息

- **E2B桌面**: 注册名为 `e2b-desktop`，类型为 SandboxType.E2B

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
# 在agentscope-runtime 根目录下执行
pip install ".[sandbox]"
```


### 2. 直接使用 E2B 桌面沙箱

```
python
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

```
python
from agentscope_runtime.sandbox.enums import SandboxType
from agentscope_runtime.engine.services.sandbox_service import SandboxService

sandbox_service = SandboxService()
sandboxes = sandbox_service.connect(
    session_id="session1",
    user_id="user1",
    env_types=[SandboxType.E2B.value]
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
