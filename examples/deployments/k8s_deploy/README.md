# Kubernetes Deployment Example

This example demonstrates how to deploy an AgentScope Runtime agent to Kubernetes using the built-in Kubernetes deployer.

## Overview

The `app_deploy_to_k8s.py` script shows how to:
- Configure a container registry for storing Docker images
- Set up Kubernetes connection and namespace
- Deploy an LLM agent using AgentApp with multiple endpoints
- Configure resource management and scaling
- Test the deployed service with various endpoints
- Clean up resources after use

## Prerequisites

Before running this example, ensure you have:

1. **Kubernetes cluster access**: A running Kubernetes cluster with kubectl configured
2. **Container registry access**: Access to a container registry (Docker Hub, ACR, etc.)
3. **Python environment**: Python 3.10+ with agentscope-runtime installed
4. **API keys**: Required API keys for your LLM provider (e.g., DASHSCOPE_API_KEY for Qwen)

## Setup

1. **Install dependencies**:
   ```bash
   pip install "agentscope-runtime[deployment]>=1.0.0"

   ```

2. **Set environment variables**:
   ```bash
   export DASHSCOPE_API_KEY="your-api-key"
   ```

3. **Configure Kubernetes access**:
   Ensure your `kubeconfig` is properly configured:
   ```bash
   kubectl cluster-info
   ```

## Configuration Parameters

### Registry Configuration

```python
registry_config = RegistryConfig(
    registry_url="your-resigstry-url",
    namespace="your-namespace",
)
```

- **`registry_url`**: The container registry URL where Docker images will be pushed
  - Examples: `docker.io`, `gcr.io/project-id`, `your-registry.com`
- **`namespace`**: The namespace/repository within the registry for organizing images

### Kubernetes Configuration

```python
k8s_config = K8sConfig(
    k8s_namespace="agentscope-runtime",
    kubeconfig_path="your-kubeconfig-local-path",
)
```

- **`k8s_namespace`**: Kubernetes namespace where resources will be deployed
  - Creates the namespace if it doesn't exist
- **`kubeconfig_path`**: Path to kubeconfig file (None uses default kubectl config at your local require kubectrl running)

### Runtime Configuration

```python
runtime_config = {
    "resources": {
        "requests": {"cpu": "200m", "memory": "512Mi"},
        "limits": {"cpu": "1000m", "memory": "2Gi"},
    },
    "image_pull_policy": "IfNotPresent",
    # Optional configurations:
    # "node_selector": {"node-type": "gpu"},
    # "tolerations": [...]
}
```

#### Resource Management
- **`requests`**: Guaranteed resources for the container
  - `cpu`: CPU units (200m = 0.2 CPU cores)
  - `memory`: Memory allocation (512Mi = 512 megabytes)
- **`limits`**: Maximum resources the container can use
  - `cpu`: Maximum CPU (1000m = 1 CPU core)
  - `memory`: Maximum memory (2Gi = 2 gigabytes)

#### Image Pull Policy
- **`IfNotPresent`**: Pull image only if not already present locally
- **`Always`**: Always pull the latest image
- **`Never`**: Never pull image (use local only)

#### Optional Configurations
- **`node_selector`**: Schedule pods on specific nodes with matching labels
- **`tolerations`**: Allow pods to run on nodes with matching taints

### Deployment Configuration

```python
deployment_config = {
    # Basic settings
    "port": "8080",
    "replicas": 1,
    "image_tag": "linux-amd64",
    "image_name": "agent_app",

    # Dependencies
    "requirements": [
        "agentscope",
        "fastapi",
        "uvicorn",
    ],
    "extra_packages": [
        os.path.join(os.path.dirname(__file__), "others", "other_project.py"),
    ],
    "base_image": "python:3.10-slim-bookworm",

    # Environment
    "environment": {
        "PYTHONPATH": "/app",
        "LOG_LEVEL": "INFO",
        "DASHSCOPE_API_KEY": os.environ.get("DASHSCOPE_API_KEY"),
    },

    # Deployment settings
    "runtime_config": runtime_config,
    "deploy_timeout": 300,
    "health_check": True,
    "platform": "linux/amd64",
    "push_to_registry": True,
}
```

#### Basic Configuration
- **`port`**: Container port for the web service
- **`replicas`**: Number of pod replicas to deploy
- **`image_tag`**: Docker image tag identifier
- **`image_name`**: Base name for the Docker image

#### Dependencies Configuration
- **`requirements`**: Python packages to install via pip
- **`extra_packages`**: Additional local Python files to include in the image
- **`base_image`**: Base Docker image (Python runtime)

#### Environment Variables that will inject into the image

