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

This guide demonstrates the four advanced deployment methods available in AgentScope Runtime, providing production-ready solutions for different scenarios: **Local Daemon**, **Detached Process**, **Kubernetes Deployment**, and **ModelStudio Deployment**.

## Overview of Deployment Methods

AgentScope Runtime offers four distinct deployment approaches, each tailored for specific use cases:

| Deployment Type | Use Case | Scalability | Management | Resource Isolation |
|----------------|----------|-------------|------------|-------------------|
| **Local Daemon** | Development & Testing | Single Process | Manual | Process-level |
| **Detached Process** | Production Services | Single Node | Automated | Process-level |
| **Kubernetes** | Enterprise & Cloud | Single-node(Will support Multi-node) | Orchestrated | Container-level |
| **ModelStudio** | Alibaba Cloud Platform | Cloud-managed | Platform-managed | Container-level |

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

#### For ModelStudio Deployment
- Alibaba Cloud account with ModelStudio access
- DashScope API key for LLM services
- OSS (Object Storage Service) access
- ModelStudio workspace configured

## Common Agent Setup

All deployment methods share the same agent and endpoint configuration. Let's first create our base agent and define the endpoints:

```{code-cell}
# agent_app.py - Shared configuration for all deployment methods
import os
import time

from agentscope.agent import ReActAgent
from agentscope.model import DashScopeChatModel
from agentscope.tool import Toolkit, view_text_file

from agentscope_runtime.engine.agents.agentscope_agent import AgentScopeAgent
from agentscope_runtime.engine.app import AgentApp
from agentscope_runtime.engine.schemas.agent_schemas import AgentRequest

# 1. Create agent with toolkit
toolkit = Toolkit()
toolkit.register_tool_function(view_text_file)

agent = AgentScopeAgent(
    name="Friday",
    model=DashScopeChatModel(
        "qwen-max",
        api_key=os.getenv("DASHSCOPE_API_KEY"),
    ),
    agent_config={
        "sys_prompt": "You're a helpful assistant named Friday.",
        "toolkit": toolkit,
    },
    agent_builder=ReActAgent,
)

# 2. Create AgentApp with multiple endpoints
app = AgentApp(agent=agent)

@app.endpoint("/sync")
def sync_handler(request: AgentRequest):
    return {"status": "ok", "payload": request}

@app.endpoint("/async")
async def async_handler(request: AgentRequest):
    return {"status": "ok", "payload": request}

@app.endpoint("/stream_async")
async def stream_async_handler(request: AgentRequest):
    for i in range(5):
        yield f"async chunk {i}, with request payload {request}\n"

@app.endpoint("/stream_sync")
def stream_sync_handler(request: AgentRequest):
    for i in range(5):
        yield f"sync chunk {i}, with request payload {request}\n"

@app.task("/task", queue="celery1")
def task_handler(request: AgentRequest):
    time.sleep(30)
    return {"status": "ok", "payload": request}

@app.task("/atask")
async def atask_handler(request: AgentRequest):
    import asyncio
    await asyncio.sleep(15)
    return {"status": "ok", "payload": request}

print("✅ Agent and endpoints configured successfully")
```

**Note**: The above configuration is shared across all deployment methods below. Each method will show only the deployment-specific code.

## Method 1: Local Daemon Deployment

**Best for**: Development, testing, and single-user scenarios where you need persistent service with manual control.

### Features
- Persistent service in main process
- Manual lifecycle management
- Interactive control and monitoring
- Direct resource sharing

### Implementation

