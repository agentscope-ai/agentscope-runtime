# A2A Registry - Service Registration and Discovery

## Overview

A2A Registry is a service registration and discovery mechanism provided by AgentScope Runtime for the A2A (Agent-to-Agent) protocol. Through Registry, you can register your agent services to service discovery systems (such as Nacos, Consul, etc.), enabling other agents or clients to dynamically discover and invoke your services.

## Core Concepts

### Registry Architecture

A2A Registry adopts an extensible plugin-based architecture:

- **A2ARegistry**: Abstract base class defining the core Registry interface
- **Concrete Implementations**: Such as `NacosRegistry`, implementing registration logic for specific service discovery systems
- **Registration Flow**:
  1. **Agent Card Publication**: Publish agent metadata (name, version, skills, etc.) to the registry center
  2. **Endpoint Registration**: Register agent service endpoints (host, port, path) information
  3. **Background Async Execution**: Registration process runs asynchronously in the background without blocking application startup

## Configuration Methods

### Method 1: Via a2a_config (Recommended)

Use `AgentCardWithRuntimeConfig` or dictionary to configure the `a2a_config` parameter.

**Using AgentCardWithRuntimeConfig:**

```python
from agentscope_runtime.engine.app import AgentApp
from agentscope_runtime.engine.deployers.adapter.a2a import (
    AgentCardWithRuntimeConfig,
    NacosRegistry,
)
from v2.nacos import ClientConfigBuilder

# Create Nacos Registry
builder = ClientConfigBuilder().server_address("localhost:8848")
nacos_registry = NacosRegistry(nacos_client_config=builder.build())

# Configure A2A (only specify key fields)
a2a_config = AgentCardWithRuntimeConfig(
    name="MyAgent",
    description="My agent",
    registry=[nacos_registry],  # Runtime field
)

# Create AgentApp
app = AgentApp(
    app_name="MyAgent",
    app_description="My agent",
    a2a_config=a2a_config,
)
```

**Using Dictionary Configuration:**

```python
a2a_config = {
    # AgentCard fields
    "name": "MyAgent",
    "version": "1.0.0",
    "description": "My agent",
    "url": "http://localhost:8099/a2a",
    "preferredTransport": "JSONRPC",
    "skills": [...],
    
    # Runtime fields
    "registry": [nacos_registry],
    "transports": [...],
    "task_timeout": 60,
}

app = AgentApp(
    app_name="MyAgent",
    app_description="My agent",
    a2a_config=a2a_config,
)
```

### Method 2: Via Environment Variables

Runtime supports automatic Registry creation from environment variables or `.env` files:

```bash
# .env file
A2A_REGISTRY_ENABLED=true          # Enable Registry (default: true)
A2A_REGISTRY_TYPE=nacos            # Registry type (e.g.: nacos)
NACOS_SERVER_ADDR=localhost:8848   # Nacos server address
NACOS_USERNAME=your_username       # Nacos username (optional)
NACOS_PASSWORD=your_password       # Nacos password (optional)
NACOS_NAMESPACE_ID=public          # Nacos namespace ID (optional, default: public)
```

When `a2a_config` is not explicitly configured, AgentApp automatically reads environment variables to create Registry

## Nacos Registry Usage Guide

### Start Nacos Service

```bash
# Quick start Nacos (standalone mode)
cd nacos/bin
sh startup.sh -m standalone
```

Access console: http://localhost:8848/nacos (default username/password: nacos/nacos)

> For more deployment options, see: https://nacos.io/docs/v3.0/quickstart/quick-start/

### Basic Configuration

```python
from v2.nacos import ClientConfigBuilder
from agentscope_runtime.engine.deployers.adapter.a2a import NacosRegistry

# Create Nacos Registry
builder = ClientConfigBuilder().server_address("localhost:8848")
nacos_registry = NacosRegistry(nacos_client_config=builder.build())

# Optional: Add authentication
builder.username("nacos").password("nacos")

# Optional: Set namespace
builder.namespace_id("your-namespace-id")
```

## Multiple Registry Support

Runtime supports registering to multiple service discovery systems simultaneously:

```python
from agentscope_runtime.engine.deployers.adapter.a2a import (
    AgentCardWithRuntimeConfig,
)

# Create multiple Registry instances
nacos_registry_1 = NacosRegistry(config_1)
nacos_registry_2 = NacosRegistry(config_2)
# consul_registry = ConsulRegistry(...)  # Future support

a2a_config = AgentCardWithRuntimeConfig(
    name="MyAgent",
    # ... other fields ...
    registry=[nacos_registry_1, nacos_registry_2],  # Multiple Registries
)
```

## Extending Custom Registry

You can implement a custom Registry to support other service discovery systems:

```python
from agentscope_runtime.engine.deployers.adapter.a2a.a2a_registry import (
    A2ARegistry,
    DeployProperties,
    A2ATransportsProperties,
)
from a2a.types import AgentCard
from typing import List

class MyCustomRegistry(A2ARegistry):
    """Custom Registry implementation"""
    
    def registry_name(self) -> str:
        """Return Registry name"""
        return "my-custom-registry"
    
    def register(
        self,
        agent_card: AgentCard,
        deploy_properties: DeployProperties,
        a2a_transports_properties: List[A2ATransportsProperties],
    ) -> None:
        """Register agent service"""
        # Implement your registration logic
        pass

# Use custom Registry
custom_registry = MyCustomRegistry()
a2a_config = AgentCardWithRuntimeConfig(
    name="MyAgent",
    # ... other fields ...
    registry=[custom_registry],
)
```

## Best Practices

1. **Use Environment Variables**: Keep sensitive information (like passwords) in `.env` files, avoid hardcoding
2. **Graceful Shutdown**: Call `cleanup()` method during application shutdown to clean up resources
3. **Monitor Registration Status**: Monitor registration status in production environments to detect and handle failures promptly
4. **Set Reasonable Timeouts**: Configure appropriate `task_timeout` and `task_event_timeout` based on network conditions
5. **Use Namespaces**: Use different namespaces to isolate services in multi-environment deployments
