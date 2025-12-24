# A2A Registry - Service Registration and Discovery

## AgentApp Extension Field a2a_config

In the `AgentApp` constructor, we introduce an optional parameter `a2a_config` to extend the configuration of the agent's A2A protocol information and runtime-related fields.

Its type is `AgentCardWithRuntimeConfig`, which wraps AgentCard protocol fields and runtime fields into a single data structure for unified management.

The fields in `AgentCardWithRuntimeConfig` fall into two categories:

**1. AgentCard Protocol Fields**

The `agent_card` field can be an `AgentCard` object or dictionary, containing the following protocol fields:

- `name`: Agent name
- `description`: Agent description
- `url`: Complete URL of the agent service. By default it can be inferred automatically from `host` / `port`.
- `version`: Agent version. By default it follows the runtime code version.
- `preferred_transport`: Preferred transport protocol, such as `"JSONRPC"`.
- `additional_interfaces`: List of additional transport interfaces.
- `skills`: List of agent capabilities/skills.
- `default_input_modes`: Default supported input modes, for example `["text"]`.
- `default_output_modes`: Default supported output modes, for example `["text"]`.
- `provider`: Provider information, which can be a string, dict, or structured object.
- `documentation_url`: Documentation URL.
- `icon_url`: Icon URL.
- `security_schemes`: Security schemes definition.
- `security`: Security requirements configuration.

**2. Runtime Fields**

- `host`: Host address for the agent to register with the Registry agent registry center. If not specified, the runtime automatically obtains the first non-loopback IP address from all network interfaces of the current deployment machine.
- `port`: Port for the agent to register with the Registry agent registry center. Defaults to `8080`.
- `registry`: Registry instance or list, used to register the agent service to centralized agent registries such as Nacos.
- `task_timeout`: Timeout in seconds for a task to complete. Defaults to `60`.
- `task_event_timeout`: Timeout in seconds for task events. Defaults to `10`.
- `wellknown_path`: Public path where the AgentCard is exposed. Defaults to `"/.wellknown/agent-card.json"`.

In practice, you only need to pass an appropriate `a2a_config` when constructing `AgentApp`. Among these fields, we provide A2A Registry capability, which allows you to specify which centralized agent registries (such as Nacos) the current agent should be registered to via the `registry` field.

## Registry Architecture

A2A Registry adopts an extensible plugin-based architecture for registering agent services to different centralized agent registries (such as Nacos).

Core components:

**1. A2ARegistry Abstract Base Class**

Defines the interface that all Registry implementations must follow:

- `registry_name()`: Returns a short name identifying the Registry (e.g., `"nacos"`).
- `register(agent_card, a2a_transports_properties)`: Executes the actual registration logic.

The Runtime captures and logs exceptions during registration to ensure that Registry failures do not block agent service startup.

**2. A2ATransportsProperties**

Describes one or more A2A transport protocols:

- `host` / `port` / `path`: Transport endpoints exposed externally.
- `support_tls`: Whether TLS is supported.
- `extra`: Additional configuration for each transport channel.
- `transport_type`: Transport type (e.g., `"JSONRPC"`, `"HTTP"`).

When an agent exposes services through multiple transport protocols, multiple transport configurations can be provided and registered together.

**Registration Process**

When `AgentApp` starts, the Registry registration process is as follows:

1. **Agent Card Publication**: Publishes agent metadata (name, version, skills, etc.) to the registry, enabling other agents to discover and understand the agent's capabilities.

2. **Endpoint Registration**: Registers agent service endpoint information (host, port, path), including transport protocol configuration, enabling other agents to connect to the service.

3. **Background Asynchronous Execution**: The registration process runs asynchronously in the background and does not block application startup. If a Registry registration fails, the Runtime logs a warning but does not affect normal agent service startup.

## Registry Configuration Methods

The Runtime supports three ways to configure Registry:

### 1. Configuration via a2a_config

When constructing `AgentApp`, specify Registry instance(s) via the `registry` field in the `a2a_config` parameter:

