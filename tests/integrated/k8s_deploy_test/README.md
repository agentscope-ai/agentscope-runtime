# Kubernetes Deployer Example with LLM Agent

This example demonstrates how to deploy LLM Agent services to Kubernetes clusters using the KubernetesDeployer.

## Prerequisites

1. **Environment Setup**
   - Python 3.9+
   - Docker installed and running
   - Kubernetes cluster access (kubectl configured)
   - Container registry access (optional for local testing)

2. **API Keys**
   - DashScope API Key (for Qwen LLM)

3. **Dependencies**
   - All dependencies are included in the agentscope-runtime package

## Quick Start

### 1. Environment Configuration

Create a `.env` file in the project root or set environment variables:

```bash
# Required for LLM functionality
DASHSCOPE_API_KEY=your_dashscope_api_key_here

# Optional: Custom registry settings
REGISTRY_URL=your-registry.com
REGISTRY_USERNAME=your-username
REGISTRY_PASSWORD=your-password
```

### 2. Kubernetes Configuration

Ensure your kubectl is properly configured:

```bash
# Check cluster access
kubectl cluster-info

# Create namespace (optional)
kubectl create namespace agentscope
```

### 3. Container Registry Setup (Optional)

For production use, configure your container registry:

```bash
# Create registry secret if using private registry
kubectl create secret docker-registry registry-secret \
  --docker-server=your-registry.com \
  --docker-username=your-username \
  --docker-password=your-password \
  --docker-email=your-email@example.com \
  --namespace=agentscope
```

### 4. Run the Example

```bash
# Navigate to the example directory
cd /Users/zhicheng/repo/agentscope-runtime/tests/integrated/k8s_deploy_test

# Run the complete example
python kubernetes_deployer_example.py
```

## Example Features

The example demonstrates:

1. **Basic LLM Agent Deployment**: Deploy a QwenLLM-based agent with streaming support
2. **Scaling Operations**: Scale replicas up and down dynamically
3. **Production Configuration**: Advanced deployment with resource limits and security
4. **Deployment Management**: Start, stop, restart, and inspect services
5. **Resource Cleanup**: Clean removal of all K8s resources
6. **Error Handling**: Graceful handling of deployment failures

## Configuration Options

### Registry Configuration
```python
registry_config = RegistryConfig(
    registry_url="your-registry.com",
    username="your-username",
    password="your-password",
    namespace="llm-agents"
)
```

### Kubernetes Configuration
```python
k8s_config = K8sConfig(
    namespace="agentscope",
    kubeconfig_path="~/.kube/config"  # or None for in-cluster
)
```

### Deployment Configuration
```python
result = await deployer.deploy(
    runner=runner,                    # Complete runner object
    user_code_path=user_code_dir,    # Custom user code
    requirements=req_file,           # Python dependencies
    replicas=2,                      # Number of replicas
    stream=True,                     # Enable streaming
    endpoint_path="/chat",           # Custom endpoint
    environment={                    # Environment variables
        "DASHSCOPE_API_KEY": "...",
        "LOG_LEVEL": "INFO"
    },
    runtime_config={                 # K8s runtime config
        "resources": {
            "requests": {"memory": "512Mi", "cpu": "500m"},
            "limits": {"memory": "1Gi", "cpu": "1000m"}
        }
    }
)
```

## Testing the Deployment

After deployment, test the service:

```bash
# Get service URL from logs or deployment result
SERVICE_URL="http://node-ip:nodeport"

# Test health endpoint
curl $SERVICE_URL/health

# Test chat endpoint with streaming
curl -X POST $SERVICE_URL/chat \
  -H "Content-Type: application/json" \
  -d '{
    "input": [
      {
        "role": "user",
        "content": [{"type": "text", "text": "Hello, how are you?"}]
      }
    ],
    "stream": true,
    "session_id": "test-session"
  }'
```

## Troubleshooting

### Common Issues

1. **API Key Missing**
   - Ensure `DASHSCOPE_API_KEY` is set in environment
   - Check .env file is loaded properly

2. **Kubernetes Access**
   - Verify kubectl configuration: `kubectl cluster-info`
   - Check namespace permissions
   - Ensure Docker is running for image builds

3. **Registry Issues**
   - Verify registry credentials
   - Check image push/pull permissions
   - For local testing, you can skip registry and use local images

4. **Resource Limits**
   - Ensure cluster has sufficient resources
   - Check node capacity: `kubectl describe nodes`
   - Adjust resource requests/limits if needed

### Debug Commands

```bash
# Check deployment status
kubectl get deployments -n agentscope

# Check pods
kubectl get pods -n agentscope

# View logs
kubectl logs -l app=agent-<deploy-id> -n agentscope

# Describe resources
kubectl describe deployment agent-<deploy-id> -n agentscope
```

## Architecture

The deployment creates:
- **Docker Image**: Contains the complete LLM runner with user code
- **Kubernetes Deployment**: Manages replica pods with rolling updates
- **Kubernetes Service**: Exposes the deployment via NodePort
- **Health Checks**: Built-in health monitoring endpoints

## Security Considerations

- Uses non-root user in containers
- Read-only root filesystem (optional)
- Resource limits enforced
- Network policies can be applied
- Image pull secrets for private registries