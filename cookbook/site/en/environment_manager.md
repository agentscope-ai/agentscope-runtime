---
jupytext:
  formats: md:myst
  text_representation:
    extension: .md
    format_name: myst
    format_version: 0.13
    jupytext_version: 1.11.5
kernelspec:
  display_name: Python 3
  language: python
  name: python3
---

# Environment Manager

## Overview

`EnvironmentManager` provides lifecycle and access to sandboxed environments and tools through `SandboxService`.

Default behavior wires a `SandboxService` instance which manages environment creation, connection, and release.

## Basic Usage

```{code-cell}
from agentscope_runtime.engine.services.environment_manager import (
    create_environment_manager,
)
from agentscope_runtime.engine.services.sandbox_service import SandboxService
async def quickstart():
    async with create_environment_manager(
      sandbox_service = SandboxService()
    ) as manager:
        boxes = manager.connect_sandbox(
            session_id="s1",
            user_id="u1",
            env_types=[],
            tools=[],
        )
        # use boxes
        manager.release_sandbox(session_id="s1", user_id="u1")
```

In the future, `EnvironmentManager` will support not only `sandbox_service` but also other services for interacting with environments.

## Sandbox Service

The **Sandbox Service** is designed to manage and provide access to sandboxed tool execution (see {doc}`sandbox` for details) sandboxes for different users and sessions. Sandboxes are organized by a composite key of session ID and user ID, allowing isolated execution contexts for each user session. The service supports multiple sandbox types and can automatically provision the required sandboxes based on the tools being used.

### Service Overview

The Sandbox Service provides a unified interface for sandbox management with support for different sandbox types like code execution, file operations, and other specialized sandboxes. The following is an example to initialize a sandbox service:

```{code-cell}
from agentscope_runtime.engine.services.sandbox_service import SandboxService

# Create and start the sandbox service
sandbox_service = SandboxService()

# Or with remote sandbox service
# sandbox_service = SandboxService(
#     base_url="http://sandbox-server:8000",
#     bearer_token="your-auth-token"
# )
```

### Core Functionality

#### Connecting to Sandboxes

The `connect` method allows you to connect to sandbox sandboxes for a specific user session:

```{code-cell}
# Connect with specific sandbox types
session_id = "session1"
user_id = "user1"
sandbox_types = ["browser", "filesystem"]

sandboxes = sandbox_service.connect(
    session_id=session_id,
    user_id=user_id,
    env_types=sandbox_types
)
```

#### Auto-provisioning with Tools

The service can automatically determine required sandbox types based on the tools being used:

```{code-cell}
# Connect with tools (sandbox types auto-detected)
from agentscope_runtime.sandbox.tools.filesystem import read_file
from agentscope_runtime.sandbox.tools.browser import browser_navigate

tools = [read_file, browser_navigate]
sandboxes = sandbox_service.connect(session_id=session_id,
    user_id=user_id,
    tools=tools
)

# The service will automatically create filesystem and browser sandboxes
print(f"Provisioned {len(sandboxes)} sandboxes")
```

#### Sandbox Reuse

The service efficiently reuses existing sandboxes for the same user session:

```{code-cell}
# First connection creates new sandboxes
sandboxes1 = sandbox_service.connect(session_id, user_id, env_types=["base"])

# Second connection reuses existing sandboxes
sandboxes2 = sandbox_service.connect(session_id, user_id, env_types=["base"])

# sandboxes1 and sandboxes2 reference the same sandbox instances
assert len(sandboxes1) == len(sandboxes2)
```

#### Releasing Sandboxes

Release sandboxes when no longer needed to free up resources:

```{code-cell}
# Release sandboxes for a specific user session
success = sandbox_service.release(session_id, user_id)
print(f"Release successful: {success}")

# Sandboxes are automatically cleaned up
```

### Service Lifecycle

The Sandbox Service follows a standard lifecycle pattern:

```{code-cell}
# Start the service
await sandbox_service.start()

# Check service health
is_healthy = await sandbox_service.health()

# Stop the service (releases all sandboxes)
await sandbox_service.stop()
```
