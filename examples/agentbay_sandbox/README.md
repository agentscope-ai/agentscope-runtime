# AgentBay SDK Integration into Agentscope-Runtime – Research Proposal

## What is AgentBay?

AgentBay is a GUI sandbox environment provided by Alibaba Cloud.
It offers four types of sandbox environments: **Code Space**, **Browser Use**, **Computer Use**, and **Mobile Use**.

AgentBay can be integrated via **MCP Server** or **AgentBay SDK**. The SDK is open source.

- **AgentBay SDK GitHub Repository**: https://github.com/aliyun/wuying-agentbay-sdk
- **AgentBay Cloud Product Page**: https://www.aliyun.com/product/agentbay

## AgentBay Capabilities

- **New Sandbox Types**: Code Space, Browser Use, Computer Use, Mobile Use
- **Integration Methods**: MCP Server and AgentBay SDK

### Supported Image Types

- `linux_latest` – Linux environment
- `windows_latest` – Windows environment
- `browser_latest` – Browser automation environment
- `code_latest` – Code execution environment
- `mobile_latest` – Mobile device environment

### Supported Tool Operations

- **Basic Operations**: `run_shell_command`, `run_ipython_cell`, `screenshot`
- **File Operations**: `read_file`, `write_file`, `list_directory`, `create_directory`, `move_file`, `delete_file`
- **Browser Operations** *(browser_latest image)*: `browser_navigate`, `browser_click`, `browser_input`

## Integrating AgentBay into Agentscope-Runtime

Currently, the sandbox containers for Agentscope-Runtime are implemented based on Docker, and the cloud containers are managed via Kubernetes.

Integrating AgentBay into Agentscope-Runtime allows users to choose **AgentBay’s GUI cloud sandbox** in addition to Docker-based sandboxes.

### Key Idea

AgentBay is similar to cloud sandbox products like **e2b** or **Daytona**, offering **API-key based access without deployment**.

We can wrap AgentBay as an **AgentBaySandbox** inside Agentscope-Runtime, serving as another cloud sandbox option.
The same logic could be reused for e2b integration.

Since the AgentBay sandbox does not depend on local containers, we introduce a `CloudSandbox` base class (inheriting from `Sandbox`), allowing Agentscope-Runtime to support both container-based and cloud-native sandboxes, with consistent usage patterns.

------

### 1. Core Architecture Integration

- **Add Sandbox Type**: `SandboxType.AGENTBAY` enum for creating AgentBay sandboxes, supporting dynamic extension.
- **CloudSandbox Base Class**: Abstract base class for cloud-based sandboxes, using cloud APIs instead of container management. Extensible for other cloud providers.
- **AgentbaySandbox Implementation**: Inherits from `CloudSandbox`, uses AgentBay API to access the cloud sandbox, implementing full tool mapping and error handling.
- **SandboxService Support**: Maintains compatibility with existing `sandbox_service` calls, includes special handling for AgentBay sandbox type, supports session management and resource cleanup.

### 2. Class Hierarchy

```
Sandbox (base class)
└── CloudSandbox (cloud sandbox base class)
    └── AgentbaySandbox (AgentBay implementation)
```

### 3. File Structure

```
src/agentscope_runtime/sandbox/
├── enums.py                          # Add AGENTBAY enum
├── box/
│   ├── cloud/
│   │   ├── __init__.py               # New
│   │   └── cloud_sandbox.py          # New CloudSandbox base class
│   └── agentbay/
│       ├── __init__.py               # New
│       └── agentbay_sandbox.py       # New AgentbaySandbox implementation
└── __init__.py                       # Update exports
```

------

### 4. Service Layer Integration

- **Registration Mechanism**: Use `@SandboxRegistry.register` decorator for sandbox registration.
- **Service Integration**: Add special handling for AgentBay in `SandboxService`.
- **Compatibility**: Ensure full compatibility with existing sandbox APIs.
- **Lifecycle Management**: Support creation, connection, and cleanup of AgentBay sessions.

## Using AgentBay Sandbox

### 0. Set Environment Variables

```bash
pip install "agentscope-runtime[ext]"
export AGENTBAY_API_KEY='your_agentbay_api_key'
export DASHSCOPE_API_KEY='your_dashscope_api_key' # optional
```

### 1. Direct Usage

```python
from agentscope_runtime.sandbox import AgentbaySandbox

sandbox = AgentbaySandbox(
    api_key="your_api_key",
    image_id="linux_latest"
)

result = sandbox.call_tool("run_shell_command", {"command": "echo 'Hello'"})
```

### 2. Using SandboxService

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

## Demo Execution

```bash
# AgentBay sandbox demo
python examples/agentbay_sandbox/agentbay_sandbox_demo.py

# Model calls using AgentBay sandbox demo
python examples/agentbay_sandbox/agentscope_use_agentbay_sandbox.py
```
