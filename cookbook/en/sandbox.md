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

# Tool Sandbox

AgentScope Runtime's Sandbox is a versatile tool that provides a **secure** and **isolated** environment for a wide range of operations, including tool execution, browser automation, and file system operations. This tutorial will empower you to set up the tool sandbox dependency and run tools in an environment that you can tailor to your specific needs.

## Prerequisites

```{note}
The current sandbox environment utilizes Docker for default isolation. In addition, we offer support for Kubernetes (K8s) as a remote service backend. Looking ahead, we plan to incorporate more third-party hosting solutions in future releases.
```


````{warning}
For **Apple Silicon devices** (such as M1/M2), we recommend the following options to run an **x86** Docker environment for maximum compatibility:
* Docker Desktop: Please refer to the [Docker Desktop installation guide](https://docs.docker.com/desktop/setup/install/mac-install/) to enable Rosetta 2, ensuring compatibility with x86_64 images.
* Colima: Ensure that Rosetta 2 support is enabled. You can start [Colima](https://github.com/abiosoft/colima) with the following command to achieve compatibility: `colima start --vm-type=vz --vz-rosetta --memory 8 --cpu 1`
````

- Docker
- (Optional,  remote mode only) Kubernetes

## Setup

### Install Dependencies

First, install AgentScope Runtime with sandbox support:

```bash
pip install "agentscope-runtime[sandbox]"
```

### Prepare the Docker Images

The sandbox uses different Docker images for various functionalities. You can pull only the images you need or all of them for complete functionality:

#### Option 1: Pull All Images (Recommended)

To ensure a complete sandbox experience with all features enabled, follow the steps below to pull and tag the necessary Docker images from our repository:

```{note}
**Image Source: Alibaba Cloud Container Registry**

All Docker images are hosted on Alibaba Cloud Container Registry (ACR) for optimal performance and reliability worldwide. Images are pulled from ACR and tagged with standard names for seamless integration with the AgentScope runtime environment.
```

```bash
# Base image
docker pull agentscope-registry.ap-southeast-1.cr.aliyuncs.com/agentscope/runtime-sandbox-base:latest && docker tag agentscope-registry.ap-southeast-1.cr.aliyuncs.com/agentscope/runtime-sandbox-base:latest agentscope/runtime-sandbox-base:latest

# Filesystem image
docker pull agentscope-registry.ap-southeast-1.cr.aliyuncs.com/agentscope/runtime-sandbox-filesystem:latest && docker tag agentscope-registry.ap-southeast-1.cr.aliyuncs.com/agentscope/runtime-sandbox-filesystem:latest agentscope/runtime-sandbox-filesystem:latest

# Browser image
docker pull agentscope-registry.ap-southeast-1.cr.aliyuncs.com/agentscope/runtime-sandbox-browser:latest && docker tag agentscope-registry.ap-southeast-1.cr.aliyuncs.com/agentscope/runtime-sandbox-browser:latest agentscope/runtime-sandbox-browser:latest
```

#### Option 2: Pull Specific Images

Choose the images based on your specific needs:

| Image                | Purpose                               | When to Use                                                  |
| -------------------- | ------------------------------------- | ------------------------------------------------------------ |
| **Base Image**       | Python code execution, shell commands | Essential for basic tool execution                           |
| **Filesystem Image** | File system operations                | When you need file read/write/management                     |
| **Browser Image**    | Web browser automation                | When you need web scraping or browser control                |
| **Training Image**   | Training and evaluating agent         | Used for training and evaluating agent on some benchmark (see {doc}`training_sandbox` for details) |

### Verify Installation

You can verify that everything is set up correctly by calling `run_ipython_cell`:

```{code-cell}
import json
from agentscope_runtime.sandbox.tools.base import run_ipython_cell

# Model Context Protocol (MCP)-compatible tool call results
result = run_ipython_cell(code="print('Setup successful!')")
print(json.dumps(result, indent=4, ensure_ascii=False))
```

### (Optional) Built the Docker Images from Scratch

If you prefer to build the Docker images yourself or need custom modifications, you can build them from scratch. Please refer to {doc}`sandbox_advanced` for detailed instructions.

## Tool Usage

### Call a Tool

The most basic usage is to directly call built-in tools (such as running Python code or shell commands):

```{note}
The following two functions will execute independently in separate sandboxes.
Each function call will start an **embedded** sandbox, execute the function within it, and then close the sandbox. The lifecycle of each sandbox is confined to the duration of the function call in this way.
```

```{code-cell}
from agentscope_runtime.sandbox.tools.base import (
    run_ipython_cell,
    run_shell_command,
)

print(run_ipython_cell(code="print('hello world')"))
print(run_shell_command(command="whoami"))
```

### Bind Sandbox to a Tool

In addition to directly calling tools, you can bind a specific sandbox to a tool using the bind method. This allows you to specify which sandbox the function will run in, giving you more control over the execution environment. It's important to note that the function's type and the sandbox type must match; otherwise, the function will not execute properly. Here's how you can do it:

```{code-cell}
from agentscope_runtime.sandbox import BaseSandbox

with BaseSandbox() as sandbox:
    # Ensure the function's sandbox type matches the sandbox instance type
    assert run_ipython_cell.sandbox_type == sandbox.sandbox_type

    # Bind the sandbox to the tool functions
    func1 = run_ipython_cell.bind(sandbox=sandbox)
    func2 = run_shell_command.bind(sandbox=sandbox)

    # Execute the function within the sandbox
    print(func1(code="repo = 'agentscope-runtime'"))
    print(func1(code="print(repo)"))
    print(func2(command="whoami"))
```

### Convert MCP Server to Tools

You can also integrate external MCP servers to extend the tools. This example demonstrates how to convert MCP server configurations into built-in tools using the `MCPConfigConverter` class.

```{code-cell}
from agentscope_runtime.sandbox.tools.mcp_tool import MCPConfigConverter

mcp_tools = MCPConfigConverter(
    server_configs={
        "mcpServers": {
            "time": {
                "command": "uvx",
                "args": [
                    "mcp-server-time",
                    "--local-timezone=America/New_York",
                ],
            },
        },
    },
).to_builtin_tools()

print(mcp_tools)
```

### Function Tool

Besides the tools that run in sandbox environments, you can also add in-process functions as tools for agents. These function tools execute directly within the current Python process without requiring sandbox isolation, making them suitable for lightweight operations and calculations.

Function tools offer two creation methods:

- **`FunctionTool` wrapper**: Wrap existing functions or methods using the `FunctionTool` class
- **Decorator approach**: Use the `@function_tool` decorator to annotate functions directly

```{code-cell}
from agentscope_runtime.sandbox.tools.function_tool import (
    FunctionTool,
    function_tool,
)


class MathCalculator:
    def calculate_power(self, base: int, exponent: int) -> int:
        """Calculate the power of a number."""
        print(f"Calculating {base}^{exponent}...")
        return base**exponent


calculator = MathCalculator()


@function_tool(
    name="calculate_power",
    description="Calculate the base raised to the power of the exponent",
)
def another_calculate_power(base: int, exponent: int) -> int:
    """Calculate the base raised to the power of the exponent."""
    print(f"Calculating {base}^{exponent}...")
    return base**exponent


tool_0 = FunctionTool(calculator.calculate_power)
tool_1 = another_calculate_power
print(tool_0, tool_1)
```

### Tool Schema

Each tool has a defined `schema` that specifies the expected structure and types of its input parameters. This schema is useful for understanding how to properly use the tool and what parameters are required. Here's an example of how you can view the schema:

```{code-cell}
print(json.dumps(run_ipython_cell.schema, indent=4, ensure_ascii=False))
```

### Function-like Tool Design Philosophy

```{note}
This section explains the design principles behind our tool module. You can skip this section if you're only interested in practical usage.
```

Our tool module is designed with a **function-like interface** that abstracts the complexity of sandbox management while providing maximum flexibility. Here are the key design principles:

#### **1. Intuitive Function Call Interface**
Our tool module provides a function-like interface, allowing you to call tools with a simple function call.
Tools behave like regular Python functions, making them easy to use and integrate:

```python
# Simple function-like calls
result = run_ipython_cell(code="print('hello world')")
result = tool_instance(param1="value1", param2="value2")
```

#### **2. Flexible Sandbox Priority System**

The tool module supports three levels of sandbox specification with clear priority:

- **Temporary sandbox** (highest priority, specified during initialization): `tool(sandbox=temp_sandbox, **kwargs)`
- **Instance-bound sandbox** (second priority, specified through the binding method): `bound_tool = tool.bind(sandbox)`
- **Dry-run mode** (lowest priority, no sandbox specified): Automatically creates temporary sandbox when none specified

#### **3. Immutable Binding Pattern**

The bind method creates new tool instances rather than modifying existing ones:

```python
# Creates a new instance, original tool remains unchanged
bound_tool = original_tool.bind(sandbox=my_sandbox)
```

This ensures thread safety and allows multiple sandbox-bound versions of the same tool to coexist.

## Sandbox Usage

### Create a Sandbox

The previous section introduced tool-centered usage methods, while this section introduces sandbox-centered usage methods.

You can create different types of sandboxes via `sandbox` sdk:

* **BaseSandbox**: Basic sandbox for Python code execution and shell commands.

```{code-cell}
from agentscope_runtime.sandbox import BaseSandbox

# Create a base sandbox
with BaseSandbox() as box:
    print(box.list_tools())
    print(box.run_ipython_cell(code="print('hi')"))
    print(box.run_shell_command(command="echo hello"))
```

* **FilesystemSandbox**: Sandbox with file system operations support.

```{code-cell}
from agentscope_runtime.sandbox import FilesystemSandbox

# Create a filesystem sandbox
with FilesystemSandbox() as box:
    print(box.list_tools())
    print(box.create_directory("test"))
    print(box.list_allowed_directories())
```

* **BrowserSandbox**: Sandbox for web automation and browser control powered by [Steel Browser](https://github.com/steel-dev/steel-browser).

```{code-cell}
from agentscope_runtime.sandbox import BrowserSandbox

# Create a browser sandbox
with BrowserSandbox() as box:
    print(box.list_tools())
    print(box.browser_navigate("https://www.example.com/"))
    print(box.browser_snapshot())
```

* **TrainingSandbox**: Sandbox for training and evaluation，please refer to {doc}`training_sandbox` for details。

```{code-cell}
from agentscope_runtime.sandbox import TrainingSandbox

# Create a training sandbox
with TrainingSandbox() as box:
    profile_list = box.get_env_profile(env_type="appworld", split="train")
    print(profile_list)
```

```{note}
We'll be expanding with more types of sandboxes soon—stay tuned!
```

### Add MCP Server to Sandbox

MCP (Model Context Protocol) is a standardized protocol that enables AI applications to connect to external data sources and tools securely. By integrating MCP servers into your sandbox, you can extend the sandbox's capabilities with specialized tools and services without compromising security.

The sandbox supports integrating MCP servers via the `add_mcp_servers` method. Once added, you can discover available tools using `list_tools` and execute them with `call_tool`. Here's an example of adding a time server that provides timezone-aware time functions:

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

    # Add the MCP server to the sandbox
    sandbox.add_mcp_servers(server_configs=mcp_server_configs)

    # List all available tools (now includes MCP tools)
    print(sandbox.list_tools())

    # Use the time tool provided by the MCP server
    print(
        sandbox.call_tool(
            "get_current_time",
            arguments={
                "timezone": "America/New_York",
            },
        ),
    )
```

### Connect to Remote Sandbox

```{note}
Remote deployment is beneficial for:
* Separating comput-intensive tasks to dedicated servers
* Multiple clients sharing the same sandbox environment
* Developing on resource-constrained local machines while executing on high-performance servers
* Deploy sandbox server with K8S

For more advanced usage of sandbox-server, please refer to {doc}`sandbox_advanced` for detailed instructions.
```

You can start the sandbox server on your local machine or different machines for convenient remote access. You should start a sandbox server via:

```bash
runtime-sandbox-server
```

To connect to the remote sandbox service, pass in `base_url`:

```python
# Connect to remote sandbox server (replace with actual server IP)
with BaseSandbox(base_url="http://your_IP_address:8000") as box:
    print(box.run_ipython_cell(code="print('hi')"))
```

### Expose Sandbox as an MCP Server

Configure the local Sandbox Runtime as an MCP server named `sandbox`, so it can be invoked by MCP-compatible clients to safely execute command from sandbox via a remote sandbox server `http://127.0.0.1:8000`.

```json
{
    "mcpServers": {
        "sandbox": {
            "command": "uvx",
            "args": [
                "--from",
                "agentscope-runtime[sandbox]",
                "runtime-sandbox-mcp",
                "--type=base",
                "--base_url=http://127.0.0.1:8000"
            ],
        }
    },
}
```

#### Command Arguments

The `runtime-sandbox-mcp` command accepts the following arguments:

| Argument         | Values                            | Description                                                  |
| ---------------- | --------------------------------- | ------------------------------------------------------------ |
| `--type`         | `base` | `browser` | `filesystem` | Sandbox type to run. `base` for Python/shell, `browser` for browser automation, `filesystem` for file operations. |
| `--base_url`     | URL string                        | Base URL of a remote sandbox service. Leave empty to run locally. |
| `--bearer_token` | String token                      | Optional authentication token for secure access.             |

## Tool List

* Base Tools (Available in all sandbox types)
* Browser Tools (Available in `BrowserSandbox`)
* Filesystem Tools (Available in `FilesystemSandbox`)

| Category             | Tool Name                                                    | Description                                        |
| -------------------- | ------------------------------------------------------------ | -------------------------------------------------- |
| **Base Tools**       | `run_ipython_cell(code: str)`                                | Execute Python code in an IPython environment      |
|                      | `run_shell_command(command: str)`                            | Execute shell commands in the sandbox              |
| **Filesystem Tools** | `read_file(path: str)`                                       | Read the complete contents of a file               |
|                      | `read_multiple_files(paths: list)`                           | Read multiple files simultaneously                 |
|                      | `write_file(path: str, content: str)`                        | Create or overwrite a file with content            |
|                      | `edit_file(path: str, edits: list, dryRun: bool)`            | Make line-based edits to a text file               |
|                      | `create_directory(path: str)`                                | Create a new directory                             |
|                      | `list_directory(path: str)`                                  | List all files and directories in a path           |
|                      | `directory_tree(path: str)`                                  | Get recursive tree view of directory structure     |
|                      | `move_file(source: str, destination: str)`                   | Move or rename files and directories               |
|                      | `search_files(path: str, pattern: str, excludePatterns: list)` | Search for files matching a pattern                |
|                      | `get_file_info(path: str)`                                   | Get detailed metadata about a file or directory    |
|                      | `list_allowed_directories()`                                 | List directories the server can access             |
| **Browser Tools**    | `browser_navigate(url: str)`                                 | Navigate to a specific URL                         |
|                      | `browser_navigate_back()`                                    | Go back to the previous page                       |
|                      | `browser_navigate_forward()`                                 | Go forward to the next page                        |
|                      | `browser_close()`                                            | Close the current browser page                     |
|                      | `browser_resize(width: int, height: int)`                    | Resize the browser window                          |
|                      | `browser_click(element: str, ref: str)`                      | Click on a web element                             |
|                      | `browser_type(element: str, ref: str, text: str, submit: bool)` | Type text into an input field                      |
|                      | `browser_hover(element: str, ref: str)`                      | Hover over a web element                           |
|                      | `browser_drag(startElement: str, startRef: str, endElement: str, endRef: str)` | Drag and drop between elements                     |
|                      | `browser_select_option(element: str, ref: str, values: list)` | Select options in a dropdown                       |
|                      | `browser_press_key(key: str)`                                | Press a keyboard key                               |
|                      | `browser_file_upload(paths: list)`                           | Upload files to the page                           |
|                      | `browser_snapshot()`                                         | Capture accessibility snapshot of the current page |
|                      | `browser_take_screenshot(raw: bool, filename: str, element: str, ref: str)` | Take a screenshot of the page or element           |
|                      | `browser_pdf_save(filename: str)`                            | Save the current page as PDF                       |
|                      | `browser_tab_list()`                                         | List all open browser tabs                         |
|                      | `browser_tab_new(url: str)`                                  | Open a new tab                                     |
|                      | `browser_tab_select(index: int)`                             | Switch to a specific tab                           |
|                      | `browser_tab_close(index: int)`                              | Close a tab (current tab if index not specified)   |
|                      | `browser_wait_for(time: int, text: str, textGone: str)`      | Wait for conditions or time to pass                |
|                      | `browser_console_messages()`                                 | Get all console messages from the page             |
|                      | `browser_network_requests()`                                 | Get all network requests since page load           |
|                      | `browser_handle_dialog(accept: bool, promptText: str)`       | Handle browser dialogs (alert, confirm, prompt)    |

## Troubleshooting
If you encounter any issues while using the browser module, here are some troubleshooting steps:

### Docker Connection Error

If you encounter the following error:

```
docker.errors.DockerException: Error while fetching server API version: ('Connection aborted.', FileNotFoundError(2, 'No such file or directory'))
```

This error typically indicates that the Docker Python SDK is unable to connect to the Docker service. If you are using Colima, you need to ensure that the Docker Python SDK is configured to use Colima's Docker service. You can do this by setting the `DOCKER_HOST` environment variable:

```bash
export DOCKER_HOST=unix://$HOME/.colima/docker.sock
```

After setting the `DOCKER_HOST` environment variable, try running your command again. This should resolve the connection issue.
