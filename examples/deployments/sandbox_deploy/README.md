# Sandbox Deployment Example

This example demonstrates how to deploy an AgentScope Runtime agent as a **Sandbox custom resource** (`agents.kruise.io/v1alpha1`) using the built-in Sandbox deployer.

## Overview

The `app_deploy_to_sandbox.py` script shows how to:
- Configure a container registry for storing Docker images
- Set up Kubernetes connection and namespace
- Deploy an LLM agent using AgentApp with endpoint
- Auto-create a LoadBalancer Service for external access
- Test the deployed service with endpoint
- Clean up resources (Sandbox CR + Service) after use

## Prerequisites

Before running this example, ensure you have:

1. **Kubernetes cluster access**: A running Kubernetes cluster with kubectl configured
2. **Sandbox CRD installed**: The Sandbox CRD (`agents.kruise.io/v1alpha1`) must be installed on the cluster
3. **Container registry access**: Access to a container registry (Docker Hub, ACR, etc.)
4. **Python environment**: Python 3.10+ with agentscope-runtime installed
5. **API keys**: Required API keys for your LLM provider (e.g., DASHSCOPE_API_KEY for Qwen)

## Setup

1. **Install dependencies**:
   ```bash
   pip install "agentscope-runtime[ext]>=1.0.0"
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

4. **Verify Sandbox is installed**:
   **`Kruise Agents`**: https://github.com/openkruise/agents
   ```bash
   kubectl get crd sandboxes.agents.kruise.io
   ```

## Configuration Parameters

### Registry Configuration

```python
registry_config = RegistryConfig(
    registry_url="your-registry-url",
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
- **`kubeconfig_path`**: Path to kubeconfig file (None uses default kubectl config)

### Runtime Configuration

```python
runtime_config = {
    "resources": {
        "requests": {"cpu": "200m", "memory": "512Mi"},
        "limits": {"cpu": "1000m", "memory": "2Gi"},
    },
    "image_pull_policy": "IfNotPresent",
    # Optional:
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

### Sandbox Configuration

```python
sandbox_config = {
    # Basic settings
    "port": "8080",
    "image_tag": "linux-amd64-1",
    "image_name": "agent_app",
    "annotations": {},
    "labels": {},

    # Dependencies
    "requirements": ["agentscope", "fastapi", "uvicorn"],
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

    # Runtime & deployment
    "runtime_config": runtime_config,
    "deploy_timeout": 300,
    "health_check": True,
    "platform": "linux/amd64",
    "push_to_registry": True,
}
```

#### Basic Configuration
- **`port`**: Container port for the web service
- **`image_tag`**: Docker image tag identifier
- **`image_name`**: Base name for the Docker image
- **`annotations`**: Sandbox CR annotations
- **`labels`**: Sandbox CR labels (the deployer auto-adds `app: <resource_name>` for Service selector)

#### Dependencies Configuration
- **`requirements`**: Python packages to install via pip
- **`extra_packages`**: Additional local Python files to include in the image
- **`base_image`**: Base Docker image (Python runtime)

#### Deployment Settings
- **`deploy_timeout`**: Maximum time (seconds) to wait for sandbox readiness
- **`platform`**: Target platform architecture
- **`push_to_registry`**: Whether to push the built image to the registry

## Running the Deployment

1. **Customize the configuration**:
   Edit `app_deploy_to_sandbox.py` to match your environment:
   - Update `registry_url` to your container registry
   - Modify `k8s_namespace` if needed
   - Adjust resource limits based on your cluster capacity
   - Set appropriate environment variables

2. **Run the deployment**:
   ```bash
   cd examples/deployments/sandbox_deploy
   python app_deploy_to_sandbox.py
   ```

3. **Monitor the deployment**:
   The script will output:
   - Deploy ID and status
   - Service URL for accessing the agent
   - Resource names in Kubernetes
   - Test commands for verification

4. **Test the deployed service**:
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
   kubectl get sandbox -n agentscope-runtime
   kubectl get svc -n agentscope-runtime
   kubectl get pods -n agentscope-runtime
   kubectl logs -l app=<resource_name> -n agentscope-runtime
   ```

6. **Cleanup**:
   The script will prompt you to press Enter to cleanup resources automatically.
   You can also use the CLI:
   ```bash
   agentscope stop <deploy_id>
   ```

## Troubleshooting

### Common Issues

1. **Sandbox CRD not found**:
   ```bash
   kubectl get crd sandboxes.agents.kruise.io
   # If missing, install the Sandbox operator first
   ```

2. **Registry Authentication**:
   ```bash
   docker login your-registry-url
   ```

3. **Kubernetes Permissions**:
   ```bash
   kubectl auth can-i create sandboxes.agents.kruise.io --namespace=agentscope-runtime
   ```

4. **Resource Limits**:
   ```bash
   kubectl describe nodes
   kubectl get resourcequota -n agentscope-runtime
   ```

5. **Image Pull Errors**:
   ```bash
   kubectl describe pod <pod-name> -n agentscope-runtime
   ```

### Logs and Debugging

- View pod logs: `kubectl logs <pod-name> -n agentscope-runtime`
- Describe sandbox: `kubectl describe sandbox <name> -n agentscope-runtime`
- Check service endpoints: `kubectl get endpoints -n agentscope-runtime`

## Files Structure

- `app_deploy_to_sandbox.py`: Main deployment script using AgentApp with multiple endpoints
- `sandbox_deploy_config.yaml`: YAML configuration example
- `sandbox_deploy_config.json`: JSON configuration example