Using the agent and endpoints defined in the [Common Agent Setup](#common-agent-setup) section:

```{code-cell}
# daemon_deploy.py
import asyncio
from agentscope_runtime.engine.deployers.local_deployer import LocalDeployManager
from agent_app import app  # Import the configured app

# Deploy in daemon mode
async def main():
    await app.deploy(LocalDeployManager())

if __name__ == "__main__":
    asyncio.run(main())
    input("Press Enter to stop the server...")
```

**Key Points**:
- Service runs in the main process (blocking)
- Manually stopped with Ctrl+C or by ending the script
- Best for development and testing

### Testing the Deployed Service

Once deployed, you can test the endpoints using curl or Python:

**Using curl:**

```bash
# Test health endpoint
curl http://localhost:8080/health

# Call sync endpoint
curl -X POST http://localhost:8080/sync \
  -H "Content-Type: application/json" \
  -d '{"input": [{"role": "user", "content": [{"type": "text", "text": "What is the weather in Beijing?"}]}], "session_id": "123"}'

# Call streaming endpoint
curl -X POST http://localhost:8080/stream_sync \
  -H "Content-Type: application/json" \
  -d '{"input": [{"role": "user", "content": [{"type": "text", "text": "What is the weather in Beijing?"}]}], "session_id": "123"}'

# Submit a task
curl -X POST http://localhost:8080/task \
  -H "Content-Type: application/json" \
  -d '{"input": [{"role": "user", "content": [{"type": "text", "text": "What is the weather in Beijing?"}]}], "session_id": "123"}'
```

**Using OpenAI SDK:**
```python
from openai import OpenAI

client = OpenAI(base_url="http://0.0.0.0:8080/compatible-mode/v1")

response = client.responses.create(
  model="any_name",
  input="What is the weather in Beijing?"
)

print(response)
```


## Method 2: Detached Process Deployment

**Best for**: Production services requiring process isolation, automated management, and independent lifecycle.

### Features
- Independent process execution
- Automated lifecycle management
- Remote shutdown capabilities
- Service persistence after main script exit

### Implementation

Using the agent and endpoints defined in the [Common Agent Setup](#common-agent-setup) section:

```{code-cell}
# detached_deploy.py
import asyncio
from agentscope_runtime.engine.deployers.local_deployer import LocalDeployManager
from agentscope_runtime.engine.deployers.utils.deployment_modes import DeploymentMode
from agent_app import app  # Import the configured app

async def main():
    """Deploy app in detached process mode"""
    print("🚀 Deploying AgentApp in detached process mode...")

    # Deploy in detached mode
    deployment_info = await app.deploy(
        LocalDeployManager(host="127.0.0.1", port=8080),
        mode=DeploymentMode.DETACHED_PROCESS,
    )

    print(f"✅ Deployment successful: {deployment_info['url']}")
    print(f"📍 Deployment ID: {deployment_info['deploy_id']}")
    print(f"""
🎯 Service started, test with:
curl {deployment_info['url']}/health
curl -X POST {deployment_info['url']}/admin/shutdown  # To stop

⚠️ Note: Service runs independently until stopped.
""")
    return deployment_info

if __name__ == "__main__":
    asyncio.run(main())
```

**Key Points**:
- Service runs in a separate detached process
- Script exits after deployment, service continues
- Remote shutdown via `/admin/shutdown` endpoint

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

Using the agent and endpoints defined in the [Common Agent Setup](#common-agent-setup) section:

```{code-cell}
# k8s_deploy.py
import asyncio
import os
from agentscope_runtime.engine.deployers.kubernetes_deployer import (
    KubernetesDeployManager,
    RegistryConfig,
    K8sConfig,
)
from agent_app import app  # Import the configured app

async def deploy_to_k8s():
    """Deploy AgentApp to Kubernetes"""

    # Configure registry and K8s connection
    deployer = KubernetesDeployManager(
        kube_config=K8sConfig(
            k8s_namespace="agentscope-runtime",
            kubeconfig_path=None,
        ),
        registry_config=RegistryConfig(
            registry_url="your-registry-url",
            namespace="agentscope-runtime",
        ),
        use_deployment=True,
    )

    # Deploy with configuration
    result = await app.deploy(
        deployer,
        port="8080",
        replicas=1,
        image_name="agent_app",
        image_tag="v1.0",
        requirements=["agentscope", "fastapi", "uvicorn"],
        base_image="python:3.10-slim-bookworm",
        environment={
            "PYTHONPATH": "/app",
            "DASHSCOPE_API_KEY": os.environ.get("DASHSCOPE_API_KEY"),
        },
        runtime_config={
            "resources": {
                "requests": {"cpu": "200m", "memory": "512Mi"},
                "limits": {"cpu": "1000m", "memory": "2Gi"},
            },
        },
        platform="linux/amd64",
        push_to_registry=True,
    )

    print(f"✅ Deployed to: {result['url']}")
    return result, deployer

if __name__ == "__main__":
    asyncio.run(deploy_to_k8s())
```

**Key Points**:
- Containerized deployment with auto-scaling support
- Resource limits and health checks configured
- Can be scaled with `kubectl scale deployment`


## Method 4: ModelStudio Deployment

**Best for**: Alibaba Cloud users requiring managed cloud deployment with built-in monitoring, scaling, and integration with Alibaba Cloud ecosystem.

### Features
- Managed cloud deployment on Alibaba Cloud
- Integrated with DashScope LLM services
- Built-in monitoring and analytics
- Automatic scaling and resource management
- OSS integration for artifact storage
- Web console for deployment management

### Prerequisites for ModelStudio Deployment

```bash
# Ensure environment variables are set
export DASHSCOPE_API_KEY="your-dashscope-api-key"
export ALIBABA_CLOUD_ACCESS_KEY_ID="your-access-key-id"
export ALIBABA_CLOUD_ACCESS_KEY_SECRET="your-access-key-secret"
export MODELSTUDIO_WORKSPACE_ID="your-workspace-id"

# Optional OSS-specific credentials
export OSS_ACCESS_KEY_ID="your-oss-access-key-id"
export OSS_ACCESS_KEY_SECRET="your-oss-access-key-secret"
```

### Implementation

Using the agent and endpoints defined in the [Common Agent Setup](#common-agent-setup) section:

```{code-cell}
# modelstudio_deploy.py
import asyncio
import os
from agentscope_runtime.engine.deployers.modelstudio_deployer import (
    ModelstudioDeployManager,
    OSSConfig,
    ModelstudioConfig,
)
from agent_app import app  # Import the configured app

async def deploy_to_modelstudio():
    """Deploy AgentApp to Alibaba Cloud ModelStudio"""

    # Configure OSS and ModelStudio
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

    print(f"✅ Deployed to ModelStudio: {result['url']}")
    print(f"📦 Artifact: {result['artifact_url']}")
    return result

if __name__ == "__main__":
    asyncio.run(deploy_to_modelstudio())
```

**Key Points**:
- Fully managed cloud deployment on Alibaba Cloud
- Built-in monitoring and auto-scaling
- Integrated with DashScope LLM services


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
