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

# 工具沙箱

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
```

#### 选项2：拉取特定镜像

根据您的具体需求选择镜像：

| Image                | Purpose                   | When to Use                                                  |
| -------------------- | ------------------------- | ------------------------------------------------------------ |
| **Base Image**       | Python代码执行，shell命令 | 基本工具执行必需                                             |
| **GUI Image**        | 计算机操作                | 当你需要图形操作页面时                                       |
| **Filesystem Image** | 文件系统操作              | 当您需要文件读取/写入/管理时                                 |
| **Browser Image**    | Web浏览器自动化           | 当您需要网络爬取或浏览器控制时                               |
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

如果您更倾向于在本地自己通过`Dockerfile`构建镜像或需要自定义修改，可以从头构建它们。请参阅 {doc}`sandbox_advanced` 了解详细说明。

## 工具使用

### 调用工具

最基本的用法是直接调用内置工具（如通过Sandbox运行Python代码或shell命令）：

```{note}
以下两个函数将在独立的沙箱中独立执行。
每个函数调用都将启动一个**嵌入式**沙箱，在其中执行函数，然后关闭沙箱。每个沙箱的生命周期都限定在函数调用的持续时间内。
```

```{code-cell}
from agentscope_runtime.sandbox.tools.base import (
    run_ipython_cell,
    run_shell_command,
)

print(run_ipython_cell(code="print('hello world')"))
print(run_shell_command(command="whoami"))
```

### 将沙箱绑定到工具

除了直接调用工具外，您还可以使用bind方法将特定沙箱绑定到工具。这允许您指定函数将在哪个沙箱中运行，让您更好地控制执行环境。需要注意的是，函数的类型和沙箱类型必须匹配，否则函数将无法正确执行。以下是操作方法：

```{code-cell}
from agentscope_runtime.sandbox import BaseSandbox

with BaseSandbox() as sandbox:
    # 确保函数的沙箱类型与沙箱实例类型匹配
    assert run_ipython_cell.sandbox_type == sandbox.sandbox_type

    # 将沙箱绑定到工具函数
    func1 = run_ipython_cell.bind(sandbox=sandbox)
    func2 = run_shell_command.bind(sandbox=sandbox)

    # 在沙箱内执行函数
    print(func1(code="repo = 'agentscope-runtime'"))
    print(func1(code="print(repo)"))
    print(func2(command="whoami"))
```

### 将 MCP 服务器转换为工具

`MCPConfigConverter` 用于将外部 MCP（Model Context Protocol）服务器的配置，转换成可在 **Sandbox** 中运行的 `MCPTool`。这样可以在沙箱内调用这些外部工具，保证安全与隔离：

```{code-cell}
from agentscope_runtime.sandbox.tools.mcp_tool import MCPConfigConverter

