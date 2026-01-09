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

This guide covers the multiple advanced deployment methods available in AgentScope Runtime, providing production-ready solutions for different scenarios: **Local Daemon**, **Detached Process**, **Kubernetes Deployment**, **ModelStudio Deployment**, **AgentRun Deployment**, **PAI Deployment**, **Knative Deployment** and **Function Compute (FC) Deployment**.

## Overview of Deployment Methods

AgentScope Runtime offers multiple distinct deployment approaches, each tailored for specific use cases:

| Deployment Type           | Use Case | Scalability | Management | Resource Isolation |
|---------------------------|----------|-------------|------------|-------------------|
| **Local Daemon**          | Development & Testing | Single Process | Manual | Process-level |
| **Detached Process**      | Production Services | Single Node | Automated | Process-level |
| **Kubernetes**            | Enterprise & Cloud | Single-node (multi-node support coming) | Orchestrated | Container-level |
| **ModelStudio**           | Alibaba Cloud Platform | Cloud-managed | Platform-managed | Container-level |
| **AgentRun**              | AgentRun Platform | Cloud-managed | Platform-managed | Container-level |
| **PAI**                   | Alibaba Cloud PAI Platform | Cloud-managed | Platform-managed | Container-level |
| **Knative**               | Enterprise & Cloud | Single-node (multi-node support coming) | Orchestrated | Container-level |
| **Function Compute (FC)** | Alibaba Cloud Serverless | Cloud-managed | Platform-managed | MicroVM-level |

### Deployment Modes (DeploymentMode)

`LocalDeployManager` supports two deployment modes:

- **`DAEMON_THREAD`** (default): Runs the service in a daemon thread, main process blocks until service stops
- **`DETACHED_PROCESS`**: Runs the service in a separate process, main script can exit while service continues running

```{code-cell}
from agentscope_runtime.engine.deployers.utils.deployment_modes import DeploymentMode

# Use different deployment modes
await app.deploy(
    LocalDeployManager(host="0.0.0.0", port=8080),
    mode=DeploymentMode.DAEMON_THREAD,  # or DETACHED_PROCESS
)
```

## Prerequisites

### 🔧 Installation Requirements

Install AgentScope Runtime with all deployment dependencies:

```bash
# Basic installation
pip install agentscope-runtime>=1.0.0

# For Kubernetes deployment
pip install "agentscope-runtime[ext]>=1.0.0"
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

(common-agent-setup)=

## Common Agent Setup

All deployment methods share the same agent and endpoint configuration. Let's first create our base agent and define the endpoints:

```{code-cell}
# agent_app.py - Shared configuration for all deployment methods
# -*- coding: utf-8 -*-
import os

from agentscope.agent import ReActAgent
from agentscope.formatter import DashScopeChatFormatter
from agentscope.model import DashScopeChatModel
from agentscope.pipeline import stream_printing_messages
from agentscope.tool import Toolkit, execute_python_code

from agentscope_runtime.adapters.agentscope.memory import (
    AgentScopeSessionHistoryMemory,
)
from agentscope_runtime.engine.app import AgentApp
from agentscope_runtime.engine.schemas.agent_schemas import AgentRequest
from agentscope_runtime.engine.services.agent_state import (
    InMemoryStateService,
)
from agentscope_runtime.engine.services.session_history import (
    InMemorySessionHistoryService,
)

app = AgentApp(
    app_name="Friday",
    app_description="A helpful assistant",
)


@app.init
async def init_func(self):
    self.state_service = InMemoryStateService()
    self.session_service = InMemorySessionHistoryService()

    await self.state_service.start()
    await self.session_service.start()


@app.shutdown
async def shutdown_func(self):
    await self.state_service.stop()
    await self.session_service.stop()


@app.query(framework="agentscope")
async def query_func(
    self,
    msgs,
    request: AgentRequest = None,
    **kwargs,
):
    assert kwargs is not None, "kwargs is Required for query_func"
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
            enable_thinking=True,
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


# 2. Create AgentApp with multiple endpoints
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