```python
from agentscope_runtime.engine.app import AgentApp
from agentscope_runtime.engine.deployers.adapter.a2a import (
    AgentCardWithRuntimeConfig,
)
from agentscope_runtime.engine.deployers.adapter.a2a.nacos_a2a_registry import (
    NacosRegistry,
)
from a2a.types import AgentSkill
from v2.nacos import ClientConfigBuilder

# Create Nacos Registry instance
nacos_config = (
    ClientConfigBuilder()
    .server_address("localhost:8848")
    .username("nacos")
    .password("nacos")
    .build()
)
nacos_registry = NacosRegistry(nacos_client_config=nacos_config)

# Configure registry in a2a_config
a2a_config = AgentCardWithRuntimeConfig(
    agent_card={
        "name": "MyAgent",
        "description": "My agent description",
        # ...
    },
    registry=[nacos_registry],  # Can be a single instance or a list
    task_timeout=60,
    # ...
)

agent_app = AgentApp(
    app_name="MyAgent",
    app_description="My agent description",
    a2a_config=a2a_config,
)
```

### 2. Configuration via Environment Variables

If `registry` is not specified in `a2a_config`, the Runtime automatically creates Registry instances from environment variables. Currently, the system only implements `NacosRegistry`, and users can configure the Nacos registry via environment variables:

- `A2A_REGISTRY_ENABLED`: Whether to enable Registry feature (default: `True`)
- `A2A_REGISTRY_TYPE`: Registry type(s), supports comma-separated values (e.g., `"nacos"`)
- `NACOS_SERVER_ADDR`: Nacos server address (default: `"localhost:8848"`)
- `NACOS_USERNAME`: Nacos username (optional, for console login)
- `NACOS_PASSWORD`: Nacos password (optional, for console login)
- `NACOS_NAMESPACE_ID`: Nacos namespace ID (optional, defaults to public)
- `NACOS_ACCESS_KEY`: Nacos Access Key (optional, for client authentication)
- `NACOS_SECRET_KEY`: Nacos Secret Key (optional, for client authentication)

Environment variables can be set via `.env` file or system environment variables:

```bash
# .env file example
A2A_REGISTRY_ENABLED=true
A2A_REGISTRY_TYPE=nacos
NACOS_SERVER_ADDR=localhost:8848
NACOS_USERNAME=nacos
NACOS_PASSWORD=nacos
NACOS_NAMESPACE_ID=your_namespace_id
```

```python
# No need to specify registry in a2a_config, will be created from environment variables
agent_app = AgentApp(
    app_name="MyAgent",
    app_description="My agent description",
)
```

### 3. Passing adapter via deploy method

When deploying using `AgentApp.deploy()`, you can pass an A2A Protocol Adapter configured with Registry via the `protocol_adapters` parameter.

**A2AFastAPIDefaultAdapter Parameter Description:**

- `agent_name` (required): Agent name for Agent Card (used as fallback if `name` is not specified in `a2a_config.agent_card`)
- `agent_description` (required): Agent description for Agent Card (used as fallback if `description` is not specified in `a2a_config.agent_card`)
- `a2a_config` (optional): `AgentCardWithRuntimeConfig` object containing AgentCard protocol fields and runtime configuration
  - `agent_card`: AgentCard object or dictionary containing protocol fields (name, description, skills, etc.)
  - `host`: Service host address. If not provided, defaults to calling `get_first_non_loopback_ip()` to automatically obtain the public IP of the current deployment machine
  - `port`: Service port number. If not provided, defaults to 8080
  - `registry`: Registry instance or Registry list for service registration and discovery
  - `task_timeout`: Timeout in seconds for task completion (default: 60)
  - `task_event_timeout`: Timeout in seconds for task events (default: 10)
  - `wellknown_path`: Public path where AgentCard is exposed (default: `"/.wellknown/agent-card.json"`)

```python
from agentscope_runtime.engine.app import AgentApp
from agentscope_runtime.engine.deployers.adapter.a2a import (
    A2AFastAPIDefaultAdapter,
    AgentCardWithRuntimeConfig,
)
from agentscope_runtime.engine.deployers.adapter.a2a.nacos_a2a_registry import (
    NacosRegistry,
)
from agentscope_runtime.engine.deployers import LocalDeployManager
from v2.nacos import ClientConfigBuilder

# Create Nacos Registry instance
nacos_config = (
    ClientConfigBuilder()
    .server_address("localhost:8848")
    .build()
)
nacos_registry = NacosRegistry(nacos_client_config=nacos_config)

# Create A2A Protocol Adapter configured with Registry
a2a_adapter = A2AFastAPIDefaultAdapter(
    agent_name="MyAgent",
    agent_description="My agent description",
    a2a_config=AgentCardWithRuntimeConfig(
        registry=[nacos_registry],
        # ...
    ),
)

# Create AgentApp
agent_app = AgentApp(
    app_name="MyAgent",
    app_description="My agent description",
)

# Pass adapter in deploy method
deployer = LocalDeployManager(host="127.0.0.1", port=8090)
await agent_app.deploy(
    deployer,
    protocol_adapters=[a2a_adapter],
    # ... other deployment parameters
)
```

