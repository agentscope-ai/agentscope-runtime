# E2B Desktop Sandbox Documentation

## Overview

E2bSandBox is a GUI sandbox environment built on the E2B cloud desktop service that allows users to remotely control desktop environments in the cloud.

## Features

### E2B Desktop Sandbox (E2bSandBox)

- **Environment Type**: Cloud desktop environment
- **Provider**: E2B Desktop
- **Security Level**: High
- **Access Method**: E2B Desktop Python SDK invocation

## Supported Operations

### Desktop Control Tools

- click: Click screen coordinates
- right_click: Right-click
- type_text: Input text
- press_key: Press key
- launch_app: Launch application
- click_and_type: Click and input text

### Command Line Tools

- run_shell_command: Run shell commands

### System Tools

- screenshot: Take screenshots

## Integration with Agentscope-Runtime

The E2B Desktop Sandbox has been integrated into Agentscope-Runtime, providing a similar user experience to Docker sandboxes.

## E2B Sandbox Integration into Agentscope-Runtime:

Currently, Agentscope-Runtime's sandbox containers are implemented based on Docker, and cloud containers are implemented based on Kubernetes. Integrating E2B Sandbox into AgentScope-Runtime provides users with another choice for cloud sandbox environments, allowing them to choose between Docker container sandboxes and E2B sandboxes.

### Core Concept:

The core idea is to encapsulate the E2B Sandbox as a Sandbox integration into AgentScope-Runtime, serving as another cloud sandbox option. Since E2B Sandbox does not depend on containers, we create the [CloudSandbox](file:///Users/zlh/PycharmProjects/1/agentscope-runtime/src/agentscope_runtime/sandbox/box/cloud/cloud_sandbox.py#L18-L253) base class inheriting from the [Sandbox](file:///Users/zlh/PycharmProjects/1/agentscope-runtime/src/agentscope_runtime/sandbox/box/sandbox.py#L14-L170) class. This enables Agentscope-Runtime to support both traditional container sandboxes and cloud-native sandboxes, maintaining consistency with traditional container sandboxes in usage.

### 1. Core Architecture Integration

- **New Sandbox Type**: [SandboxType.E2B](file:///Users/zlh/PycharmProjects/1/agentscope-runtime/src/agentscope_runtime/sandbox/enums.py#L74-L74) enumeration for creating E2B Sandboxes, supporting dynamic enumeration extension
- **CloudSandbox Base Class**: Abstract base class providing unified interface for cloud service sandboxes, not dependent on container management, communicating directly through cloud APIs, extensible to different cloud providers
- **E2bSandBox Implementation**: Inherits from [CloudSandbox](file:///Users/zlh/PycharmProjects/1/agentscope-runtime/src/agentscope_runtime/sandbox/box/cloud/cloud_sandbox.py#L18-L253), accesses cloud sandboxes directly through E2B SDK, implementing complete tool mapping and error handling
- **SandboxService Support**: Maintains compatibility with existing [sandbox_service](file:///Users/zlh/PycharmProjects/1/agentscope-runtime/src/agentscope_runtime/engine/services/sandbox/sandbox_service.py#L0-L210) calling methods, specially handles E2B sandbox types, resource cleanup

### 2. Class Hierarchy Structure

```
Sandbox (Base Class)
└── CloudSandbox (Cloud Sandbox Base Class)
    └── E2bSandBox (E2B Desktop Implementation)
```


### 3. File Structure

```
src/agentscope_runtime/sandbox/
├── enums.py                          # Added AGENTBAY enumeration
├── box/
│   ├── cloud/
│   │   ├── __init__.py               # Added
│   │   └── cloud_sandbox.py         # Added CloudSandbox base class
│   └── e2b/
│       ├── __init__.py               # Added
│       └── e2b_sandbox.py           # Added E2bSandBox implementation
└── __init__.py                       # Updated exports
```


### 4. Service Layer Integration

- **Registration Mechanism**: Register using [@SandboxRegistry.register](file:///Users/zlh/PycharmProjects/1/agentscope-runtime/src/agentscope_runtime/sandbox/registry.py#L38-L89) decorator
- **Service Integration**: Special handling of E2B types in [SandboxService](file:///Users/zlh/PycharmProjects/1/agentscope-runtime/src/agentscope_runtime/engine/services/sandbox/sandbox_service.py#L10-L209)
- **Compatibility**: Full compatibility with existing sandbox interfaces
- **Lifecycle Management**: Supports creation, connection, and release of cloud resources

## How to Use

### 1. Set Environment Variables

Configure authentication information according to E2B official documentation.
##### 1.1.1 E2B Activation
Visit the E2B website to register and obtain credentials, then configure E2B_API_KEY
https://e2b.dev

Edit the .env.template file in the current directory or set environment variables

```bash
# E2B API Key
export E2B_API_KEY=
# Docker runtime environment $home replaced with user home directory, no configuration needed when using cloud sandbox directly, unix:///$home/.colima/default/docker.sock
export DOCKER_HOST=''
```


Dependency Installation

```bash
# Install core dependencies
pip install agentscope-runtime

# Install extensions
pip install "agentscope-runtime[ext]"
```


### 2. Direct Usage of E2B Desktop Sandbox

```python
import os
from agentscope_runtime.sandbox import E2bSandBox

sandbox = E2bSandBox()

# Run shell command
result = sandbox.call_tool("run_shell_command", {"command": "echo Hello World"})
print(result["output"])

# Screenshot
result_screenshot = sandbox.call_tool(
                "screenshot",
                {"file_path": f"{os.getcwd()}/screenshot.png"},
            )
print(f"screenshot result: {result_screenshot}")
```


### 3. Using via SandboxService

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


## Configuration Parameters

### E2B Desktop Sandbox Configuration

| Parameter | Type | Description |
|-----------|------|-------------|
| timeout | int | Operation timeout (seconds), default 600 |
| command_timeout | int | Command execution timeout (seconds), default 60 |

## Notes

1. Ensure E2B service is registered and configured before use
2. Need to properly configure corresponding environment variables
3. E2B service will incur corresponding resource costs

## Running Demo

```bash
# Sandbox demo
python examples/e2b_sandbox/e2b_sandbox_demo.py
```