Using the agent and endpoints defined in the {ref}`Common Agent Setup<common-agent-setup>` section:

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

Using the agent and endpoints defined in the {ref}`Common Agent Setup<common-agent-setup>` section:

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
deployment_info = await app.deploy(
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

Using the agent and endpoints defined in the {ref}`Common Agent Setup<common-agent-setup>` section:

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


## Method 4: Serverless Deployment: ModelStudio

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

Using the agent and endpoints defined in the {ref}`Common Agent Setup<common-agent-setup>` section:

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

## Method 5: Serverless Deployment: AgentRun

**Best For**: Alibaba Cloud users who need to deploy agents to AgentRun service with automated build, upload, and deployment workflows.

### Features
- Managed deployment on Alibaba Cloud AgentRun service
- Automatic project building and packaging
- OSS integration for artifact storage
- Complete lifecycle management
- Automatic runtime endpoint creation and management

### AgentRun Deployment Prerequisites

```bash
# Ensure environment variables are set
# More env settings, please refer to the table below
export ALIBABA_CLOUD_ACCESS_KEY_ID="your-access-key-id"
export ALIBABA_CLOUD_ACCESS_KEY_SECRET="your-access-key-secret"
export AGENT_RUN_REGION_ID="cn-hangzhou"  # or other regions

# OSS configuration (for storing build artifacts)
export OSS_ACCESS_KEY_ID="your-oss-access-key-id"
export OSS_ACCESS_KEY_SECRET="your-oss-access-key-secret"
export OSS_REGION="cn-hangzhou"
export OSS_BUCKET_NAME="your-bucket-name"
```

You can set the following environment variables or `AgentRunConfig` to customize the deployment:

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ALIBABA_CLOUD_ACCESS_KEY_ID` | Yes | - | Alibaba Cloud Access Key ID |
| `ALIBABA_CLOUD_ACCESS_KEY_SECRET` | Yes | - | Alibaba Cloud Access Key Secret |
| `AGENT_RUN_REGION_ID` | No | `cn-hangzhou` | Region ID for AgentRun service |
| `AGENT_RUN_ENDPOINT` | No | `agentrun.{region_id}.aliyuncs.com` | AgentRun service endpoint |
| `AGENT_RUN_LOG_STORE` | No | - | Log store name (requires log_project to be set) |
| `AGENT_RUN_LOG_PROJECT` | No | - | Log project name (requires log_store to be set) |
| `AGENT_RUN_NETWORK_MODE` | No | `PUBLIC` | Network mode: `PUBLIC`/`PRIVATE`/`PUBLIC_AND_PRIVATE` |
| `AGENT_RUN_VPC_ID` | Conditional | - | VPC ID (required if network_mode is `PRIVATE`) |
| `AGENT_RUN_SECURITY_GROUP_ID` | Conditional | - | Security Group ID (required if network_mode is `PRIVATE`) |
| `AGENT_RUN_VSWITCH_IDS` | Conditional | - | VSwitch IDs in JSON array format (required if network_mode is `PRIVATE`) |
| `AGENT_RUN_CPU` | No | `2.0` | CPU allocation in cores |
| `AGENT_RUN_MEMORY` | No | `2048` | Memory allocation in MB |
| `AGENT_RUN_EXECUTION_ROLE_ARN` | No | - | Execution role ARN for permissions |
| `AGENT_RUN_SESSION_CONCURRENCY_LIMIT` | No | `200` | Session concurrency limit |
| `AGENT_RUN_SESSION_IDLE_TIMEOUT_SECONDS` | No | `600` | Session idle timeout in seconds |
| `OSS_ACCESS_KEY_ID` | No | `ALIBABA_CLOUD_ACCESS_KEY_ID` | OSS Access Key ID (falls back to Alibaba Cloud credentials) |
| `OSS_ACCESS_KEY_SECRET` | No | `ALIBABA_CLOUD_ACCESS_KEY_SECRET` | OSS Access Key Secret (falls back to Alibaba Cloud credentials) |
| `OSS_REGION` | No | `cn-hangzhou` | OSS region |
| `OSS_BUCKET_NAME` | Yes | - | OSS bucket name for storing build artifacts |

### Implementation

Using the agent and endpoints defined in the {ref}`Common Agent Setup<common-agent-setup>` section:

```{code-cell}
# agentrun_deploy.py
import asyncio
import os
from agentscope_runtime.engine.deployers.agentrun_deployer import (
    AgentRunDeployManager,
    OSSConfig,
    AgentRunConfig,
)
from agent_app import app  # Import configured app

async def deploy_to_agentrun():
    """Deploy AgentApp to Alibaba Cloud AgentRun service"""

    # Configure OSS and AgentRun
    deployer = AgentRunDeployManager(
        oss_config=OSSConfig(
            access_key_id=os.environ.get("OSS_ACCESS_KEY_ID"),
            access_key_secret=os.environ.get("OSS_ACCESS_KEY_SECRET"),
            region=os.environ.get("OSS_REGION"),
            bucket_name=os.environ.get("OSS_BUCKET_NAME"),
        ),
        agentrun_config=AgentRunConfig(
            access_key_id=os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_ID"),
            access_key_secret=os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_SECRET"),
            region_id=os.environ.get("ALIBABA_CLOUD_REGION_ID", "cn-hangzhou"),
        ),
    )

    # Execute deployment
    result = await app.deploy(
        deployer,
        endpoint_path="/process",
        requirements=["agentscope", "fastapi", "uvicorn"],
        environment={
            "PYTHONPATH": "/app",
            "DASHSCOPE_API_KEY": os.environ.get("DASHSCOPE_API_KEY"),
        },
        deploy_name="agent-app-example",
        project_dir=".",  # Current project directory
        cmd="python -m uvicorn app:app --host 0.0.0.0 --port 8080",
    )

    print(f"✅ Deployed to AgentRun: {result['url']}")
    print(f"📍 AgentRun ID: {result.get('agentrun_id', 'N/A')}")
    print(f"📦 Artifact URL: {result.get('artifact_url', 'N/A')}")
    return result

if __name__ == "__main__":
    asyncio.run(deploy_to_agentrun())
```

**Key Points**:
- Automatically builds and packages the project as a wheel file
- Uploads artifacts to OSS
- Creates and manages runtime in the AgentRun service
- Automatically creates public access endpoints
- Supports updating existing deployments (via `agentrun_id` parameter)

### Configuration

#### OSSConfig

OSS configuration for storing build artifacts:

```python
OSSConfig(
    access_key_id="your-access-key-id",
    access_key_secret="your-access-key-secret",
    region="cn-hangzhou",
    bucket_name="your-bucket-name",
)
```

#### AgentRunConfig

AgentRun service configuration:

```python
AgentRunConfig(
    access_key_id="your-access-key-id",
    access_key_secret="your-access-key-secret",
    region_id="cn-hangzhou",  # Supported regions: cn-hangzhou, cn-beijing, etc.
)
```

### Advanced Usage

#### Using Pre-built Wheel Files

```python
result = await app.deploy(
    deployer,
    external_whl_path="/path/to/prebuilt.whl",  # Use pre-built wheel
    skip_upload=False,  # Still needs to upload to OSS
    # ... other parameters
)
```

#### Updating Existing Deployment

```python
result = await app.deploy(
    deployer,
    agentrun_id="existing-agentrun-id",  # Update existing deployment
    # ... other parameters
)
```

## Method 6: PAI Deployment (Platform for AI)

**Best for**: Enterprise users who need to deploy on Alibaba Cloud PAI platform, leveraging LangStudio for project management and EAS (Elastic Algorithm Service) for service deployment.

### Features
- Fully managed deployment on Alibaba Cloud PAI platform
- Integrated LangStudio project and snapshot management
- EAS (Elastic Algorithm Service) service deployment
- Three resource types: Public Resource Pool, Dedicated Resource Group, Quota
- VPC network configuration support
- RAM role and permission configuration
- Tracing support
- Automatic/manual approval workflow
- Auto-generated deployment tags

### Prerequisites for PAI Deployment

```bash
# Set required environment variables
export ALIBABA_CLOUD_ACCESS_KEY_ID="your-access-key-id"
export ALIBABA_CLOUD_ACCESS_KEY_SECRET="your-access-key-secret"

# Optional configuration
export PAI_WORKSPACE_ID="your-workspace-id"
export REGION_ID="cn-hangzhou"  # or ALIBABA_CLOUD_REGION_ID
```

You can set the following environment variables or use config file/CLI parameters to customize deployment:

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ALIBABA_CLOUD_ACCESS_KEY_ID` | Yes | - | Alibaba Cloud Access Key ID |
| `ALIBABA_CLOUD_ACCESS_KEY_SECRET` | Yes | - | Alibaba Cloud Access Key Secret |
| `PAI_WORKSPACE_ID` | No | - | PAI Workspace ID (can be specified via CLI or config file) |
| `REGION_ID` / `ALIBABA_CLOUD_REGION_ID` | No | `cn-hangzhou` | Region ID |
| `ALIBABA_CLOUD_SECURITY_TOKEN` | No | - | STS Security Token (when using STS) |

### PAI Workspace Requirements

- If using a RAM user account, PAI Developer Role must be assigned
- OSS bucket must be configured for storing build artifacts
- (Optional) VPC with public network access if using DashScope models

> **Note**: Services deployed to PAI EAS have no public network access by default. If using DashScope models, configure a VPC with public network access. Reference: [Configure Network Connectivity](https://help.aliyun.com/zh/pai/user-guide/configure-network-connectivity)

### Implementation (SDK)

Using the agent and endpoints defined in the {ref}`Common Agent Setup<common-agent-setup>` section:

```{code-cell}
# pai_deploy.py
import asyncio
import os
from agentscope_runtime.engine.deployers.pai_deployer import (
    PAIDeployManager,
)
from agent_app import app  # Import configured app

async def deploy_to_pai():
    """Deploy AgentApp to Alibaba Cloud PAI"""

    # Create PAI deploy manager
    deployer = PAIDeployManager(
        workspace_id=os.environ.get("PAI_WORKSPACE_ID"),
        region_id=os.environ.get("REGION_ID", "cn-hangzhou"),
    )

    # Execute deployment
    result = await app.deploy(
        deployer,
        service_name="my-agent-service",
        project_dir="./my_agent",
        entrypoint="agent.py",
        resource_type="public",
        instance_type="ecs.c6.large",
        instance_count=1,
        environment={
            "DASHSCOPE_API_KEY": os.environ.get("DASHSCOPE_API_KEY"),
        },
        enable_trace=True,
        wait=True,
    )

    print(f"✅ Deployment successful: {result['url']}")
    print(f"📍 Deployment ID: {result['deploy_id']}")
    print(f"📦 Project ID: {result['flow_id']}")
    return result

if __name__ == "__main__":
    asyncio.run(deploy_to_pai())
```

**Key Points**:
- Automatically packages project and uploads to OSS
- Creates LangStudio project and snapshot
- Deploys as EAS service
- Supports multiple resource type configurations

### Implementation (CLI)

PAI deployment recommends using configuration files for clarity and maintainability:

**Method 1: Using Configuration File (Recommended)**

```bash
# Navigate to example directory
cd examples/deployments/pai_deploy

# Deploy using config file
agentscope deploy pai --config deploy_config.yaml

# Deploy with CLI overrides
agentscope deploy pai --config deploy_config.yaml --name new-service-name
```

**Method 2: Using CLI Only**

```bash
agentscope deploy pai ./my_agent \
  --name my-service \
  --workspace-id 12345 \
  --region cn-hangzhou \
  --instance-type ecs.c6.large \
  --env DASHSCOPE_API_KEY=your-key
```

**Full CLI Options**

```bash
agentscope deploy pai [SOURCE] [OPTIONS]

Arguments:
  SOURCE                  Source directory or file (optional if using config)

Options:
  --config, -c PATH       Path to deployment config file (.yaml)
  --name TEXT             Service name (required)
  --workspace-id TEXT     PAI workspace ID
  --region TEXT           Region ID (e.g., cn-hangzhou)
  --entrypoint TEXT       Entrypoint file (default: app.py, agent.py, main.py)
  --oss-path TEXT         OSS work directory
  --instance-type TEXT    Instance type (for public resource)
  --instance-count INT    Number of instances
  --resource-id TEXT      EAS resource group ID (for resource mode)
  --quota-id TEXT         PAI quota ID (for quota mode)
  --cpu INT               CPU cores
  --memory INT            Memory in MB
  --service-group TEXT    Service group name
  --resource-type TEXT    Resource type: public, resource, quota
  --vpc-id TEXT           VPC ID
  --vswitch-id TEXT       VSwitch ID
  --security-group-id TEXT  Security group ID
  --ram-role-arn TEXT     RAM role ARN
  --enable-trace/--no-trace  Enable/disable tracing
  --wait/--no-wait        Wait for deployment to complete
  --timeout INT           Deployment timeout in seconds
  --auto-approve/--no-auto-approve  Auto approve deployment
  --env, -E TEXT          Environment variable (KEY=VALUE, repeatable)
  --env-file PATH         Path to .env file
  --tag, -T TEXT          Tag (KEY=VALUE, repeatable)
```

### Configuration

#### PAIDeployConfig Structure

PAI deployment uses YAML configuration files with the following structure:

```yaml
# deploy_config.yaml
context:
  # PAI workspace ID (required)
  workspace_id: "your-workspace-id"
  # Region (e.g., cn-hangzhou, cn-shanghai)
  region: "cn-hangzhou"

spec:
  # Service name (required, unique within region)
  name: "my_agent_service"

  code:
    # Source directory (relative to config file location)
    source_dir: "my_agent"
    # Entrypoint file
    entrypoint: "agent.py"

  resources:
    # Resource type: public, resource, quota
    type: "public"
    # Instance type (required for public mode)
    instance_type: "ecs.c6.large"
    # Number of instances
    instance_count: 1

  # VPC configuration (optional)
  vpc_config:
    vpc_id: "vpc-xxxxx"
    vswitch_id: "vsw-xxxxx"
    security_group_id: "sg-xxxxx"

  # RAM role configuration (optional)
  identity:
    ram_role_arn: "acs:ram::xxx:role/xxx"

  # Observability configuration
  observability:
    enable_trace: true

  # Environment variables
  env:
    DASHSCOPE_API_KEY: "your-dashscope-api-key"

  # Tags
  tags:
    team: "ai-team"
    project: "agent-demo"
```

> **Note**: `code.source_dir` is resolved relative to the config file location.

#### Configuration Structure Reference

| Section | Description |
|---------|-------------|
| `context` | Deployment target (workspace, region, storage) |
| `spec.name` | Service name (required) |
| `spec.code` | Source directory and entrypoint |
| `spec.resources` | Resource allocation settings |
| `spec.vpc_config` | VPC network configuration (optional) |
| `spec.identity` | RAM role configuration (optional) |
| `spec.observability` | Tracing settings |
| `spec.env` | Environment variables |
| `spec.tags` | Deployment tags |

### Resource Types

PAI supports three resource types:

#### 1. Public Resource Pool (`type: "public"`)

Deploy on shared ECS instances, suitable for development/testing and small-scale deployments:

```yaml
spec:
  resources:
    type: "public"
    instance_type: "ecs.c6.large"  # Required
    instance_count: 1
```

#### 2. Dedicated Resource Group (`type: "resource"`)

Deploy on dedicated EAS resource group, suitable for production environments requiring resource isolation:

```yaml
spec:
  resources:
    type: "resource"
    resource_id: "eas-r-xxxxx"  # Required
    cpu: 2
    memory: 4096
```

#### 3. Quota-based (`type: "quota"`)

Deploy using PAI quota, suitable for enterprise-level resource management:

```yaml
spec:
  resources:
    type: "quota"
    quota_id: "quota-xxxxxxxx"  # Required
    cpu: 2
    memory: 4096
```

### VPC Configuration

Private network deployment configuration for scenarios requiring access to public or internal resources:

```yaml
spec:
  vpc_config:
    vpc_id: "vpc-xxxxx"
    vswitch_id: "vsw-xxxxx"
    security_group_id: "sg-xxxxx"
```

### Advanced Usage

#### Manual Approval Workflow

By default, deployments are auto-approved. For manual approval:

```bash
# Use --no-auto-approve option
agentscope deploy pai --config deploy_config.yaml --no-auto-approve
```

In interactive terminal, CLI will prompt you to choose:
- `[A]pprove` - Approve and start deployment
- `[C]ancel` - Cancel deployment
- `[S]kip` - Skip, approve later in console

#### Environment Variable Injection

**Method 1: Configuration File**

```yaml
spec:
  env:
    DASHSCOPE_API_KEY: "your-key"
    MY_CONFIG: "value"
```

**Method 2: CLI Parameters**

```bash
agentscope deploy pai ./my_agent \
  --env DASHSCOPE_API_KEY=your-key \
  --env MY_CONFIG=value
```

**Method 3: .env File**

```bash
agentscope deploy pai ./my_agent --env-file .env
```

#### Auto-Generated Tags

The following tags are automatically added to deployments:

- `deployed-by: agentscope-runtime`
- `client-version: <version>`
- `deploy-method: cli`

#### Managing Deployments

```bash
# Stop deployment
agentscope stop <deploy-id>

# View deployment status
# Visit the PAI console URL provided after deployment
```

### Troubleshooting

#### Common Issues

1. **"PAI deployer is not available"**

   ```bash
   pip install 'agentscope-runtime[ext]'
   ```

2. **"Workspace ID is required"**
   - Set `PAI_WORKSPACE_ID` environment variable, or
   - Use `--workspace-id` CLI option, or
   - Add `context.workspace_id` in config file

3. **"Service name is owned by another user"**
   - Choose a different service name (must be unique within region)

4. **Credential errors**
   - Verify `ALIBABA_CLOUD_ACCESS_KEY_ID` and `ALIBABA_CLOUD_ACCESS_KEY_SECRET`
   - Check RAM permissions for PAI/EAS/OSS access

5. **OSS upload failures**
   - Ensure OSS bucket exists and is accessible
   - Check region matches between workspace and OSS bucket

### Complete Example

For more detailed PAI deployment examples, refer to:
- Example directory: `examples/deployments/pai_deploy/`
- Config file example: `examples/deployments/pai_deploy/deploy_config.yaml`

## Method 7: Knative Deployment

**Best for**: Enterprise production environments requiring scalability, high availability, and cloud-native serverless container orchestration.

### Features
- Container-based Serverless deployment
- Provides automatic scaling from zero to thousands of instances, intelligent traffic routing
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

# Check Knative Serving installed
kubectl auth can-i create ksvc
```

### Implementation

Using the agent and endpoints defined in the {ref}`Common Agent Setup<common-agent-setup>` section:

```{code-cell}
# knative_deploy.py
import asyncio
import os
from agentscope_runtime.engine.deployers.knative_deployer import (
    KnativeDeployManager,
    RegistryConfig,
    K8sConfig,
)
from agent_app import app  # Import the configured app

async def deploy_to_knative():
    """Deploy AgentApp to Knative"""

    # Configure registry and K8s connection
    deployer = KnativeDeployManager(
        kube_config=K8sConfig(
            k8s_namespace="agentscope-runtime",
            kubeconfig_path=None,
        ),
        registry_config=RegistryConfig(
            registry_url="your-registry-url",
            namespace="agentscope-runtime",
        ),
    )

    # Deploy with configuration
    result = await app.deploy(
        deployer,
        port="8080",
        image_name="agent_app",
        image_tag="v1.0",
        requirements=["agentscope", "fastapi", "uvicorn"],
        base_image="python:3.10-slim-bookworm",
        environment={
            "PYTHONPATH": "/app",
            "DASHSCOPE_API_KEY": os.environ.get("DASHSCOPE_API_KEY"),
        },
        labels: {
          "app":"agent-ksvc",
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
    asyncio.run(deploy_to_knative())
```

**Key Points**:
- Containerized Serverless deployment
- Provides automatic scaling from zero to thousands of instances, intelligent traffic routing
- Resource limits and health checks configured

## Method 8: Serverless Deployment: Function Compute (FC)

**Best For**: Alibaba Cloud users who need to deploy agents to Function Compute (FC) service with automated build, upload, and deployment workflows. FC provides a true serverless experience with pay-per-use pricing and automatic scaling.

### Features
- Serverless deployment on Alibaba Cloud Function Compute
- Automatic project building and packaging with Docker
- OSS integration for artifact storage
- HTTP trigger for public access
- Session affinity support for stateful applications
- VPC and logging configuration support
- Pay-per-use pricing model

### FC Deployment Prerequisites

```bash
# Ensure environment variables are set
# More env settings, please refer to the table below
export ALIBABA_CLOUD_ACCESS_KEY_ID="your-access-key-id"
export ALIBABA_CLOUD_ACCESS_KEY_SECRET="your-access-key-secret"
export FC_ACCOUNT_ID="your-fc-account-id"
export FC_REGION_ID="cn-hangzhou"  # or other regions

# OSS configuration (for storing build artifacts)
export OSS_ACCESS_KEY_ID="your-oss-access-key-id"
export OSS_ACCESS_KEY_SECRET="your-oss-access-key-secret"
export OSS_REGION="cn-hangzhou"
export OSS_BUCKET_NAME="your-bucket-name"
```

You can set the following environment variables or `FCConfig` to customize the deployment:

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ALIBABA_CLOUD_ACCESS_KEY_ID` | Yes | - | Alibaba Cloud Access Key ID |
| `ALIBABA_CLOUD_ACCESS_KEY_SECRET` | Yes | - | Alibaba Cloud Access Key Secret |
| `FC_ACCOUNT_ID` | Yes | - | Alibaba Cloud Account ID for FC |
| `FC_REGION_ID` | No | `cn-hangzhou` | Region ID for FC service |
| `FC_LOG_STORE` | No | - | Log store name (requires log_project to be set) |
| `FC_LOG_PROJECT` | No | - | Log project name (requires log_store to be set) |
| `FC_VPC_ID` | No | - | VPC ID for private network access |
| `FC_SECURITY_GROUP_ID` | No | - | Security Group ID (required if vpc_id is set) |
| `FC_VSWITCH_IDS` | No | - | VSwitch IDs in JSON array format (required if vpc_id is set) |
| `FC_CPU` | No | `2.0` | CPU allocation in cores |
| `FC_MEMORY` | No | `2048` | Memory allocation in MB |
| `FC_DISK` | No | `512` | Disk allocation in MB |
| `FC_EXECUTION_ROLE_ARN` | No | - | Execution role ARN for permissions |
| `FC_SESSION_CONCURRENCY_LIMIT` | No | `200` | Session concurrency limit per instance |
| `FC_SESSION_IDLE_TIMEOUT_SECONDS` | No | `3600` | Session idle timeout in seconds |
| `OSS_ACCESS_KEY_ID` | No | `ALIBABA_CLOUD_ACCESS_KEY_ID` | OSS Access Key ID (falls back to Alibaba Cloud credentials) |
| `OSS_ACCESS_KEY_SECRET` | No | `ALIBABA_CLOUD_ACCESS_KEY_SECRET` | OSS Access Key Secret (falls back to Alibaba Cloud credentials) |
| `OSS_REGION` | No | `cn-hangzhou` | OSS region |
| `OSS_BUCKET_NAME` | Yes | - | OSS bucket name for storing build artifacts |

### Implementation

Using the agent and endpoints defined in the {ref}`Common Agent Setup<common-agent-setup>` section:

```{code-cell}
# fc_deploy.py
import asyncio
import os
from agentscope_runtime.engine.deployers.fc_deployer import (
    FCDeployManager,
    OSSConfig,
    FCConfig,
)
from agent_app import app  # Import configured app

async def deploy_to_fc():
    """Deploy AgentApp to Alibaba Cloud Function Compute (FC)"""

    # Configure OSS and FC
    deployer = FCDeployManager(
        oss_config=OSSConfig(
            access_key_id=os.environ.get("OSS_ACCESS_KEY_ID"),
            access_key_secret=os.environ.get("OSS_ACCESS_KEY_SECRET"),
            region=os.environ.get("OSS_REGION", "cn-hangzhou"),
            bucket_name=os.environ.get("OSS_BUCKET_NAME"),
        ),
        fc_config=FCConfig(
            access_key_id=os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_ID"),
            access_key_secret=os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_SECRET"),
            account_id=os.environ.get("FC_ACCOUNT_ID"),
            region_id=os.environ.get("FC_REGION_ID", "cn-hangzhou"),
        ),
    )

    # Execute deployment
    result = await app.deploy(
        deployer,
        deploy_name="agent-app-example",
        requirements=["agentscope", "fastapi", "uvicorn"],
        environment={
            "PYTHONPATH": "/code",
            "DASHSCOPE_API_KEY": os.environ.get("DASHSCOPE_API_KEY"),
        },
    )

    print(f"✅ Deployed to FC: {result['url']}")
    print(f"📍 Function Name: {result['function_name']}")
    print(f"🔗 Endpoint URL: {result['endpoint_url']}")
    print(f"📦 Artifact URL: {result['artifact_url']}")
    return result

if __name__ == "__main__":
    asyncio.run(deploy_to_fc())
```

**Key Points**:
- Automatically builds project with Docker and creates a deployable zip package
- Uploads artifacts to OSS for FC to pull
- Creates FC function with HTTP trigger for public access
- Supports session affinity via `x-agentscope-runtime-session-id` header
- Supports updating existing deployments (via `function_name` parameter)

### Configuration

#### OSSConfig

OSS configuration for storing build artifacts:

```python
OSSConfig(
    access_key_id="your-access-key-id",
    access_key_secret="your-access-key-secret",
    region="cn-hangzhou",
    bucket_name="your-bucket-name",
)
```

#### FCConfig

Function Compute service configuration:

```python
FCConfig(
    access_key_id="your-access-key-id",
    access_key_secret="your-access-key-secret",
    account_id="your-account-id",
    region_id="cn-hangzhou",  # Supported regions: cn-hangzhou, cn-beijing, etc.
    cpu=2.0,  # CPU cores
    memory=2048,  # Memory in MB
    disk=512,  # Disk in MB
)
```

### Advanced Usage

#### Updating Existing Function

```python
result = await app.deploy(
    deployer,
    function_name="existing-function-name",  # Update existing function
    # ... other parameters
)
```

#### Deploying from Project Directory

```python
result = await app.deploy(
    deployer,
    project_dir="/path/to/project",  # Project directory
    cmd="python main.py",  # Startup command
    deploy_name="my-agent-app",
    # ... other parameters
)
```

### Testing the Deployed Service

Once deployed, you can test the endpoints using curl:

```bash
# Health check
curl https://<your-endpoint-url>/health

# Test sync endpoint with session affinity
curl -X POST https://<your-endpoint-url>/sync \
  -H "Content-Type: application/json" \
  -H "x-agentscope-runtime-session-id: 123" \
  -d '{
    "input": [
      {
        "role": "user",
        "content": [
          {
            "type": "text",
            "text": "Hello, how are you?"
          }
        ]
      }
    ],
    "session_id": "123"
  }'

# Test streaming endpoint
curl -X POST https://<your-endpoint-url>/stream_async \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -H "x-agentscope-runtime-session-id: 123" \
  --no-buffer \
  -d '{
    "input": [
      {
        "role": "user",
        "content": [
          {
            "type": "text",
            "text": "Tell me a story"
          }
        ]
      }
    ],
    "session_id": "123"
  }'
```

**Note**: The `x-agentscope-runtime-session-id` header enables session affinity, which routes requests with the same session ID to the same FC instance for stateful operations.

