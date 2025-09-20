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

# Advanced Deployment Guide

This guide demonstrates the three advanced deployment methods available in AgentScope Runtime, providing production-ready solutions for different scenarios: **Local Daemon**, **Detached Process**, and **Kubernetes Deployment**.

## Overview of Deployment Methods

AgentScope Runtime offers three distinct deployment approaches, each tailored for specific use cases:

| Deployment Type | Use Case | Scalability | Management | Resource Isolation |
|----------------|----------|-------------|------------|-------------------|
| **Local Daemon** | Development & Testing | Single Process | Manual | Process-level |
| **Detached Process** | Production Services | Single Node | Automated | Process-level |
| **Kubernetes** | Enterprise & Cloud | Single-node(Will support Multi-node) | Orchestrated | Container-level |

## Prerequisites

### 🔧 Installation Requirements

Install AgentScope Runtime with all deployment dependencies:

```bash
# Basic installation
pip install agentscope-runtime

# For Kubernetes deployment
pip install "agentscope-runtime[deployment]"

# For sandbox tools (optional)
pip install "agentscope-runtime[sandbox]"
```

### 🔑 Environment Setup

Configure your API keys and environment variables:

```bash
# Required for LLM functionality
export DASHSCOPE_API_KEY="your_qwen_api_key"

# Optional for cloud deployments
export DOCKER_REGISTRY="your_registry_url"
export KUBECONFIG="/path/to/your/kubeconfig"
```

### 📦 Prerequisites by Deployment Type

#### For All Deployments
- Python 3.10+
- AgentScope Runtime installed

#### For Kubernetes Deployment
- Docker installed and configured
- Kubernetes cluster access
- kubectl configured
- Container registry access (for image pushing)

## Common Agent Setup

All deployment methods share the same agent configuration. Let's first create our base agent:

```{code-cell}
# agent.py
import os
from agentscope_runtime.engine.agents.llm_agent import LLMAgent
from agentscope_runtime.engine.llms import QwenLLM

# Create the LLM model
model = QwenLLM(
    model_name="qwen-turbo",
    api_key=os.getenv("DASHSCOPE_API_KEY"),
)

# Create the agent
llm_agent = LLMAgent(
    model=model,
    name="ProductionAgent",
    agent_config={
        "sys_prompt": (
            "You are a helpful assistant deployed in production. "
            "You can help users with various tasks and provide reliable responses."
        ),
    },
)

print("✅ Agent definition ready for deployment")
```

## Method 1: Local Daemon Deployment

**Best for**: Development, testing, and single-user scenarios where you need persistent service with manual control.

### Features
- Persistent service in main process
- Manual lifecycle management
- Interactive control and monitoring
- Direct resource sharing

### Implementation

```{code-cell}
import asyncio
from contextlib import asynccontextmanager
from agentscope_runtime.engine.deployers.local_deployer import LocalDeployManager
from agentscope_runtime.engine.runner import Runner
from agentscope_runtime.engine.services.context_manager import ContextManager
from agentscope_runtime.engine.services.session_history_service import InMemorySessionHistoryService
from agentscope_runtime.engine.services.environment_manager import create_environment_manager
from agentscope_runtime.sandbox.tools.filesystem import run_ipython_cell, edit_file

# Import our agent definition
from agent_definition import llm_agent

async def prepare_services():
    """Prepare context and environment services"""
    # Session management
    session_history_service = InMemorySessionHistoryService()
    await session_history_service.create_session(
        user_id="production_user",
        session_id="prod_session_001",
    )

    # Context manager
    context_manager = ContextManager(
        session_history_service=session_history_service,
    )

    return context_manager

@asynccontextmanager
async def create_production_runner():
    """Create runner with full production services"""
    context_manager = await prepare_services()

    async with context_manager:
        # Add sandbox tools for enhanced functionality
        enhanced_agent = LLMAgent(
            model=llm_agent.model,
            name=llm_agent.name,
            agent_config=llm_agent.agent_config,
            tools=[run_ipython_cell, edit_file],  # Add tools if needed
        )

        async with create_environment_manager() as env_manager:
            runner = Runner(
                agent=enhanced_agent,
                context_manager=context_manager,
                environment_manager=env_manager,
            )
            print("✅ Production runner created successfully")
            yield runner

async def deploy_daemon():
    """Deploy agent as a local daemon service"""
    async with create_production_runner() as runner:
        # Create deployment manager
        deploy_manager = LocalDeployManager(
            host="0.0.0.0",  # Allow external connections
            port=8090,
        )

        # Deploy with full configuration
        deploy_result = await runner.deploy(
            deploy_manager=deploy_manager,
            endpoint_path="/process",
            stream=True,
        )

        print(f"🚀 Daemon service deployed successfully!")
        print(f"🌐 Service URL: {deploy_result['url']}")
        print(f"💚 Health check: {deploy_result['url']}/health")
        print(f"""
🎯 Service Management Commands:

# Health check
curl {deploy_result['url']}/health

# Process request
curl -X POST {deploy_result['url']}/process \\
  -H "Content-Type: application/json" \\
  -H "Accept: text/event-stream" \\
  --no-buffer \\
  -d '{{
    "input": [{{
      "role": "user",
      "content": [{{
        "type": "text",
        "text": "Hello, how can you help me today?"
      }}]
    }}],
    "session_id": "prod_session_001"
  }}'
        """)

        return deploy_manager

async def run_daemon_deployment():
    """Main function for daemon deployment"""
    try:
        deploy_manager = await deploy_daemon()

        print("🏃 Daemon service is running...")
        print("Press Ctrl+C to stop the service")

        # Keep service running
        while True:
            await asyncio.sleep(1)

    except (KeyboardInterrupt, asyncio.CancelledError):
        print("\n🛑 Shutdown signal received. Stopping service...")
        if deploy_manager and deploy_manager.is_running:
            await deploy_manager.stop()
        print("✅ Daemon service stopped.")
    except Exception as e:
        print(f"❌ Error in daemon deployment: {e}")
        if deploy_manager and deploy_manager.is_running:
            await deploy_manager.stop()

# Run daemon deployment
# asyncio.run(run_daemon_deployment())
```