#### Deployment Settings
- **`deploy_timeout`**: Maximum time (seconds) to wait for deployment completion
- **`health_check`**: Enable health check endpoint
- **`platform`**: Target platform architecture
- **`push_to_registry`**: Whether to push the built image to the registry

## Running the Deployment

1. **Customize the configuration**:
   Edit `app_deploy_to_k8s.py` to match your environment:
   - Update `registry_url` to your container registry
   - Modify `k8s_namespace` if needed
   - Adjust resource limits based on your cluster capacity
   - Set appropriate environment variables

2. **Run the deployment**:
   ```bash
   cd examples/deployments/k8s_deploy
   python app_deploy_to_k8s.py
   ```

3. **Monitor the deployment**:
   The script will output:
   - Deployment ID and status
   - Service URL for accessing the agent
   - Resource names in Kubernetes
   - Test commands for verification

4. **Test the deployed service**:
   Use the provided curl commands to test different endpoints:
   ```bash
   # Health check
   curl http://your-service-url/health

   # Synchronous request
   curl -X POST http://your-service-url/sync \
     -H "Content-Type: application/json" \
     -d '{"input": [{"role": "user", "content": [{"type": "text", "text": "Hello!"}]}], "session_id": "123"}'

   # Asynchronous request
   curl -X POST http://your-service-url/async \
     -H "Content-Type: application/json" \
     -d '{"input": [{"role": "user", "content": [{"type": "text", "text": "Hello!"}]}], "session_id": "123"}'

   # Streaming request
   curl -X POST http://your-service-url/stream_async \
     -H "Content-Type: application/json" \
     -H "Accept: text/event-stream" \
     --no-buffer \
     -d '{"input": [{"role": "user", "content": [{"type": "text", "text": "Tell me a story"}]}], "session_id": "123"}'
   ```

5. **View Kubernetes resources**:
   ```bash
   kubectl get pods -n agentscope-runtime
   kubectl get svc -n agentscope-runtime
   kubectl logs -l app=agent-app -n agentscope-runtime
   ```

6. **Cleanup**:
   The script will prompt you to press Enter to cleanup resources automatically.

## Troubleshooting

### Common Issues

1. **Registry Authentication**: Ensure Docker is logged into your registry:
   ```bash
   docker login your-registry-url
   ```

2. **Kubernetes Permissions**: Verify you have sufficient permissions:
   ```bash
   kubectl auth can-i create deployments --namespace=agentscope-runtime
   ```

3. **Resource Limits**: If pods fail to start, check if your cluster has enough resources:
   ```bash
   kubectl describe nodes
   kubectl get resourcequota -n agentscope-runtime
   ```

4. **Image Pull Errors**: Check if the image was pushed successfully:
   ```bash
   kubectl describe pod <pod-name> -n agentscope-runtime
   ```

### Logs and Debugging

- View pod logs: `kubectl logs <pod-name> -n agentscope-runtime`
- Describe pod status: `kubectl describe pod <pod-name> -n agentscope-runtime`
- Check service endpoints: `kubectl get endpoints -n agentscope-runtime`


## Advanced Features

### Multiple Endpoints

The example demonstrates how to create multiple endpoints for different use cases:

```python
@agent_app.endpoint("/sync")
def sync_handler(request: AgentRequest):
    return {"status": "ok", "payload": request}

@agent_app.endpoint("/async")
async def async_handler(request: AgentRequest):
    return {"status": "ok", "payload": request}

@agent_app.endpoint("/stream_async")
async def stream_async_handler(request: AgentRequest):
    for i in range(5):
        yield f"async chunk {i}, with request payload {request}\n"

@agent_app.task("/task", queue="celery1")
def task_handler(request: AgentRequest):
    time.sleep(30)
    return {"status": "ok", "payload": request}
```

### Service Testing

The script includes built-in service testing functionality that:
- Automatically tests sync and async endpoints after deployment
- Validates service health and availability
- Provides example curl commands for manual testing

### Cleanup Management

The deployment includes automatic cleanup capabilities:
- Interactive cleanup prompt
- Proper resource deletion through deployer.stop()
- Kubernetes resource verification

## Comparison with Other Deployment Methods

| Feature | Daemon | Detached Process | Kubernetes | ModelStudio |
|---------|--------|------------------|------------|-------------|
| Process Control | Blocking | Independent | Container | Cloud-managed |
| Scalability | Single | Single Node | Multi-node | Cloud-scale |
| Resource Isolation | Process-level | Process-level | Container-level | Container-level |
| Management | Manual | API-based | Orchestrated | Platform-managed |
| Best For | Development | Production (single) | Enterprise | Cloud users |

## Files Structure

- `app_deploy_to_k8s.py`: Main deployment script using AgentApp with multiple endpoints

This example provides a complete workflow for deploying AgentScope Runtime agents to Kubernetes with production-ready configurations.