**Configuration Priority**: The `registry` explicitly specified via `a2a_config` has the highest priority. If not specified, it will be automatically created from environment variables. The `protocol_adapters` passed via the `deploy` method will override the adapter configured in `AgentApp`.

## Nacos Registry Usage Guide

Nacos is a dynamic service discovery, configuration management, and AI agent management platform that makes it easy to build AI Agent applications.
Nacos implemented Agent registry capability in version 3.1.0, supporting distributed registration, discovery, and version management for A2A agents.
> Note: The prerequisite for using NacosAgentCardResolver is that a Nacos server version 3.1.0 or higher has been deployed.

Before using Nacos Registry, you need to install and start the Nacos server. Here are the quick start steps:

### 1. Download Installation Package

Go to [Nacos Github latest stable release](https://github.com/alibaba/nacos/releases), select the Nacos version you want to download, and click to download the `nacos-server-$version.zip` package in `Assets`.

### 2. Extract Nacos Distribution Package

```bash
unzip nacos-server-$version.zip
# or tar -xvf nacos-server-$version.tar.gz
cd nacos/bin
```

### 3. Start Server

**Linux/Unix/Mac:**
```bash
sh startup.sh -m standalone
```

**Windows:**
```bash
startup.cmd -m standalone
```

> Note: `standalone` represents standalone mode, not cluster mode.

For more detailed installation, configuration, and verification steps, please refer to the [Nacos official quick start documentation](https://nacos.io/docs/v3.0/quickstart/quick-start/).

## Custom Registry Implementation

If you need to integrate other types of centralized agent registries, you can implement a custom Registry. Custom Registry needs to inherit from the `A2ARegistry` abstract base class and implement the following methods:

### Implementation Steps

1. **Inherit from `A2ARegistry` abstract base class**
2. **Implement `registry_name()` method**: Returns a short name for the Registry, used for logging and diagnostics
3. **Implement `register()` method**: Executes the actual registration logic

### Example Code

Here is a simple custom Registry implementation example:

```python
from agentscope_runtime.engine.deployers.adapter.a2a.a2a_registry import (
    A2ARegistry,
    A2ATransportsProperties,
)
from a2a.types import AgentCard
from typing import Optional, List
import logging

logger = logging.getLogger(__name__)


class MyCustomRegistry(A2ARegistry):
    """Custom Registry implementation example."""

    def registry_name(self) -> str:
        return "my-custom-registry"

    def register(
        self,
        agent_card: AgentCard,
        a2a_transports_properties: Optional[
            List[A2ATransportsProperties]
        ] = None,
    ) -> None:

        try:
            # Build registration information
            if a2a_transports_properties and len(a2a_transports_properties) > 0:
                transport = a2a_transports_properties[0]
                service_info = {
                    "agent_name": agent_card.name,
                    "agent_version": agent_card.version,
                    "host": transport.host,
                    "port": transport.port,
                }
            else:
                service_info = {
                    "agent_name": agent_card.name,
                    "agent_version": agent_card.version,
                }

            # Execute registration logic
            logger.info(f"[MyCustomRegistry] Registering: {service_info}")
            # ...

        except Exception as e:
            logger.warning(f"[MyCustomRegistry] Registration failed: {e}", exc_info=True)
```

### Using Custom Registry

After implementing a custom Registry, you can use it in the following way:

```python
from agentscope_runtime.engine.app import AgentApp
from agentscope_runtime.engine.deployers.adapter.a2a import (
    AgentCardWithRuntimeConfig,
)

# Create custom Registry instance
custom_registry = MyCustomRegistry()

# Use in a2a_config
a2a_config = AgentCardWithRuntimeConfig(
    registry=[custom_registry],
    # ...
)

agent_app = AgentApp(
    app_name="MyAgent",
    app_description="My agent description",
    a2a_config=a2a_config,
)
```
