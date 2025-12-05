<div align="center">

# AgentScope Runtime v1.0

[![GitHub Repo](https://img.shields.io/badge/GitHub-Repo-black.svg?logo=github)](https://github.com/agentscope-ai/agentscope-runtime)
[![PyPI](https://img.shields.io/pypi/v/agentscope-runtime?label=PyPI&color=brightgreen&logo=python)](https://pypi.org/project/agentscope-runtime/)
[![Downloads](https://static.pepy.tech/badge/agentscope-runtime)](https://pepy.tech/project/agentscope-runtime)
[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg?logo=python&label=Python)](https://python.org)
[![License](https://img.shields.io/badge/license-Apache%202.0-red.svg?logo=apache&label=License)](LICENSE)
[![Code Style](https://img.shields.io/badge/code%20style-black-black.svg?logo=python&label=CodeStyle)](https://github.com/psf/black)
[![GitHub Stars](https://img.shields.io/github/stars/agentscope-ai/agentscope-runtime?style=flat&logo=github&color=yellow&label=Stars)](https://github.com/agentscope-ai/agentscope-runtime/stargazers)
[![GitHub Forks](https://img.shields.io/github/forks/agentscope-ai/agentscope-runtime?style=flat&logo=github&color=purple&label=Forks)](https://github.com/agentscope-ai/agentscope-runtime/network)
[![Build Status](https://img.shields.io/badge/build-passing-brightgreen.svg?logo=githubactions&label=Build)](https://github.com/agentscope-ai/agentscope-runtime/actions)
[![Cookbook](https://img.shields.io/badge/📚_Cookbook-English|中文-teal.svg)](https://runtime.agentscope.io)
[![DeepWiki](https://img.shields.io/badge/DeepWiki-agentscope--runtime-navy.svg?logo=data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACwAAAAyCAYAAAAnWDnqAAAAAXNSR0IArs4c6QAAA05JREFUaEPtmUtyEzEQhtWTQyQLHNak2AB7ZnyXZMEjXMGeK/AIi+QuHrMnbChYY7MIh8g01fJoopFb0uhhEqqcbWTp06/uv1saEDv4O3n3dV60RfP947Mm9/SQc0ICFQgzfc4CYZoTPAswgSJCCUJUnAAoRHOAUOcATwbmVLWdGoH//PB8mnKqScAhsD0kYP3j/Yt5LPQe2KvcXmGvRHcDnpxfL2zOYJ1mFwrryWTz0advv1Ut4CJgf5uhDuDj5eUcAUoahrdY/56ebRWeraTjMt/00Sh3UDtjgHtQNHwcRGOC98BJEAEymycmYcWwOprTgcB6VZ5JK5TAJ+fXGLBm3FDAmn6oPPjR4rKCAoJCal2eAiQp2x0vxTPB3ALO2CRkwmDy5WohzBDwSEFKRwPbknEggCPB/imwrycgxX2NzoMCHhPkDwqYMr9tRcP5qNrMZHkVnOjRMWwLCcr8ohBVb1OMjxLwGCvjTikrsBOiA6fNyCrm8V1rP93iVPpwaE+gO0SsWmPiXB+jikdf6SizrT5qKasx5j8ABbHpFTx+vFXp9EnYQmLx02h1QTTrl6eDqxLnGjporxl3NL3agEvXdT0WmEost648sQOYAeJS9Q7bfUVoMGnjo4AZdUMQku50McDcMWcBPvr0SzbTAFDfvJqwLzgxwATnCgnp4wDl6Aa+Ax283gghmj+vj7feE2KBBRMW3FzOpLOADl0Isb5587h/U4gGvkt5v60Z1VLG8BhYjbzRwyQZemwAd6cCR5/XFWLYZRIMpX39AR0tjaGGiGzLVyhse5C9RKC6ai42ppWPKiBagOvaYk8lO7DajerabOZP46Lby5wKjw1HCRx7p9sVMOWGzb/vA1hwiWc6jm3MvQDTogQkiqIhJV0nBQBTU+3okKCFDy9WwferkHjtxib7t3xIUQtHxnIwtx4mpg26/HfwVNVDb4oI9RHmx5WGelRVlrtiw43zboCLaxv46AZeB3IlTkwouebTr1y2NjSpHz68WNFjHvupy3q8TFn3Hos2IAk4Ju5dCo8B3wP7VPr/FGaKiG+T+v+TQqIrOqMTL1VdWV1DdmcbO8KXBz6esmYWYKPwDL5b5FA1a0hwapHiom0r/cKaoqr+27/XcrS5UwSMbQAAAABJRU5ErkJggg==)](https://deepwiki.com/agentscope-ai/agentscope-runtime)
[![A2A](https://img.shields.io/badge/A2A-Agent_to_Agent-blue.svg?label=A2A)](https://a2a-protocol.org/)
[![MCP](https://img.shields.io/badge/MCP-Model_Context_Protocol-purple.svg?logo=plug&label=MCP)](https://modelcontextprotocol.io/)
[![Discord](https://img.shields.io/badge/Discord-Join_Us-blueviolet.svg?logo=discord)](https://discord.gg/eYMpfnkG8h)
[![DingTalk](https://img.shields.io/badge/DingTalk-Join_Us-orange.svg)](https://qr.dingtalk.com/action/joingroup?code=v1,k1,OmDlBXpjW+I2vWjKDsjvI9dhcXjGZi3bQiojOq3dlDw=&_dt_no_comment=1&origin=11)

[[Cookbook]](https://runtime.agentscope.io/)
[[中文README]](README_zh.md)
[[Samples]](https://github.com/agentscope-ai/agentscope-samples)

**A Production-Ready Runtime Framework for Intelligent Agent Applications**

***AgentScope Runtime** is a full-stack agent runtime that tackles two core challenges: **efficient agent deployment** and **secure sandbox execution**. It ships with foundational services such as short- and long-term memory plus agent state persistence, along with hardened sandbox infrastructure. Whether you need to orchestrate production-grade agents or guarantee safe tool interactions, AgentScope Runtime provides developer-friendly workflows with complete observability.*

*In V1.0, these services are exposed via an **adapter pattern**, enabling seamless integration with the native modules of different agent frameworks while preserving their native interfaces and behaviors, ensuring both compatibility and flexibility.*

</div>

---

## 🆕 NEWS

* **[2025-12]** We have released **AgentScope Runtime v1.0**, introducing a unified “Agent as API” white-box development experience, with enhanced multi-agent collaboration, state persistence, and cross-framework integration. This release also streamlines abstractions and modules to ensure consistency between development and production environments. Please refer to the **[CHANGELOG](https://runtime.agentscope.io/en/CHANGELOG.html)** for full update details and migration guide.

---

## ✨ Key Features

- **🏗️ Deployment Infrastructure**: Built-in services for agent state management, conversation history, long-term memory, and sandbox lifecycle control
- **🔧 Framework-Agnostic**: Not tied to any specific agent framework; seamlessly integrates with popular open-source and custom implementations
- ⚡ **Developer-Friendly**: Offers `AgentApp` for easy deployment with powerful customization options
- **📊 Observability**: Comprehensive tracking and monitoring of runtime operations
- **🔒 Sandboxed Tool Execution**: Isolated sandbox ensures safe tool execution without affecting the system
- **🛠️ Out-of-the-Box Tools & One-Click Adaptation**: Rich set of ready-to-use tools, with adapters enabling quick integration into different frameworks

> [!NOTE]
>
> **About Framework-Agnostic**: Currently, AgentScope Runtime supports the **AgentScope** framework. We plan to extend compatibility to more agent development frameworks in the future.

---

## 💬 Contact

Welcome to join our community on

| [Discord](https://discord.gg/eYMpfnkG8h)                     | DingTalk                                                     |
| ------------------------------------------------------------ | ------------------------------------------------------------ |
| <img src="https://gw.alicdn.com/imgextra/i1/O1CN01hhD1mu1Dd3BWVUvxN_!!6000000000238-2-tps-400-400.png" width="100" height="100"> | <img src="https://img.alicdn.com/imgextra/i1/O1CN01LxzZha1thpIN2cc2E_!!6000000005934-2-tps-497-477.png" width="100" height="100"> |

---

## 📋 Table of Contents

- [🚀 Quick Start](#-quick-start)
- [📚 Cookbook](#-cookbook)
- [🏗️ Deployment](#️-deployment)
- [🤝 Contributing](#-contributing)
- [📄 License](#-license)

---

## 🚀 Quick Start

### Prerequisites
- Python 3.10 or higher
- pip or uv package manager

### Installation

From PyPI:

```bash
# Install core dependencies
pip install agentscope-runtime

# Install extension
pip install "agentscope-runtime[ext]"

# Install preview version
pip install --pre agentscope-runtime
```

(Optional) From source:

```bash
# Pull the source code from GitHub
git clone -b main https://github.com/agentscope-ai/agentscope-runtime.git
cd agentscope-runtime

# Install core dependencies
pip install -e .
```

### Agent App Example

This example demonstrates how to create an agent API server using agentscope `ReActAgent` and `AgentApp`.  To run a minimal `AgentScope` Agent with AgentScope Runtime, you generally need to implement:

1. **`@agent_app.init`** – Initialize services/resources at startup
2. **`@agent_app.query(framework="agentscope")`** – Core logic for handling requests, **must use** `stream_printing_messages` to `yield msg, last` for streaming output
3. **`@agent_app.shutdown`** – Clean up services/resources on exit


```python
import os

from agentscope.agent import ReActAgent
from agentscope.model import DashScopeChatModel
from agentscope.formatter import DashScopeChatFormatter
from agentscope.tool import Toolkit, execute_python_code
from agentscope.pipeline import stream_printing_messages

from agentscope_runtime.engine import AgentApp
from agentscope_runtime.engine.schemas.agent_schemas import AgentRequest
from agentscope_runtime.adapters.agentscope.memory import (
    AgentScopeSessionHistoryMemory,
)
from agentscope_runtime.engine.services.agent_state import (
    InMemoryStateService,
)
from agentscope_runtime.engine.services.session_history import (
    InMemorySessionHistoryService,
)

agent_app = AgentApp(
    app_name="Friday",
    app_description="A helpful assistant",
)


@agent_app.init
async def init_func(self):
    self.state_service = InMemoryStateService()
    self.session_service = InMemorySessionHistoryService()

    await self.state_service.start()
    await self.session_service.start()


@agent_app.shutdown
async def shutdown_func(self):
    await self.state_service.stop()
    await self.session_service.stop()


@agent_app.query(framework="agentscope")
async def query_func(
    self,
    msgs,
    request: AgentRequest = None,
    **kwargs,
):
    session_id = request.session_id
    user_id = request.user_id

    state = await self.state_service.export_state(
        session_id=session_id,
        user_id=user_id,
    )

    toolkit = Toolkit()
    toolkit.register_tool_function(execute_python_code)

    agent = ReActAgent(
        name="Friday",
        model=DashScopeChatModel(
            "qwen-turbo",
            api_key=os.getenv("DASHSCOPE_API_KEY"),
            stream=True,
        ),
        sys_prompt="You're a helpful assistant named Friday.",
        toolkit=toolkit,
        memory=AgentScopeSessionHistoryMemory(
            service=self.session_service,
            session_id=session_id,
            user_id=user_id,
        ),
        formatter=DashScopeChatFormatter(),
    )
    agent.set_console_output_enabled(enabled=False)

    if state:
        agent.load_state_dict(state)

    async for msg, last in stream_printing_messages(
        agents=[agent],
        coroutine_task=agent(msgs),
    ):
        yield msg, last

    state = agent.state_dict()

    await self.state_service.save_state(
        user_id=user_id,
        session_id=session_id,
        state=state,
    )


agent_app.run(host="127.0.0.1", port=8090)
```

The server will start and listen on: `http://localhost:8090/process`. You can send JSON input to the API using `curl`:

```bash
curl -N \
  -X POST "http://localhost:8090/process" \
  -H "Content-Type: application/json" \
  -d '{
    "input": [
      {
        "role": "user",
        "content": [
          { "type": "text", "text": "What is the capital of France?" }
        ]
      }
    ]
  }'
```

You’ll see output streamed in **Server-Sent Events (SSE)** format:

```bash
data: {"sequence_number":0,"object":"response","status":"created", ... }
data: {"sequence_number":1,"object":"response","status":"in_progress", ... }
data: {"sequence_number":2,"object":"message","status":"in_progress", ... }
data: {"sequence_number":3,"object":"content","status":"in_progress","text":"The" }
data: {"sequence_number":4,"object":"content","status":"in_progress","text":" capital of France is Paris." }
data: {"sequence_number":5,"object":"message","status":"completed","text":"The capital of France is Paris." }
data: {"sequence_number":6,"object":"response","status":"completed", ... }
```

### Sandbox Example

These examples demonstrate how to create sandboxed environments and execute tools within them, with some examples featuring interactive frontend interfaces accessible via VNC (Virtual Network Computing):

> [!NOTE]
>
> Current version requires Docker or Kubernetes to be installed and running on your system. Please refer to [this tutorial](https://runtime.agentscope.io/en/sandbox.html) for more details.
>
> If you plan to use the sandbox on a large scale in production, we recommend deploying it directly in Alibaba Cloud for managed hosting: [One-click deploy sandbox on Alibaba Cloud](https://computenest.console.aliyun.com/service/instance/create/default?ServiceName=AgentScope%20Runtime%20%E6%B2%99%E7%AE%B1%E7%8E%AF%E5%A2%83)

#### Base Sandbox

Use for running **Python code** or **shell commands** in an isolated environment.

```python
from agentscope_runtime.sandbox import BaseSandbox

with BaseSandbox() as box:
    # By default, pulls `agentscope/runtime-sandbox-base:latest` from DockerHub
    print(box.list_tools()) # List all available tools
    print(box.run_ipython_cell(code="print('hi')"))  # Run Python code
    print(box.run_shell_command(command="echo hello"))  # Run shell command
    input("Press Enter to continue...")
```

#### GUI Sandbox

Provides a **virtual desktop** environment for mouse, keyboard, and screen operations.

<img src="https://img.alicdn.com/imgextra/i2/O1CN01df5SaM1xKFQP4KGBW_!!6000000006424-2-tps-2958-1802.png" alt="GUI Sandbox" width="800" height="500">

```python
from agentscope_runtime.sandbox import GuiSandbox

with GuiSandbox() as box:
    # By default, pulls `agentscope/runtime-sandbox-gui:latest` from DockerHub
    print(box.list_tools()) # List all available tools
    print(box.desktop_url)  # Web desktop access URL
    print(box.computer_use(action="get_cursor_position"))  # Get mouse cursor position
    print(box.computer_use(action="get_screenshot"))       # Capture screenshot
    input("Press Enter to continue...")
```

#### Browser Sandbox

A GUI-based sandbox with **browser operations** inside an isolated sandbox.

<img src="https://img.alicdn.com/imgextra/i4/O1CN01OIq1dD1gAJMcm0RFR_!!6000000004101-2-tps-2734-1684.png" alt="GUI Sandbox" width="800" height="500">

```python
from agentscope_runtime.sandbox import BrowserSandbox

with BrowserSandbox() as box:
    # By default, pulls `agentscope/runtime-sandbox-browser:latest` from DockerHub
    print(box.list_tools()) # List all available tools
    print(box.desktop_url)  # Web desktop access URL
    box.browser_navigate("https://www.google.com/")  # Open a webpage
    input("Press Enter to continue...")
```

#### Filesystem Sandbox

A GUI-based sandbox with **file system operations** such as creating, reading, and deleting files.

<img src="https://img.alicdn.com/imgextra/i3/O1CN01VocM961vK85gWbJIy_!!6000000006153-2-tps-2730-1686.png" alt="GUI Sandbox" width="800" height="500">

```python
from agentscope_runtime.sandbox import FilesystemSandbox

with FilesystemSandbox() as box:
    # By default, pulls `agentscope/runtime-sandbox-filesystem:latest` from DockerHub
    print(box.list_tools()) # List all available tools
    print(box.desktop_url)  # Web desktop access URL
    box.create_directory("test")  # Create a directory
    input("Press Enter to continue...")
```

#### Mobile Sandbox

Provides a **sandboxed Android emulator environment** that allows executing various mobile operations, such as tapping, swiping, inputting text, and taking screenshots.

##### Prerequisites

- **Linux Host**:
  When running on a Linux host, this sandbox requires the `binder` and `ashmem` kernel modules to be loaded. If they are missing, execute the following commands on your host to install and load the required modules:

  ```bash
  # 1. Install extra kernel modules
  sudo apt update && sudo apt install -y linux-modules-extra-`uname -r`

  # 2. Load modules and create device nodes
  sudo modprobe binder_linux devices="binder,hwbinder,vndbinder"
  sudo modprobe ashmem_linux
- **Architecture Compatibility**:
  When running on an ARM64/aarch64 architecture (e.g., Apple M-series chips), you may encounter compatibility or performance issues. It is recommended to run on an x86_64 host.
```python
from agentscope_runtime.sandbox import MobileSandbox

with MobileSandbox() as box:
    # By default, pulls 'agentscope/runtime-sandbox-mobile:latest' from DockerHub
    print(box.list_tools()) # List all available tools
    print(box.mobile_get_screen_resolution()) # Get the screen resolution
    print(box.mobile_tap(x=500, y=1000)) # Tap at coordinate (500, 1000)
    print(box.mobile_input_text("Hello from AgentScope!")) # Input text
    print(box.mobile_key_event(3)) # Sends a HOME key event (KeyCode: 3)
    screenshot_result = box.mobile_get_screenshot() # Get the current screenshot
    input("Press Enter to continue...")
```

> [!NOTE]
>
> To add tools to the AgentScope `Toolkit`:
>
> 1. Wrap sandbox tool with `sandbox_tool_adapter`, so the AgentScope agent can call them:
>
>    ```python
>    from agentscope_runtime.adapters.agentscope.tool import sandbox_tool_adapter
>
>    wrapped_tool = sandbox_tool_adapter(sandbox.browser_navigate)
>    ```
>
> 2. Register the tool with `register_tool_function`:
>
>    ```python
>    toolkit = Toolkit()
>    Toolkit.register_tool_function(wrapped_tool)
>    ```

#### Configuring Sandbox Image Registry, Namespace, and Tag

##### 1. Registry

If pulling images from DockerHub fails (for example, due to network restrictions), you can switch the image source to Alibaba Cloud Container Registry for faster access:

```bash
export RUNTIME_SANDBOX_REGISTRY="agentscope-registry.ap-southeast-1.cr.aliyuncs.com"
```

##### 2. Namespace

A namespace is used to distinguish images of different teams or projects. You can customize the namespace via an environment variable:

```bash
export RUNTIME_SANDBOX_IMAGE_NAMESPACE="agentscope"
```

For example, here `agentscope` will be used as part of the image path.

##### 3. Tag

An image tag specifies the version of the image, for example:

```bash
export RUNTIME_SANDBOX_IMAGE_TAG="preview"
```

Details:

- Default is `latest`, which means the image version matches the PyPI latest release.
- `preview` means the latest preview version built in sync with the **GitHub main branch**.
- You can also use a specified version number such as `20250909`. You can check all available image versions at [DockerHub](https://hub.docker.com/repositories/agentscope).

##### 4. Complete Image Path

The sandbox SDK will build the full image path based on the above environment variables:

```bash
<RUNTIME_SANDBOX_REGISTRY>/<RUNTIME_SANDBOX_IMAGE_NAMESPACE>/runtime-sandbox-base:<RUNTIME_SANDBOX_IMAGE_TAG>
```

Example:

```bash
agentscope-registry.ap-southeast-1.cr.aliyuncs.com/agentscope/runtime-sandbox-base:preview
```

---

#### Serverless Sandbox Deployment

AgentScope Runtime also supports serverless deployment, which is suitable for running sandboxes in a serverless environment,
[Alibaba Cloud Function Compute (FC)](https://help.aliyun.com/zh/functioncompute/fc/) or [Alibaba Cloud AgentRun](https://docs.agent.run/).

First, please refer to the [documentation](https://runtime.agentscope.io/en/sandbox/advanced.html#optional-function-compute-fc-settings) to configure the serverless environment variables.
Make `CONTAINER_DEPLOYMENT` to `fc` or `agentrun` to enable serverless deployment.

Then, start a sandbox server, use the `--config` option to specify a serverless environment setup:

```bash
# This command will load the settings defined in the `custom.env` file
runtime-sandbox-server --config fc.env
```
After the server starts, you can access the sandbox server at baseurl `http://localhost:8000` and invoke sandbox tools described above.

## 📚 Cookbook

- **[📖 Cookbook](https://runtime.agentscope.io/en/intro.html)**: Comprehensive tutorials
- **[💡 Concept](https://runtime.agentscope.io/en/concept.html)**: Core concepts and architecture overview
- **[🚀 Quick Start](https://runtime.agentscope.io/en/quickstart.html)**: Quick start tutorial
- **[🏠 Demo House](https://runtime.agentscope.io/en/demohouse.html)**: Rich example projects
- **[📋 API Reference](https://runtime.agentscope.io/en/api/index.html)**: Complete API documentation

---

## 🏗️ Deployment

The `AgentApp` exposes a `deploy` method that takes a `DeployManager` instance and deploys the agent.

* The service port is set as the parameter `port` when creating the `LocalDeployManager`.
* The service endpoint path is set as the parameter `endpoint_path` to `/process` when deploying the agent.

* The deployer will automatically add common agent protocols, such as **A2A**, **Response API**.

After deployment, users can access the service at `http://localhost:8090/process:

```python
from agentscope_runtime.engine.deployers import LocalDeployManager

# Create deployment manager
deployer = LocalDeployManager(
    host="0.0.0.0",
    port=8090,
)

# Deploy the app as a streaming service
deploy_result = await app.deploy(deployer=deployer)

```

After deployment, users can also access this service using the Response API of the OpenAI SDK:

```python
from openai import OpenAI

client = OpenAI(base_url="http://0.0.0.0:8090/compatible-mode/v1")

response = client.responses.create(
  model="any_name",
  input="What is the weather in Beijing?"
)

print(response)
```

Besides, `DeployManager` also supports serverless deployments, such as deploying your agent app
to [ModelStudio](https://bailian.console.aliyun.com/?admin=1&tab=doc#/doc/?type=app&url=2983030)
or [AgentRun](https://docs.agent.run/).

```python
from agentscope_runtime.engine.deployers import ModelStudioDeployManager
# Create deployment manager
deployer = ModelstudioDeployManager(
    oss_config=OSSConfig(
        access_key_id=os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_ID"),
        access_key_secret=os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_SECRET"),
    ),
    modelstudio_config=ModelstudioConfig(
        workspace_id=os.environ.get("MODELSTUDIO_WORKSPACE_ID"),
        access_key_id=os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_ID"),
        access_key_secret=os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_SECRET"),
        dashscope_api_key=os.environ.get("DASHSCOPE_API_KEY"),
    ),
)

# Deploy to ModelStudio
result = await app.deploy(
    deployer,
    deploy_name="agent-app-example",
    telemetry_enabled=True,
    requirements=["agentscope", "fastapi", "uvicorn"],
    environment={
        "PYTHONPATH": "/app",
        "DASHSCOPE_API_KEY": os.environ.get("DASHSCOPE_API_KEY"),
    },
)
```

For more advanced serverless deployment guides, please refer to the [documentation](https://runtime.agentscope.io/en/advanced_deployment.html#method-4-modelstudio-deployment).

---

## 🤝 Contributing

We welcome contributions from the community! Here's how you can help:

### 🐛 Bug Reports
- Use GitHub Issues to report bugs
- Include detailed reproduction steps
- Provide system information and logs

### 💡 Feature Requests
- Discuss new ideas in GitHub Discussions
- Follow the feature request template
- Consider implementation feasibility

### 🔧 Code Contributions
1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

For detailed contributing guidelines, please see  [CONTRIBUTE](cookbook/en/contribute.md).

---

## 📄 License

AgentScope Runtime is released under the [Apache License 2.0](LICENSE).

```
Copyright 2025 Tongyi Lab

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
```

## Contributors ✨
<!-- ALL-CONTRIBUTORS-BADGE:START - Do not remove or modify this section -->
[![All Contributors](https://img.shields.io/badge/all_contributors-25-orange.svg?style=flat-square)](#contributors-)
<!-- ALL-CONTRIBUTORS-BADGE:END -->

Thanks goes to these wonderful people ([emoji key](https://allcontributors.org/emoji-key/)):

<!-- ALL-CONTRIBUTORS-LIST:START - Do not remove or modify this section -->
<!-- prettier-ignore-start -->
<!-- markdownlint-disable -->
<table>
  <tbody>
    <tr>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/rayrayraykk"><img src="https://avatars.githubusercontent.com/u/39145382?v=4?s=100" width="100px;" alt="Weirui Kuang"/><br /><sub><b>Weirui Kuang</b></sub></a><br /><a href="https://github.com/agentscope-ai/agentscope-runtime/commits?author=rayrayraykk" title="Code">💻</a> <a href="https://github.com/agentscope-ai/agentscope-runtime/pulls?q=is%3Apr+reviewed-by%3Arayrayraykk" title="Reviewed Pull Requests">👀</a> <a href="#maintenance-rayrayraykk" title="Maintenance">🚧</a> <a href="#projectManagement-rayrayraykk" title="Project Management">📆</a></td>
      <td align="center" valign="top" width="14.28%"><a href="http://www.bruceluo.net/"><img src="https://avatars.githubusercontent.com/u/7297307?v=4?s=100" width="100px;" alt="Bruce Luo"/><br /><sub><b>Bruce Luo</b></sub></a><br /><a href="https://github.com/agentscope-ai/agentscope-runtime/commits?author=zhilingluo" title="Code">💻</a> <a href="https://github.com/agentscope-ai/agentscope-runtime/pulls?q=is%3Apr+reviewed-by%3Azhilingluo" title="Reviewed Pull Requests">👀</a> <a href="#example-zhilingluo" title="Examples">💡</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/zzhangpurdue"><img src="https://avatars.githubusercontent.com/u/5746653?v=4?s=100" width="100px;" alt="Zhicheng Zhang"/><br /><sub><b>Zhicheng Zhang</b></sub></a><br /><a href="https://github.com/agentscope-ai/agentscope-runtime/commits?author=zzhangpurdue" title="Code">💻</a> <a href="https://github.com/agentscope-ai/agentscope-runtime/pulls?q=is%3Apr+reviewed-by%3Azzhangpurdue" title="Reviewed Pull Requests">👀</a> <a href="https://github.com/agentscope-ai/agentscope-runtime/commits?author=zzhangpurdue" title="Documentation">📖</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/ericczq"><img src="https://avatars.githubusercontent.com/u/116273607?v=4?s=100" width="100px;" alt="ericczq"/><br /><sub><b>ericczq</b></sub></a><br /><a href="https://github.com/agentscope-ai/agentscope-runtime/commits?author=ericczq" title="Code">💻</a> <a href="https://github.com/agentscope-ai/agentscope-runtime/commits?author=ericczq" title="Documentation">📖</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/qbc2016"><img src="https://avatars.githubusercontent.com/u/22984042?v=4?s=100" width="100px;" alt="qbc"/><br /><sub><b>qbc</b></sub></a><br /><a href="https://github.com/agentscope-ai/agentscope-runtime/pulls?q=is%3Apr+reviewed-by%3Aqbc2016" title="Reviewed Pull Requests">👀</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/rankesterc"><img src="https://avatars.githubusercontent.com/u/114560457?v=4?s=100" width="100px;" alt="Ran Chen"/><br /><sub><b>Ran Chen</b></sub></a><br /><a href="https://github.com/agentscope-ai/agentscope-runtime/commits?author=rankesterc" title="Code">💻</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/jinliyl"><img src="https://avatars.githubusercontent.com/u/6469360?v=4?s=100" width="100px;" alt="jinliyl"/><br /><sub><b>jinliyl</b></sub></a><br /><a href="https://github.com/agentscope-ai/agentscope-runtime/commits?author=jinliyl" title="Code">💻</a> <a href="https://github.com/agentscope-ai/agentscope-runtime/commits?author=jinliyl" title="Documentation">📖</a></td>
    </tr>
    <tr>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/Osier-Yi"><img src="https://avatars.githubusercontent.com/u/8287381?v=4?s=100" width="100px;" alt="Osier-Yi"/><br /><sub><b>Osier-Yi</b></sub></a><br /><a href="https://github.com/agentscope-ai/agentscope-runtime/commits?author=Osier-Yi" title="Code">💻</a> <a href="https://github.com/agentscope-ai/agentscope-runtime/commits?author=Osier-Yi" title="Documentation">📖</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/kevinlin09"><img src="https://avatars.githubusercontent.com/u/26913335?v=4?s=100" width="100px;" alt="Kevin Lin"/><br /><sub><b>Kevin Lin</b></sub></a><br /><a href="https://github.com/agentscope-ai/agentscope-runtime/commits?author=kevinlin09" title="Code">💻</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://davdgao.github.io/"><img src="https://avatars.githubusercontent.com/u/102287034?v=4?s=100" width="100px;" alt="DavdGao"/><br /><sub><b>DavdGao</b></sub></a><br /><a href="https://github.com/agentscope-ai/agentscope-runtime/pulls?q=is%3Apr+reviewed-by%3ADavdGao" title="Reviewed Pull Requests">👀</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/FLyLeaf-coder"><img src="https://avatars.githubusercontent.com/u/122603493?v=4?s=100" width="100px;" alt="FlyLeaf"/><br /><sub><b>FlyLeaf</b></sub></a><br /><a href="https://github.com/agentscope-ai/agentscope-runtime/commits?author=FLyLeaf-coder" title="Code">💻</a> <a href="https://github.com/agentscope-ai/agentscope-runtime/commits?author=FLyLeaf-coder" title="Documentation">📖</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/jinghuan-Chen"><img src="https://avatars.githubusercontent.com/u/42742857?v=4?s=100" width="100px;" alt="jinghuan-Chen"/><br /><sub><b>jinghuan-Chen</b></sub></a><br /><a href="https://github.com/agentscope-ai/agentscope-runtime/commits?author=jinghuan-Chen" title="Code">💻</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/Sodawyx"><img src="https://avatars.githubusercontent.com/u/34974468?v=4?s=100" width="100px;" alt="Yuxuan Wu"/><br /><sub><b>Yuxuan Wu</b></sub></a><br /><a href="https://github.com/agentscope-ai/agentscope-runtime/commits?author=Sodawyx" title="Code">💻</a> <a href="https://github.com/agentscope-ai/agentscope-runtime/commits?author=Sodawyx" title="Documentation">📖</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/TianYu92"><img src="https://avatars.githubusercontent.com/u/12960468?v=4?s=100" width="100px;" alt="Fear1es5"/><br /><sub><b>Fear1es5</b></sub></a><br /><a href="https://github.com/agentscope-ai/agentscope-runtime/issues?q=author%3ATianYu92" title="Bug reports">🐛</a></td>
    </tr>
    <tr>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/ms-cs"><img src="https://avatars.githubusercontent.com/u/43086458?v=4?s=100" width="100px;" alt="zhiyong"/><br /><sub><b>zhiyong</b></sub></a><br /><a href="https://github.com/agentscope-ai/agentscope-runtime/commits?author=ms-cs" title="Code">💻</a> <a href="https://github.com/agentscope-ai/agentscope-runtime/issues?q=author%3Ams-cs" title="Bug reports">🐛</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/jooojo"><img src="https://avatars.githubusercontent.com/u/11719425?v=4?s=100" width="100px;" alt="jooojo"/><br /><sub><b>jooojo</b></sub></a><br /><a href="https://github.com/agentscope-ai/agentscope-runtime/commits?author=jooojo" title="Code">💻</a> <a href="https://github.com/agentscope-ai/agentscope-runtime/issues?q=author%3Ajooojo" title="Bug reports">🐛</a></td>
      <td align="center" valign="top" width="14.28%"><a href="http://ceshihao.github.io"><img src="https://avatars.githubusercontent.com/u/7711875?v=4?s=100" width="100px;" alt="Zheng Dayu"/><br /><sub><b>Zheng Dayu</b></sub></a><br /><a href="https://github.com/agentscope-ai/agentscope-runtime/commits?author=ceshihao" title="Code">💻</a> <a href="https://github.com/agentscope-ai/agentscope-runtime/issues?q=author%3Aceshihao" title="Bug reports">🐛</a></td>
      <td align="center" valign="top" width="14.28%"><a href="http://lokk.cn/about"><img src="https://avatars.githubusercontent.com/u/39740818?v=4?s=100" width="100px;" alt="quanyu"/><br /><sub><b>quanyu</b></sub></a><br /><a href="https://github.com/agentscope-ai/agentscope-runtime/commits?author=taoquanyus" title="Code">💻</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/Littlegrace111"><img src="https://avatars.githubusercontent.com/u/3880455?v=4?s=100" width="100px;" alt="Grace Wu"/><br /><sub><b>Grace Wu</b></sub></a><br /><a href="https://github.com/agentscope-ai/agentscope-runtime/commits?author=Littlegrace111" title="Code">💻</a> <a href="https://github.com/agentscope-ai/agentscope-runtime/commits?author=Littlegrace111" title="Documentation">📖</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/pitt-liang"><img src="https://avatars.githubusercontent.com/u/8534560?v=4?s=100" width="100px;" alt="LiangQuan"/><br /><sub><b>LiangQuan</b></sub></a><br /><a href="https://github.com/agentscope-ai/agentscope-runtime/commits?author=pitt-liang" title="Code">💻</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://lishengcn.cn"><img src="https://avatars.githubusercontent.com/u/12003270?v=4?s=100" width="100px;" alt="ls"/><br /><sub><b>ls</b></sub></a><br /><a href="https://github.com/agentscope-ai/agentscope-runtime/commits?author=lishengzxc" title="Code">💻</a> <a href="#design-lishengzxc" title="Design">🎨</a></td>
    </tr>
    <tr>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/iSample"><img src="https://avatars.githubusercontent.com/u/12894421?v=4?s=100" width="100px;" alt="iSample"/><br /><sub><b>iSample</b></sub></a><br /><a href="https://github.com/agentscope-ai/agentscope-runtime/commits?author=iSample" title="Code">💻</a> <a href="https://github.com/agentscope-ai/agentscope-runtime/commits?author=iSample" title="Documentation">📖</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/XiuShenAl"><img src="https://avatars.githubusercontent.com/u/242360128?v=4?s=100" width="100px;" alt="XiuShenAl"/><br /><sub><b>XiuShenAl</b></sub></a><br /><a href="https://github.com/agentscope-ai/agentscope-runtime/commits?author=XiuShenAl" title="Code">💻</a> <a href="https://github.com/agentscope-ai/agentscope-runtime/commits?author=XiuShenAl" title="Documentation">📖</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/k-farruh"><img src="https://avatars.githubusercontent.com/u/33511681?v=4?s=100" width="100px;" alt="Farruh Kushnazarov"/><br /><sub><b>Farruh Kushnazarov</b></sub></a><br /><a href="https://github.com/agentscope-ai/agentscope-runtime/commits?author=k-farruh" title="Documentation">📖</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/fengxsong"><img src="https://avatars.githubusercontent.com/u/7008971?v=4?s=100" width="100px;" alt="fengxsong"/><br /><sub><b>fengxsong</b></sub></a><br /><a href="https://github.com/agentscope-ai/agentscope-runtime/issues?q=author%3Afengxsong" title="Bug reports">🐛</a></td>
    </tr>
  </tbody>
  <tfoot>
    <tr>
      <td align="center" size="13px" colspan="7">
        <img src="https://raw.githubusercontent.com/all-contributors/all-contributors-cli/1b8533af435da9854653492b1327a23a4dbd0a10/assets/logo-small.svg">
          <a href="https://all-contributors.js.org/docs/en/bot/usage">Add your contributions</a>
        </img>
      </td>
    </tr>
  </tfoot>
</table>

<!-- markdownlint-restore -->
<!-- prettier-ignore-end -->

<!-- ALL-CONTRIBUTORS-LIST:END -->

This project follows the [all-contributors](https://github.com/all-contributors/all-contributors) specification. Contributions of any kind welcome!