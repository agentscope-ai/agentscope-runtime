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

# 沙箱

AgentScope Runtime的Sandbox提供了一个**安全**且**隔离**的环境，用于工具执行、浏览器自动化、文件系统操作、训练评测等功能。在本教程中，您将学习如何设置工具沙箱依赖项并在沙箱环境中运行工具。

## 前提条件

```{note}
当前的沙箱环境默认使用 Docker 进行隔离。此外，我们还支持 Kubernetes (K8s) 作为远程服务后端。未来，我们计划在即将发布的版本中加入更多第三方托管解决方案。
```


````{warning}
对于使用**苹果芯片**（如M1/M2）的设备，我们建议以下选项来运行**x86** Docker环境以获得最大兼容性：
* Docker Desktop：请参阅[Docker Desktop安装指南](https://docs.docker.com/desktop/setup/install/mac-install/)以启用Rosetta2，确保与x86_64镜像的兼容性。
* Colima：确保启用Rosetta 2支持。您可以使用以下命令启动[Colima](https://github.com/abiosoft/colima)以实现兼容性：`colima start --vm-type=vz --vz-rosetta --memory 8 --cpu 1`
````

- Docker
- （可选，仅支持远程模式）Kubernetes

## 安装

### 安装依赖项

首先，安装AgentScope Runtime：

```bash
pip install agentscope-runtime
```

### 准备Docker镜像

沙箱为不同功能使用不同的Docker镜像。您可以只拉取需要的镜像，或者拉取所有镜像以获得完整功能：

#### 选项1：拉取所有镜像（推荐）

为了确保完整的沙箱体验并启用所有功能，请按照以下步骤从我们的仓库拉取并标记必要的Docker镜像：

```{note}
**镜像来源：阿里云容器镜像服务**

所有Docker镜像都托管在阿里云容器镜像服务(ACR)上，以在全球范围内实现可获取和可靠性。镜像从ACR拉取后使用标准名称重命名，以与AgentScope Runtime无缝集成。
```

```bash
# 基础镜像
docker pull agentscope-registry.ap-southeast-1.cr.aliyuncs.com/agentscope/runtime-sandbox-base:latest && docker tag agentscope-registry.ap-southeast-1.cr.aliyuncs.com/agentscope/runtime-sandbox-base:latest agentscope/runtime-sandbox-base:latest

# GUI镜像
docker pull agentscope-registry.ap-southeast-1.cr.aliyuncs.com/agentscope/runtime-sandbox-gui:latest && docker tag agentscope-registry.ap-southeast-1.cr.aliyuncs.com/agentscope/runtime-sandbox-gui:latest agentscope/runtime-sandbox-gui:latest

# 文件系统镜像
docker pull agentscope-registry.ap-southeast-1.cr.aliyuncs.com/agentscope/runtime-sandbox-filesystem:latest && docker tag agentscope-registry.ap-southeast-1.cr.aliyuncs.com/agentscope/runtime-sandbox-filesystem:latest agentscope/runtime-sandbox-filesystem:latest

# 浏览器镜像
docker pull agentscope-registry.ap-southeast-1.cr.aliyuncs.com/agentscope/runtime-sandbox-browser:latest && docker tag agentscope-registry.ap-southeast-1.cr.aliyuncs.com/agentscope/runtime-sandbox-browser:latest agentscope/runtime-sandbox-browser:latest

# 移动端镜像
docker pull agentscope-registry.ap-southeast-1.cr.aliyuncs.com/agentscope/runtime-sandbox-mobile:latest && docker tag agentscope-registry.ap-southeast-1.cr.aliyuncs.com/agentscope/runtime-sandbox-mobile:latest agentscope/runtime-sandbox-mobile:latest
```

#### 选项2：拉取特定镜像

根据您的具体需求选择镜像：

| Image                | Purpose                   | When to Use                                                  |
| -------------------- | ------------------------- | ------------------------------------------------------------ |
| **Base Image**       | Python代码执行，shell命令 | 基本工具执行必需                                             |
| **GUI Image**        | 计算机操作                | 当你需要图形操作页面时                                       |
| **Filesystem Image** | 文件系统操作              | 当您需要文件读取/写入/管理时                                 |
| **Browser Image**    | Web浏览器自动化           | 当您需要网络爬取或浏览器控制时                               |
| **Mobile Image**     | 移动端操作                | 当您需要操作移动端设备时                                    |
| **Training Image**   | 训练和评估智能体          | 当你需要在某些基准数据集上训练和评估智能体时 （详情请参考 {doc}`training_sandbox` ） |

### 验证安装

您可以通过调用`run_ipython_cell`来验证一切设置是否正确：

```{code-cell}
import json
from agentscope_runtime.sandbox.tools.base import run_ipython_cell

# 模型上下文协议（MCP）兼容的工具调用结果
result = run_ipython_cell(code="print('Setup successful!')")
print(json.dumps(result, indent=4, ensure_ascii=False))
```

### （可选）从头构建Docker镜像

如果您更倾向于在本地自己通过`Dockerfile`构建镜像或需要自定义修改，可以从头构建它们。请参阅 {doc}`advanced` 了解详细说明。

## 沙箱使用

### 创建沙箱

前面的部分介绍了以工具为中心的使用方法，而本节介绍以沙箱为中心的使用方法。

您可以通过`sandbox` SDK创建不同类型的沙箱。通过 `SandboxService` 管理沙箱生命周期，支持会话管理和沙箱复用。AgentScope Runtime 为每种沙箱类型都提供了 **同步版本** 和 **异步版本**：

| 同步类              | 异步类                   |
| ------------------- | ------------------------ |
| `BaseSandbox`       | `BaseSandboxAsync`       |
| `GuiSandbox`        | `GuiSandboxAsync`        |
| `FilesystemSandbox` | `FilesystemSandboxAsync` |
| `BrowserSandbox`    | `BrowserSandboxAsync`    |
| `MobileSandbox`     | `MobileSandboxAsync`     |
| `TrainingSandbox`   | \- （暂无异步版本）      |
| `AgentbaySandbox`   | \- （暂无异步版本）      |


* **基础沙箱（Base Sandbox）**：用于在隔离环境中运行 **Python 代码** 或 **Shell 命令**。

```{code-cell}
# --- 同步版本 ---
from agentscope_runtime.sandbox import BaseSandbox

with BaseSandbox() as box:
    # 默认使用镜像 `agentscope/runtime-sandbox-base:latest` 从 DockerHub 拉取
    print(box.list_tools())  # 列出所有可用工具
    print(box.run_ipython_cell(code="print('你好')"))  # 在沙箱中运行 Python 代码
    print(box.run_shell_command(command="echo hello"))  # 在沙箱中运行 Shell 命令
    input("按 Enter 键继续...")

# --- 异步版本 ---
from agentscope_runtime.sandbox import BaseSandboxAsync

async with BaseSandboxAsync() as box:
    # 默认使用镜像 `agentscope/runtime-sandbox-base:latest` 从 DockerHub 拉取
    print(await box.list_tools())  # 列出所有可用工具
    print(await box.run_ipython_cell(code="print('你好')"))  # 在沙箱中运行 Python 代码
    print(await box.run_shell_command(command="echo hello"))  # 在沙箱中运行 Shell 命令
    input("按 Enter 键继续...")
```

* **GUI 沙箱 （GUI Sandbox）**： 提供**可视化桌面环境**，可执行鼠标、键盘以及屏幕相关操作。

  <img src="https://img.alicdn.com/imgextra/i2/O1CN01df5SaM1xKFQP4KGBW_!!6000000006424-2-tps-2958-1802.png" alt="GUI Sandbox" width="800" height="500">

```{code-cell}
# --- 同步版本 ---
from agentscope_runtime.sandbox import GuiSandbox

with GuiSandbox() as box:
    # 默认使用镜像 `agentscope/runtime-sandbox-gui:latest` 从 DockerHub 拉取
    print(box.list_tools())  # 列出所有可用工具
    print(box.desktop_url)  # Web 桌面访问地址
    print(box.computer_use(action="get_cursor_position"))  # 获取鼠标位置坐标
    print(box.computer_use(action="get_screenshot"))  # 截取桌面截图
    input("按 Enter 键继续...")

# --- 异步版本 ---
from agentscope_runtime.sandbox import GuiSandboxAsync

async with GuiSandboxAsync() as box:
    # 默认使用镜像 `agentscope/runtime-sandbox-gui:latest` 从 DockerHub 拉取
    print(await box.list_tools())  # 列出所有可用工具
    print(box.desktop_url)  # Web 桌面访问地址
    print(await box.computer_use(action="get_cursor_position"))  # 获取鼠标位置坐标
    print(await box.computer_use(action="get_screenshot"))  # 截取桌面截图
    input("按 Enter 键继续...")
```

* **文件系统沙箱 （Filesystem Sandbox）**：基于 GUI 的隔离沙箱，可进行文件系统操作，如创建、读取和删除文件。

  <img src="https://img.alicdn.com/imgextra/i3/O1CN01VocM961vK85gWbJIy_!!6000000006153-2-tps-2730-1686.png" alt="GUI Sandbox" width="800" height="500">

```{code-cell}
# --- 同步版本 ---
from agentscope_runtime.sandbox import FilesystemSandbox

with FilesystemSandbox() as box:
    # 默认使用镜像 `agentscope/runtime-sandbox-filesystem:latest` 从 DockerHub 拉取
    print(box.list_tools())  # 列出所有可用工具
    print(box.desktop_url)  # Web 桌面访问地址
    box.create_directory("test")  # 创建一个目录
    input("按 Enter 键继续...")

# --- 异步版本 ---
from agentscope_runtime.sandbox import FilesystemSandboxAsync

async with FilesystemSandboxAsync() as box:
    # 默认使用镜像 `agentscope/runtime-sandbox-filesystem:latest` 从 DockerHub 拉取
    print(await box.list_tools())  # 列出所有可用工具
    print(box.desktop_url)  # Web 桌面访问地址
    await box.create_directory("test")  # 创建一个目录
    input("按 Enter 键继续...")
```

* **浏览器沙箱（Browser Sandbox）**: 基于 GUI 的沙箱，可进行浏览器操作。

  <img src="https://img.alicdn.com/imgextra/i4/O1CN01OIq1dD1gAJMcm0RFR_!!6000000004101-2-tps-2734-1684.png" alt="GUI Sandbox" width="800" height="500">

```{code-cell}
# --- 同步版本 ---
from agentscope_runtime.sandbox import BrowserSandbox

with BrowserSandbox() as box:
    # 默认使用镜像 `agentscope/runtime-sandbox-browser:latest` 从 DockerHub 拉取
    print(box.list_tools())  # 列出所有可用工具
    print(box.desktop_url)  # Web 桌面访问地址
    box.browser_navigate("https://www.google.com/")  # 打开网页
    input("按 Enter 键继续...")

# --- 异步版本 ---
from agentscope_runtime.sandbox import BrowserSandboxAsync

async with BrowserSandboxAsync() as box:
    # 默认使用镜像 `agentscope/runtime-sandbox-browser:latest` 从 DockerHub 拉取
    print(await box.list_tools())  # 列出所有可用工具
    print(box.desktop_url)  # Web 桌面访问地址
    await box.browser_navigate("https://www.google.com/")  # 打开网页
    input("按 Enter 键继续...")
```

* **移动端沙箱（Mobile Sandbox）**: 基于 Android 模拟器的沙箱，可进行移动端操作，如点击、滑动、输入文本和截屏等。

  <img src="https://img.alicdn.com/imgextra/i4/O1CN01yPnBC21vOi45fLy7V_!!6000000006163-2-tps-544-865.png" alt="Mobile Sandbox" height="500">

  - **运行环境要求**

    - **Linux 主机**:
    该沙箱在 Linux 主机上运行时，需要内核加载 `binder` 和 `ashmem` 模块。如果缺失，请在主机上执行以下命令来安装和加载所需模块：

    ```bash
        # 1. 安装额外的内核模块
        sudo apt update && sudo apt install -y linux-modules-extra-`uname -r`

        # 2. 加载模块并创建设备节点
        sudo modprobe binder_linux devices="binder,hwbinder,vndbinder"
        sudo modprobe ashmem_linux
    ```

    - **架构兼容性**:
    在 ARM64/aarch64 架构（如 Apple M 系列芯片）上运行时，可能会遇到兼容性或性能问题，建议在 x86_64 架构的主机上运行。

```{code-cell}
# --- 同步版本 ---
from agentscope_runtime.sandbox import MobileSandbox

with MobileSandbox() as box:
    # 默认使用镜像 'agentscope/runtime-sandbox-mobile:latest' 从 DockerHub 拉取
    print(box.list_tools())  # 列出所有可用工具
    print(box.mobile_get_screen_resolution())  # 获取屏幕分辨率
    print(box.mobile_tap([500, 1000]))  # 在坐标 (500, 1000) 点击
    print(box.mobile_input_text("来自 AgentScope 的问候！"))  # 输入文本
    print(box.mobile_key_event(3))  # 发送 HOME 按键事件（KeyCode: 3）
    screenshot_result = box.mobile_get_screenshot()  # 截取屏幕
    print(screenshot_result)
    input("按 Enter 键继续...")

# --- 异步版本 ---
from agentscope_runtime.sandbox import MobileSandboxAsync

async with MobileSandboxAsync() as box:
    # 默认使用镜像 'agentscope/runtime-sandbox-mobile:latest' 从 DockerHub 拉取
    print(await box.list_tools())  # 列出所有可用工具
    print(await box.mobile_get_screen_resolution())  # 获取屏幕分辨率
    print(await box.mobile_tap([500, 1000]))  # 在坐标 (500, 1000) 点击
    print(await box.mobile_input_text("来自 AgentScope 的问候！"))  # 输入文本
    print(await box.mobile_key_event(3))  # 发送 HOME 按键事件（KeyCode: 3）
    screenshot_result = await box.mobile_get_screenshot()  # 截取屏幕
    print(screenshot_result)
    input("按 Enter 键继续...")
```

* **TrainingSandbox**：训练评估沙箱，详情请参考：{doc}`training_sandbox`。

```{code-cell}
from agentscope_runtime.sandbox import TrainingSandbox

# 创建训练评估用沙箱
with TrainingSandbox() as box:
    profile_list = box.get_env_profile(env_type="appworld", split="train")
    print(profile_list)
```

* **云沙箱（Cloud Sandbox）**：基于云服务的沙箱环境，无需本地 Docker 容器。`CloudSandbox` 是云沙箱的基类，提供了云沙箱的统一接口。

```{code-cell}
from agentscope_runtime.sandbox import CloudSandbox

# CloudSandbox 是抽象基类，通常不直接使用
# 请使用具体的云沙箱实现，如 AgentbaySandbox
```

* **AgentBay 沙箱（AgentbaySandbox）**：基于 AgentBay 云服务的沙箱实现，支持多种镜像类型（Linux、Windows、Browser、CodeSpace、Mobile 等）。

```{code-cell}
from agentscope_runtime.sandbox import AgentbaySandbox

# 使用 AgentBay 云沙箱（需要配置 API Key）
with AgentbaySandbox(
    api_key="your_agentbay_api_key",
    image_id="linux_latest",  # 可选：指定镜像类型
) as box:
    print(box.list_tools())  # 列出所有可用工具
    print(box.run_shell_command(command="echo hello from cloud"))
    print(box.get_session_info())  # 获取会话信息
```

**AgentBay 沙箱特性**：
- 无需本地 Docker，完全基于云服务
- 支持多种环境类型（Linux、Windows、Browser 等）
- 自动管理会话生命周期
- 通过 API 直接与云服务通信

```{note}
更多沙箱类型正在开发中，敬请期待！
```

### 向沙箱添加MCP服务器

MCP（模型上下文协议）是一个标准化协议，使AI应用程序能够安全地连接到外部数据源和工具。通过将MCP服务器集成到您的沙箱中，您可以在不影响安全性的情况下使用专门的工具和服务扩展沙箱的功能。

沙箱支持通过`add_mcp_servers`方法集成MCP服务器。添加后，您可以使用`list_tools`发现可用工具并使用`call_tool`执行它们。

```{code-cell}
with BaseSandbox() as sandbox:
    mcp_server_configs = {
        "mcpServers": {
            "time": {
                "command": "uvx",
                "args": [
                    "mcp-server-time",
                    "--local-timezone=America/New_York",
                ],
            },
        },
    }

    # 将MCP服务器添加到沙箱
    sandbox.add_mcp_servers(server_configs=mcp_server_configs)

    # 列出所有可用工具（现在包括MCP工具）
    print(sandbox.list_tools())

    #使用MCP服务器提供的时间工具
    print(
        sandbox.call_tool(
            "get_current_time",
            arguments={
                "timezone": "America/New_York",
            },
        ),
    )
```

### 连接到远程沙箱

```{note}
沙箱远程部署特别适用于：
* 将计算密集型任务分离到专用服务器
* 多个客户端共享同一沙箱环境
* 在资源受限的本地机器上开发，同时在高性能服务器上执行
* K8S集群部署沙盒服务

有关sandbox-server的更高级用法，请参阅{doc}`advanced`了解详细说明。
```

您可以在本地机器或不同机器上启动沙箱服务器，以便于远程访问。您应该通过以下命令启动沙箱服务器：

```bash
runtime-sandbox-server
```

要连接到远程沙箱服务，可以通过以下方式：

```python
# 连接到远程沙箱服务器（替换为实际的服务器IP）
with BaseSandbox(base_url="http://your_IP_address:8000") as box:
    print(box.run_ipython_cell(code="print('hi')"))
```

### 将沙箱暴露为 MCP 服务

将本地的 Sandbox Runtime 配置为名为 `sandbox` 的 MCP 服务，使其可以被 MCP 兼容的客户端调用，通过远程的 sandbox 服务器 `http://127.0.0.1:8000` 来安全地执行沙箱中的命令。

```json
{
    "mcpServers": {
        "sandbox": {
            "command": "uvx",
            "args": [
                "--from",
                "agentscope-runtime",
                "runtime-sandbox-mcp",
                "--type=base",
                "--base_url=http://127.0.0.1:8000"
            ]
        }
    }
}
```

#### 命令参数

`runtime-sandbox-mcp` 命令支持以下参数：

| 参数             | 取值范围                          | 描述                                                         |
| ---------------- | --------------------------------- | ------------------------------------------------------------ |
| `--type`         | `base`, `gui`, `browser`, `filesystem` | 沙箱种类 |
| `--base_url`     | URL 字符串                        | 远程 Sandbox 服务的基础 URL。不填写则在本地运行。            |
| `--bearer_token` | 字符串令牌                        | （可选）安全访问的身份认证令牌。                             |

## 沙箱服务

### 使用沙箱服务管理沙箱

`SandboxService` 提供了统一的沙箱管理接口，支持通过 `session_id` 和 `user_id` 来管理不同用户会话的沙箱环境。使用 `SandboxService` 可以让您更好地控制沙箱的生命周期，并实现沙箱的复用。

```{code-cell}
from agentscope_runtime.engine.services.sandbox import SandboxService

async def main():
    # 创建并启动沙箱服务
    sandbox_service = SandboxService()
    await sandbox_service.start()

    session_id = "session_123"
    user_id = "user_12345"

    # 连接到沙箱，指定需要的沙箱类型
    sandboxes = sandbox_service.connect(
        session_id=session_id,
        user_id=user_id,
        sandbox_types=["base"],
    )

    base_sandbox = sandboxes[0]

    # 直接在沙箱实例上调用工具方法
    result = base_sandbox.run_ipython_cell("print('Hello, World!')")
    base_sandbox.run_ipython_cell("a=1")

    print(result)

    # 使用相同的 session_id 和 user_id 会复用同一个沙箱实例
    new_sandboxes = sandbox_service.connect(
        session_id=session_id,
        user_id=user_id,
        sandbox_types=["base"],
    )

    new_base_sandbox = new_sandboxes[0]
    # 变量 a 仍然存在，因为复用了同一个沙箱
    result = new_base_sandbox.run_ipython_cell("print(a)")
    print(result)

    # 停止沙箱服务
    await sandbox_service.stop()

await main()
```

### 使用沙箱服务添加MCP服务器

```{code-cell}
from agentscope_runtime.engine.services.sandbox import SandboxService

async def main():
    sandbox_service = SandboxService()
    await sandbox_service.start()

    session_id = "session_mcp"
    user_id = "user_mcp"

    sandboxes = sandbox_service.connect(
        session_id=session_id,
        user_id=user_id,
        sandbox_types=["base"],
    )

    sandbox = sandboxes[0]

    mcp_server_configs = {
        "mcpServers": {
            "time": {
                "command": "uvx",
                "args": [
                    "mcp-server-time",
                    "--local-timezone=America/New_York",
                ],
            },
        },
    }

    # 将MCP服务器添加到沙箱
    sandbox.add_mcp_servers(server_configs=mcp_server_configs)

    # 列出所有可用工具（现在包括MCP工具）
    print(sandbox.list_tools())

    # 使用MCP服务器提供的时间工具
    print(
        sandbox.call_tool(
            "get_current_time",
            arguments={
                "timezone": "America/New_York",
            },
        ),
    )

    await sandbox_service.stop()

await main()
```

### 使用沙箱服务连接远程沙箱

```{code-cell}
from agentscope_runtime.engine.services.sandbox import SandboxService

async def main():
    # 创建 SandboxService 并指定远程服务器地址
    sandbox_service = SandboxService(
        base_url="http://your_IP_address:8000",  # 替换为实际的服务器IP
        bearer_token="your_token"  # 可选：如果需要身份验证
    )
    await sandbox_service.start()

    session_id = "remote_session"
    user_id = "remote_user"

    # 连接到远程沙箱
    sandboxes = sandbox_service.connect(
        session_id=session_id,
        user_id=user_id,
        sandbox_types=["base"],
    )

    base_sandbox = sandboxes[0]
    print(base_sandbox.run_ipython_cell(code="print('hi')"))

    await sandbox_service.stop()

await main()
```

## 工具列表

* 基础工具（在所有沙箱类型中可用）
* 计算机操作工具（在`GuiSandbox`中可用）
* 文件系统工具（在`FilesystemSandbox`中可用）
* 浏览器工具（在`BrowserSandbox`中可用）
* 移动端工具（在`MobileSandbox`中可用）

| 分类               | 工具名称                                                     | 描述                                                         |
| ------------------ | ------------------------------------------------------------ | ------------------------------------------------------------ |
| **基础工具**       | `run_ipython_cell(code: str)`                                | 在IPython环境中执行Python代码                                |
|                    | `run_shell_command(command: str)`                            | 在沙箱中执行shell命令                                        |
| **文件系统工具**   | `read_file(path: str)`                                       | 读取文件的完整内容                                           |
|                    | `read_multiple_files(paths: list)`                           | 同时读取多个文件                                             |
|                    | `write_file(path: str, content: str)`                        | 创建或覆盖文件内容                                           |
|                    | `edit_file(path: str, edits: list,dryRun: bool)`             | 对文本文件进行基于行的编辑                                   |
|                    | `create_directory(path: str)`                                | 创建新目录                                                   |
|                    | `list_directory(path: str)`                                  | 列出路径中的所有文件和目录                                   |
|                    | `directory_tree(path: str)`                                  | 获取目录结构的递归树视图                                     |
|                    | `move_file(source: str, destination: str)`                   | 移动或重命名文件和目录                                       |
|                    | `search_files(path: str, pattern: str, excludePatterns: list)` | 搜索匹配模式的文件                                           |
|                    | `get_file_info(path: str)`                                   | 获取文件或目录的详细元数据                                   |
|                    | `list_allowed_directories()`                                 | 列出服务器可以访问的目录                                     |
| **浏览器工具**     | `browser_navigate(url: str)`                                 | 导航到特定URL                                                |
|                    | `browser_navigate_back()`                                    | 返回到上一页                                                 |
|                    | `browser_navigate_forward()`                                 | 前进到下一页                                                 |
|                    | `browser_close()`                                            | 关闭当前浏览器页面                                           |
|                    | `browser_resize(width: int, height: int)`                    | 调整浏览器窗口大小                                           |
|                    | `browser_click(element: str, ref: str)`                      | 点击Web元素                                                  |
|                    | `browser_type(element: str, ref: str, text: str, submit: bool)` | 在输入框中输入文本                                           |
|                    | `browser_hover(element: str, ref: str)`                      | 悬停在Web元素上                                              |
|                    | `browser_drag(startElement: str, startRef: str, endElement: str, endRef: str)` | 在元素之间拖拽                                               |
|                    | `browser_select_option(element: str, ref: str, values: list)` | 在下拉菜单中选择选项                                         |
|                    | `browser_press_key(key: str)`                                | 按键盘按键                                                   |
|                    | `browser_file_upload(paths: list)`                           | 上传文件到页面                                               |
|                    | `browser_snapshot()`                                         | 捕获当前页面的可访问性快照                                   |
|                    | `browser_take_screenshot(raw: bool, filename: str, element: str, ref: str)` | 截取页面或元素的屏幕快照                                     |
|                    | `browser_pdf_save(filename: str)`                            | 将当前页面保存为PDF                                          |
|                    | `browser_tab_list()`                                         | 列出所有打开的浏览器标签页                                   |
|                    | `browser_tab_new(url: str)`                                  | 打开新标签页                                                 |
|                    | `browser_tab_select(index: int)`                             | 切换到特定标签页                                             |
|                    | `browser_tab_close(index: int)`                              | 关闭标签页（如果未指定索引则关闭当前标签页）                 |
|                    | `browser_wait_for(time: int, text: str, textGone: str)`      | 等待条件或时间流逝                                           |
|                    | `browser_console_messages()`                                 | 获取页面的所有控制台消息                                     |
|                    | `browser_network_requests()`                                 | 获取页面加载以来的所有网络请求                               |
|                    | `browser_handle_dialog(accept: bool, promptText: str)`       | 处理浏览器对话框（警告、确认、提示）                         |
| **计算机操作工具** | `computer_use(action: str, coordinate: list, text: str)`     | 使用鼠标和键盘与桌面 GUI 互动，支持以下操作：移动光标、点击、输入文字以及截图 |
| **移动端工具**     | `mobile_get_screen_resolution()`                                 | 获取移动设备的屏幕分辨率                                     |
|                    | `mobile_tap(coordinate: List[int])`                                     | 在屏幕上的特定坐标处进行点击                                 |
|                    | `mobile_swipe(start: List[int], end: List[int], duration: int = None)` | 在屏幕上从起点到终点执行滑动操作                         |
|                    | `mobile_input_text(text: str)`                                   | 在当前聚焦的UI元素中输入文本字符串                           |
|                    | `mobile_key_event(code: int\|str)`                        | 向设备发送一个按键事件（如 HOME、BACK）                  |
|                    | `mobile_get_screenshot()`                                        | 获取当前设备屏幕的截图                                       |