# 定义 MCP 服务器配置
config = {
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

# 转换为可以在 Sandbox 中运行的 MCPTool 列表
mcp_tools = MCPConfigConverter(server_configs=config).to_builtin_tools()

print(mcp_tools)
```

#### 可选参数

- `sandbox`：传入已有 Sandbox 实例，工具绑定到该沙箱运行
- `sandbox_type`：未传 `sandbox` 时指定沙箱类型（如 `"base"`、`"gui"`），自动创建临时沙箱运行工具
- `whitelist` / `blacklist`：按工具名过滤导入的工具

#### 使用不同沙箱类型注册工具

```{code-cell}
# 自动创建指定类型的沙箱并注册工具
mcp_tools = MCPConfigConverter(server_configs=config).to_builtin_tools(
    sandbox_type="base",
)

# 使用已有的沙箱实例注册工具
with BaseSandbox() as sandbox:
    mcp_tools = MCPConfigConverter(server_configs=config).to_builtin_tools(
        sandbox=sandbox,
    )
```

这里选择的沙箱类型会决定转换好的工具运行时依赖的沙箱类型，因此应根据实际需求选择合适的 `sandbox_type` 或具体的 `Sandbox` 实例。

### 函数工具（Function Tool）

除了在沙箱环境中运行的工具，您还可以为Agent添加进程内函数作为工具。这些函数工具直接在当前 Python 进程中执行，而不会在沙箱隔离环境中运行，非常适合轻量级操作和计算。

函数工具提供两种创建方法：

- **`FunctionTool` 包装器**：使用 `FunctionTool` 类包装现有函数或方法
- **装饰器方法**：使用 `@function_tool` 装饰器直接标注函数

```{code-cell}
from agentscope_runtime.sandbox.tools.function_tool import (
    FunctionTool,
    function_tool,
)


class MathCalculator:
    def calculate_power(self, base: int, exponent: int) -> int:
        """计算一个数的幂。"""
        print(f"Calculating {base}^{exponent}...")
        return base**exponent


calculator = MathCalculator()


@function_tool(
    name="calculate_power",
    description="计算底数的幂次方",
)
def another_calculate_power(base: int, exponent: int) -> int:
    """计算底数的幂次方。"""
    print(f"计算 {base}^{exponent}...")
    return base**exponent


tool_0 = FunctionTool(calculator.calculate_power)
tool_1 = another_calculate_power
print(tool_0, tool_1)
```

### 工具Schema

每个工具都有一个定义的`schema`，它指定了输入参数的预期结构和类型。这个schema对于了解如何正确使用工具以及需要哪些参数非常有用。以下是查看schema的示例：

```{code-cell}
print(json.dumps(run_ipython_cell.schema, indent=4, ensure_ascii=False))
```

### 了解函数式工具设计理念

```{note}
本节解释了我们工具模块背后的设计理念，如果您只对实际使用感兴趣，可以跳过本节。
```

我们的工具模块采用**函数式接口**设计，在提供最大灵活性的同时抽象了沙箱管理的复杂性。以下是关键设计原则：

#### **1. 直观的函数调用接口**

我们的工具模块提供了一个类似函数的接口，允许您通过简单的类函数调用来调用工具。

工具的使用范式类似常规的Python函数，这样使其易于使用和集成：

```python
# 简单的函数式调用
result = run_ipython_cell(code="print('hello world')")
result = tool_instance(param1="value1", param2="value2")
```

#### **2. 灵活的执行优先级系统**

工具模块支持三个级别的沙箱执行规范，具有清晰的优先级：

- **临时沙箱**（最高优先级，初始化时指定）：`tool(sandbox=temp_sandbox, **kwargs)`
- **实例绑定沙箱**（第二优先级，通过绑定方法指定）：`bound_tool = tool.bind(sandbox)`
- **干运行模式**（最低优先级，不指定沙箱）：未指定时自动创建临时沙箱

#### **3. 不可变绑定模式**

bind方法会创建新的工具实例而不是修改现有实例：

```python
# 创建新实例，原始工具保持不变
bound_tool = original_tool.bind(sandbox=my_sandbox)
```

这确保了工具实例的线程安全，并允许同一工具的多个沙箱绑定版本共存。

## 沙箱使用

### 创建沙箱

前面的部分介绍了以工具为中心的使用方法，而本节介绍以沙箱为中心的使用方法。

您可以通过`sandbox` SDK创建不同类型的沙箱：

* **基础沙箱（Base Sandbox）**：用于在隔离环境中运行 **Python 代码** 或 **Shell 命令**。

```{code-cell}
from agentscope_runtime.sandbox import BaseSandbox

with BaseSandbox() as box:
    # 默认从 DockerHub 拉取 `agentscope/runtime-sandbox-base:latest` 镜像
    print(box.list_tools()) # 列出所有可用工具
    print(box.run_ipython_cell(code="print('hi')"))
    print(box.run_shell_command(command="echo hello"))
    input("按 Enter 键继续...")
```

* **GUI 沙箱 （GUI Sandbox）**： 提供**可视化桌面环境**，可执行鼠标、键盘以及屏幕相关操作。

  <img src="https://img.alicdn.com/imgextra/i2/O1CN01df5SaM1xKFQP4KGBW_!!6000000006424-2-tps-2958-1802.png" alt="GUI Sandbox" width="800" height="500">

```{code-cell}
from agentscope_runtime.sandbox import GuiSandbox

with GuiSandbox() as box:
    # 默认从 DockerHub 拉取 `agentscope/runtime-sandbox-gui:latest` 镜像
    print(box.list_tools()) # 列出所有可用工具
    print(box.desktop_url)  # 桌面访问链接
    print(box.computer_use(action="get_cursor_position"))  # 获取鼠标位置
    print(box.computer_use(action="get_screenshot"))       # 获取屏幕截图
    input("按 Enter 键继续...")
```

* **文件系统沙箱 （Filesystem Sandbox）**：基于 GUI 的隔离沙箱，可进行文件系统操作，如创建、读取和删除文件。

  <img src="https://img.alicdn.com/imgextra/i3/O1CN01VocM961vK85gWbJIy_!!6000000006153-2-tps-2730-1686.png" alt="GUI Sandbox" width="800" height="500">

```{code-cell}
from agentscope_runtime.sandbox import FilesystemSandbox

with FilesystemSandbox() as box:
    # 默认从 DockerHub 拉取 `agentscope/runtime-sandbox-filesystem:latest` 镜像
    print(box.list_tools()) # 列出所有可用工具
    print(box.desktop_url)  # 桌面访问链接
    box.create_directory("test")  # 创建目录
    input("按 Enter 键继续...")
```

* **浏览器沙箱（Browser Sandbox）**: 基于 GUI 的沙箱，可进行浏览器操作。

  <img src="https://img.alicdn.com/imgextra/i4/O1CN01OIq1dD1gAJMcm0RFR_!!6000000004101-2-tps-2734-1684.png" alt="GUI Sandbox" width="800" height="500">

```{code-cell}
from agentscope_runtime.sandbox import BrowserSandbox

with BrowserSandbox() as box:
    # 默认从 DockerHub 拉取 `agentscope/runtime-sandbox-browser:latest` 镜像
    print(box.list_tools()) # 列出所有可用工具
    print(box.desktop_url)  # 浏览器桌面访问链接
    box.browser_navigate("https://www.google.com/")  # 打开网页
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

```{note}
我们很快会扩展更多类型的沙箱——敬请期待！
```

### 向沙箱添加MCP服务器

MCP（模型上下文协议）是一个标准化协议，使AI应用程序能够安全地连接到外部数据源和工具。通过将MCP服务器集成到您的沙箱中，您可以在不影响安全性的情况下使用专门的工具和服务扩展沙箱的功能。

沙箱支持通过`add_mcp_servers`方法集成MCP服务器。添加后，您可以使用`list_tools`发现可用工具并使用`call_tool`执行它们。以下是添加提供时区感知的MCP的示例：

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

有关sandbox-server的更高级用法，请参阅{doc}`sandbox_advanced`了解详细说明。
```

您可以在本地机器或不同机器上启动沙箱服务器，以便于远程访问。您应该通过以下命令启动沙箱服务器：

```bash
runtime-sandbox-server
```

要连接到远程沙箱服务，只需传入`base_url`：

```python
# 连接到远程沙箱服务器（替换为实际的服务器IP）
with BaseSandbox(base_url="http://your_IP_address:8000") as box:
    print(box.run_ipython_cell(code="print('hi')"))
```

### 将 Sandbox 暴露为 MCP 服务

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

## 工具列表

* 基础工具（在所有沙箱类型中可用）
* 计算机操作工具（在`GuiSandbox`中可用）
* 文件系统工具（在`FilesystemSandbox`中可用）
* 浏览器工具（在`BrowserSandbox`中可用）

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