### Daemon Deployment Advantages
- ✅ **Simple Setup**: Easy to configure and start
- ✅ **Interactive Control**: Direct process management
- ✅ **Resource Efficiency**: No process overhead
- ✅ **Development Friendly**: Easy debugging and monitoring

### Daemon Deployment Considerations
- ⚠️ **Single Point of Failure**: Service stops if main process exits
- ⚠️ **Manual Management**: Requires manual start/stop
- ⚠️ **Limited Scalability**: Single process limitation

## Method 2: Detached Process Deployment

**Best for**: Production services requiring process isolation, automated management, and independent lifecycle.

### Features
- Independent process execution
- Automated lifecycle management
- Remote shutdown capabilities
- Service persistence after main script exit

### Implementation

```{code-cell}
import asyncio
from agentscope_runtime.engine.deployers.adapter.a2a import A2AFastAPIDefaultAdapter
from agentscope_runtime.engine.deployers.local_deployer import LocalDeployManager
from agentscope_runtime.engine.deployers.utils.deployment_modes import DeploymentMode
from agentscope_runtime.engine.deployers.utils.service_utils import ServicesConfig
from agentscope_runtime.engine.runner import Runner

# Import our agent definition
from agent_definition import llm_agent

async def deploy_detached():
    """Deploy agent as detached process"""

    print("🚀 Starting detached deployment...")

    # Create A2A protocol adapter
    a2a_protocol = A2AFastAPIDefaultAdapter(agent=llm_agent)

    # Create deployment manager
    deploy_manager = LocalDeployManager(
        host="0.0.0.0",
        port=8080,
    )

    # Create runner
    runner = Runner(agent=llm_agent)

    # Deploy in detached mode with full configuration
    deployment_info = await runner.deploy(
        deploy_manager=deploy_manager,
        endpoint_path="/process",
        stream=True,
        mode=DeploymentMode.DETACHED_PROCESS,  # Key: detached mode
        services_config=ServicesConfig(),  # Use default in-memory services
        protocol_adapters=[a2a_protocol],  # Add A2A support
    )

    print(f"✅ Detached deployment successful!")
    print(f"📍 Deploy ID: {deployment_info['deploy_id']}")
    print(f"🌐 Service URL: {deployment_info['url']}")

    return deployment_info

async def manage_detached_service():
    """Deploy and manage detached service"""
    # Deploy the service
    deployment_info = await deploy_detached()
    service_url = deployment_info['url']

    print(f"""
🎯 Detached Service Management:

# Health check
curl {service_url}/health

# Process request
curl -X POST {service_url}/process \\
  -H "Content-Type: application/json" \\
  -H "Accept: text/event-stream" \\
  --no-buffer \\
  -d '{{
    "input": [{{
      "role": "user",
      "content": [{{
        "type": "text",
        "text": "What are the benefits of detached deployment?"
      }}]
    }}],
    "session_id": "detached_session"
  }}'

# Check process status
curl {service_url}/admin/status

# Remote shutdown
curl -X POST {service_url}/admin/shutdown

⚠️ Note: The service runs independently after this script exits.
    """)

    return deployment_info

# Deploy detached service
# deployment_info = await manage_detached_service()
```

