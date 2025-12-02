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

# Sandbox Service

## Overview

The **Sandbox Service** provides isolated **tool execution environments** (sandboxes) for different users and sessions, allowing agents to use tools (such as browsers, code executors, etc.) in a controlled and secure environment.
For more on sandboxes, see {doc}`../sandbox/sandbox`.

In the course of agent execution, typical roles of the sandbox service include:

- **Creating execution environments**: Generate a sandbox instance (e.g., a browser sandbox) for a new user/session.
- **Connecting to existing environments**: In multi-turn conversations, connect the agent to a previously created sandbox to continue operations.
- **Tool invocation**: Provide callable methods (such as `browser_navigate`, `browser_take_screenshot`, etc.) that can be registered as tools in an agent.
- **Releasing environments**: Release the corresponding environment resources when the session ends or requirements change.
- **Multi-type support**: Supports different types of sandboxes (`BASE`, `BROWSER`, `CODE`, `AGENTBAY`, etc.).

In different implementations, sandbox services mainly differ in:
**running modes** (embedded/remote), **supported types**, **management methods**, and **extensibility**.

```{note}
In business code, it is not recommended to directly implement the sandbox service and `SandboxManager`'s low-level management logic.

Instead, it is better to **use an adapter to bind sandbox methods to the agent framework’s tool module**:
- Hide low-level sandbox API details
- Let Runner/Engine manage the lifecycle uniformly
- Ensure that switching running modes or sandbox types does not affect business logic
```

## Using Adapters in AgentScope

In the **AgentScope** framework, we can use `sandbox_tool_adapter` to wrap sandbox methods into **tool functions** and register them into the Agent's `Toolkit`:

```{code-cell}
from agentscope_runtime.engine.services.sandbox import SandboxService
from agentscope_runtime.adapters.agentscope.tools import sandbox_tool_adapter
from agentscope import Toolkit

# 1. Start the service (usually managed by Runner/Engine)
sandbox_service = SandboxService()
await sandbox_service.start()

# 2. Connect to or create a sandbox (creating a browser type here)
sandboxes = sandbox_service.connect(
    session_id="TestSession",
    user_id="User1",
    sandbox_types=["browser"],
)

# 3. Get tool methods and register into the Agent's Toolkit
toolkit = Toolkit()
for tool in [
    sandboxes[0].browser_navigate,
    sandboxes[0].browser_take_screenshot,
]:
    toolkit.register_tool_function(sandbox_tool_adapter(tool))

# After this, the Agent can call these tools to perform safe operations in the sandbox
```

## Optional Running Modes and Types

### 1. **Embedded Mode**

- **Characteristics**: The sandbox manager and AgentScope Runtime run in the same process.
- **Config**: `base_url=None`
- **Advantages**: Simple deployment, no external API needed; suitable for local development and single-machine testing.
- **Disadvantages**: The environment is released when the process exits; not suitable for distributed deployment.

### 2. **Remote API Mode**

- **Characteristics**: Connect to remote sandbox instances via the sandbox management API (`SandboxManager`).
- **Config**: `base_url="http://host:port"`, `bearer_token="..."`
- **Advantages**: Can share environments across processes/machines, supporting distributed scalability.
- **Disadvantages**: Requires deployment and maintenance of a remote sandbox management service.

### Supported Sandbox Types

| Type Value   | Description                                  | Common Usage Examples                                        |
| ------------ | -------------------------------------------- | ------------------------------------------------------------ |
| `DUMMY`      | Null implementation / placeholder sandbox    | Test workflows, simulate sandbox APIs without actual execution |
| `BASE`       | Basic sandbox environment                    | General tool execution environment                           |
| `BROWSER`    | Browser sandbox                              | Web navigation, screenshots, data crawling                   |
| `FILESYSTEM` | File system sandbox                          | Reading/writing files in a secure isolated file system       |
| `GUI`        | Graphical interface sandbox                  | Interacting with GUI apps (clicking, typing, screenshots)    |
| `MOBILE`     | Mobile device emulation sandbox              | Simulating mobile app operations and touch interactions      |
| `APPWORLD`   | App world emulation sandbox                  | Simulating cross-app interactions in a virtual environment   |
| `BFCL`       | BFCL (domain-specific execution environment) | Running business process scripts (depends on implementation) |
| `AGENTBAY`   | Session-based AgentBay sandbox               | Dedicated for multi-agent collaboration or complex task orchestration |

## Example: Switching Running Modes

### **Embedded Mode (good for dev/testing)**

```{code-cell}
sandbox_service = SandboxService(base_url=None)  # local mode
await sandbox_service.start()

sandboxes = sandbox_service.connect(
    session_id="DevSession",
    sandbox_types=["browser"]
)
```

### **Remote Mode (good for production)**

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

### Releasing environments

Explicitly release resources when the session ends:

```{code-cell}
sandbox_service.release(session_id="ProdSession", user_id="UserABC")
```

```{note}
Sandboxes of type AGENTBAY will be automatically cleaned up when the object is destroyed.
```

## Recommendations

- Rapid prototyping / single-machine development & debugging:
  - Embedded mode (`base_url=None`)
  - Use `BROWSER`/`CODE` type as needed
- Production / multi-user distributed:
  - Remote API mode (requires deploying a `SandboxManager` service)
  - Consider clustering and authentication (`bearer_token`)
- High security/isolation requirements:
  - Create independent sandboxes for different user sessions
  - Use `release()` to free resources in time

## Summary

- **SandboxService** is the core component for managing sandbox execution environments, supporting multiple types.
- It is recommended to use **adapters** (`sandbox_tool_adapter`) to register sandbox methods as tools, avoiding direct manipulation of low-level APIs.
- You can choose **embedded mode** (simple, single-machine) or **remote mode** (scalable, production-ready).
- Lifecycle is managed by Runner/Engine, ensuring consistent startup, health checks, and cleanup.
- Switching modes or types only requires changing service initialization parameters, without affecting agent business logic.