### Advanced Detached Configuration

For production environments, you can configure external services:

```{code-cell}
from agentscope_runtime.engine.deployers.utils.service_utils import ServicesConfig

# Production services configuration
production_services = ServicesConfig(
    # Use Redis for persistence
    memory_provider="redis",
    session_history_provider="redis",
    redis_config={
        "host": "redis.production.local",
        "port": 6379,
        "db": 0,
    }
)

# Deploy with production services
deployment_info = await runner.deploy(
    deploy_manager=deploy_manager,
    endpoint_path="/process",
    stream=True,
    mode=DeploymentMode.DETACHED_PROCESS,
    services_config=production_services,  # Use production config
    protocol_adapters=[a2a_protocol],
)
```

### Detached Deployment Advantages
- ✅ **Process Isolation**: Independent process execution
- ✅ **Automated Management**: Built-in lifecycle management
- ✅ **Remote Control**: API-based process management
- ✅ **Production Ready**: Suitable for production environments

### Detached Deployment Considerations
- ⚠️ **Resource Overhead**: Additional process overhead
- ⚠️ **Monitoring Required**: Need external process monitoring
- ⚠️ **Single Node**: Limited to single machine deployment

## Method 3: Kubernetes Deployment

**Best for**: Enterprise production environments requiring scalability, high availability, and cloud-native orchestration.

### Features
- Container-based deployment
- Horizontal scaling support
- Cloud-native orchestration
- Resource management and limits
- Health checks and auto-recovery

### Prerequisites for Kubernetes Deployment

```bash
# Ensure Docker is running
docker --version

# Verify Kubernetes access
kubectl cluster-info

# Check registry access (example with Aliyun)
docker login  your-registry
```

### Implementation

```{code-cell}
import asyncio
import os
from agentscope_runtime.engine.deployers.kubernetes_deployer import (
    KubernetesDeployManager,
    RegistryConfig,
    K8sConfig,
)
from agentscope_runtime.engine.runner import Runner

# Import our agent definition
from agent_definition import llm_agent

async def deploy_to_kubernetes():
    """Deploy agent to Kubernetes cluster"""

    print("🚀 Starting Kubernetes deployment...")

    # 1. Configure Container Registry
    registry_config = RegistryConfig(
        registry_url="your register",
        namespace="your-acr-namesapce",
    )

    # 2. Configure Kubernetes Connection
    k8s_config = K8sConfig(
        k8s_namespace="your-ack-namespace",
        kubeconfig_path="your-kubeconfig-path"
    )

    # 3. Create Kubernetes Deploy Manager
    deployer = KubernetesDeployManager(
        kube_config=k8s_config,
        registry_config=registry_config,
        use_deployment=True,  # Use Deployment for scaling support
    )

    # 4. Create Runner
    runner = Runner(agent=llm_agent)

    # 5. Configure Runtime Resources
    runtime_config = {
        "resources": {
            "requests": {"cpu": "200m", "memory": "512Mi"},
            "limits": {"cpu": "1000m", "memory": "2Gi"},
        },
        "image_pull_policy": "IfNotPresent",
    }
    # 6. Deployment Configuration
    deployment_config = {
        # Service Configuration
        "api_endpoint": "/process",
        "stream": True,
        "port": "8080",
        "replicas": 1,  # Deploy 2 replicas for HA

        # Container Configuration
        "image_tag": "production-v1.0",
        "image_name": "agent-llm-production",
        "base_image": "python:3.10-slim-bookworm",
        "platform": "linux/amd64",

        # Dependencies
        "requirements": [
            "agentscope",
            "fastapi",
            "uvicorn",
            "redis",  # For persistence
        ],

        # Environment Variables
        "environment": {
            "PYTHONPATH": "/app",
            "LOG_LEVEL": "INFO",
            "DASHSCOPE_API_KEY": os.environ.get("DASHSCOPE_API_KEY"),
            "REDIS_HOST": "redis-service.agentscope-runtime.svc.cluster.local",
            "REDIS_PORT": "6379",
        },

        # Kubernetes Runtime Configuration
        "runtime_config": runtime_config,

        # Deployment Options
        "deploy_timeout": 300,
        "health_check": True,
        "push_to_registry": True,
    }

    # 7. define the production services
    production_services = ServicesConfig(
        # Use Redis for persistence
        memory=ServiceConfig(
            provider=ServiceProvider.REDIS,
            config={
                "host": "redis-endpoiont",
                "port": 6379,
                "db": 0,
            }
        ),
        session_history=ServiceConfig(
            provider=ServiceProvider.REDIS,
            config={
                "host": "redis-endpoiont",
                "port": 6379,
                "db": 0,
            }
        ),
    )

    try:
        # 8. Execute Deployment
        result = await runner.deploy(
            deploy_manager=deployer,
            services_config=production_services,
            **deployment_config,
        )

        print("✅ Kubernetes deployment successful!")
        print(f"📍 Deploy ID: {result['deploy_id']}")
        print(f"🌐 Service URL: {result['url']}")
        print(f"📦 Resource Name: {result['resource_name']}")
        print(f"🔢 Replicas: {result['replicas']}")

        return result, deployer

    except Exception as e:
        print(f"❌ Kubernetes deployment failed: {e}")
        raise

async def manage_kubernetes_deployment():
    """Deploy and manage Kubernetes service"""
    try:
        # Deploy to Kubernetes
        result, deployer = await deploy_to_kubernetes()
        service_url = result["url"]

        # Check deployment status
        print("\n📊 Checking deployment status...")
        status = deployer.get_status()
        print(f"Status: {status}")

        print(f"""
🎯 Kubernetes Service Management:

# Health check
curl {service_url}/health

# Process request
curl -X POST {service_url}/process \\
  -H "Content-Type: application/json" \\
  -H "Accept: text/event-stream" \\
  --no-buffer \\
  -d '{{
    "input": [{{
      "role": "user",
      "content": [{{
        "type": "text",
        "text": "How does Kubernetes deployment scale?"
      }}]
    }}],
    "session_id": "k8s_session"
  }}'

# Kubernetes management commands
kubectl get pods -n agentscope-runtime
kubectl get svc -n agentscope-runtime
kubectl logs -l app={result['resource_name']} -n agentscope-runtime

# Scale deployment
kubectl scale deployment {result['resource_name']} --replicas=3 -n agentscope-runtime
        """)

        # Interactive management
        input("\nPress Enter to cleanup deployment...")

        # Cleanup
        print("🧹 Cleaning up Kubernetes deployment...")
        cleanup_result = await deployer.stop()
        if cleanup_result:
            print("✅ Cleanup completed successfully")
        else:
            print("❌ Cleanup failed, please check manually")

        return result

    except Exception as e:
        print(f"❌ Error in Kubernetes deployment management: {e}")
        import traceback
        traceback.print_exc()

# Deploy to Kubernetes
# k8s_result = await manage_kubernetes_deployment()
```



### Kubernetes Deployment Advantages
- ✅ **Horizontal Scaling**: Easy replica scaling
- ✅ **High Availability**: Built-in fault tolerance
- ✅ **Resource Management**: CPU/memory limits and requests
- ✅ **Cloud Native**: Full Kubernetes ecosystem integration
- ✅ **Auto Recovery**: Automatic pod restart on failure

### Kubernetes Deployment Considerations
- ⚠️ **Complexity**: More complex setup and management
- ⚠️ **Resource Requirements**: Higher resource overhead
- ⚠️ **Cluster Dependency**: Requires Kubernetes cluster
- ⚠️ **Container Registry**: Needs accessible registry

## Deployment Comparison and Best Practices

### When to Use Each Method

#### Local Daemon
- ✅ **Development and Testing**: Quick setup for development
- ✅ **Single User Applications**: Personal or small team usage
- ✅ **Resource Constrained**: Limited computational resources
- ✅ **Simple Requirements**: Basic deployment needs

#### Detached Process
- ✅ **Production Services**: Single-node production deployments
- ✅ **Service Independence**: Need process isolation
- ✅ **Automated Management**: Require remote management
- ✅ **Medium Scale**: Moderate traffic applications

#### Kubernetes
- ✅ **Enterprise Production**: Large-scale production environments
- ✅ **High Availability**: Mission-critical applications
- ✅ **Cloud Deployment**: Cloud-native architectures
- ✅ **Microservices**: Part of larger microservice ecosystem

## Summary

This guide covered three deployment methods for AgentScope Runtime:

### 🏃 **Local Daemon**: Development & Testing
- Quick setup and direct control
- Best for development and small-scale usage
- Manual lifecycle management

### 🔧 **Detached Process**: Production Services
- Process isolation and automated management
- Suitable for production single-node deployments
- Remote control capabilities

### ☸️ **Kubernetes**: Enterprise & Cloud
- Full container orchestration and scaling
- High availability and cloud-native features
- Enterprise-grade production deployments

Choose the deployment method that best fits your use case, infrastructure, and scaling requirements. All methods use the same agent code, making migration between deployment types straightforward as your needs evolve.

For more detailed information on specific components, refer to the [Manager Module](manager.md), [Sandbox](sandbox.md), and [Quick Start](quickstart.md) guides.
