# ModelStudio Deployment Example

This example demonstrates how to deploy an AgentScope Runtime agent to Alibaba Cloud ModelStudio using the built-in ModelStudio deployer.

## Overview

The `app_deploy_to_modelstudio.py` script shows how to:
- Configure OSS (Object Storage Service) for storing deployment artifacts
- Set up ModelStudio connection and workspace
- Deploy an LLM agent to Alibaba Cloud ModelStudio
- Package and upload the agent application
- Access the deployed service through ModelStudio console

## Prerequisites

Before running this example, ensure you have:

1. **Alibaba Cloud Account**: Active Alibaba Cloud account with ModelStudio service enabled
2. **API Keys**: Required Alibaba Cloud credentials and DashScope API key
3. **ModelStudio Workspace**: A configured ModelStudio workspace
4. **Python environment**: Python 3.10+ with agentscope-runtime installed
5. **OSS Access**: Access to Alibaba Cloud Object Storage Service

## Setup

1. **Install dependencies**:
   ```bash
   pip install "agentscope-runtime[ext]>=1.0.0"
   ```

2. **Set environment variables**:
   ```bash
   # Required API keys
   export DASHSCOPE_API_KEY="your-dashscope-api-key"
   export ALIBABA_CLOUD_ACCESS_KEY_ID="your-access-key-id"
   export ALIBABA_CLOUD_ACCESS_KEY_SECRET="your-access-key-secret"
   export MODELSTUDIO_WORKSPACE_ID="your-workspace-id"

   # Optional OSS-specific keys (will fallback to Alibaba Cloud keys if not set)
   export OSS_ACCESS_KEY_ID="your-oss-access-key-id"
   export OSS_ACCESS_KEY_SECRET="your-oss-access-key-secret"
   ```

3. **Configure environment file**:
   Copy and modify the `.env` file with your credentials:
   ```bash
   cp .env.example .env
   # Edit .env with your actual credentials
   ```

## Configuration Parameters

### OSS Configuration

```python
oss_config = OSSConfig(
    access_key_id=os.environ.get("OSS_ACCESS_KEY_ID",
                                  os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_ID")),
    access_key_secret=os.environ.get("OSS_ACCESS_KEY_SECRET",
                                      os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_SECRET")),
)
```

- **OSS credentials**: Optional specific OSS credentials, falls back to Alibaba Cloud credentials
- **Automatic fallback**: Uses main Alibaba Cloud credentials if OSS-specific ones aren't provided

### ModelStudio Configuration

```python
modelstudio_config = ModelstudioConfig(
    workspace_id=os.environ.get("MODELSTUDIO_WORKSPACE_ID"),
    access_key_id=os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_ID"),
    access_key_secret=os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_SECRET"),
    dashscope_api_key=os.environ.get("DASHSCOPE_API_KEY"),
)
```

- **`workspace_id`**: Your ModelStudio workspace identifier
- **`access_key_id/secret`**: Alibaba Cloud credentials for ModelStudio API access
- **`dashscope_api_key`**: DashScope API key for LLM access

### Deployment Configuration

```python
deployment_config = {
    # Basic configuration
    "deploy_name": "agent-app-example",
    "telemetry_enabled": True,

    # Dependencies
    "requirements": [
        "agentscope",
        "fastapi",
        "uvicorn",
    ],
    "extra_packages": [
        os.path.join(os.path.dirname(__file__), "others", "other_project.py"),
    ],

    # Environment variables
    "environment": {
        "PYTHONPATH": "/app",
        "LOG_LEVEL": "INFO",
        "DASHSCOPE_API_KEY": os.environ.get("DASHSCOPE_API_KEY"),
    },
}
```

#### Basic Configuration
- **`deploy_name`**: Name for the deployment in ModelStudio
- **`telemetry_enabled`**: Enable telemetry and monitoring

#### Dependencies Configuration
- **`requirements`**: Python packages to install
- **`extra_packages`**: Additional local Python files to include

#### Environment Variables
- **Runtime environment**: Configuration injected into the deployed service

## Running the Deployment

1. **Customize the configuration**:
   Edit `app_deploy_to_modelstudio.py` to match your environment:
   - Update workspace ID
   - Modify deployment name if needed
   - Adjust dependencies based on your agent requirements
   - The script creates an AgentScopeAgent automatically

2. **Run the deployment**:
   ```bash
   cd examples/deployments/modelstudio_deploy
   python app_deploy_to_modelstudio.py
   ```

3. **Monitor the deployment**:
   The script will output:
   - Deployment ID and status
   - Wheel package path
   - OSS artifact URL
   - Resource name and workspace information
   - ModelStudio console URL for management

4. **Access the deployed service**:
   After successful deployment, access your agent through ModelStudio:
   - Check deployment status in ModelStudio console
   - Use provided API endpoints for testing

## API Endpoints

After successful deployment, the service provides the following endpoints through ModelStudio:

### Basic Endpoints
- `GET /health` - Health check
- `POST /sync` - Synchronous conversation interface
- `POST /async` - Asynchronous conversation interface
- `POST /stream_async` - Streaming conversation interface
- `POST /stream_sync` - Streaming conversation interface

### Task Endpoints (if using Celery)
- `POST /task` - Celery task endpoint
- `POST /atask` - Async Celery task endpoint

## Test Commands

Once deployed, you can test using the provided URLs from ModelStudio:

### Health Check
```bash
curl https://your-modelstudio-url/health
```

### Synchronous Request
```bash
curl -X POST https://your-modelstudio-url/sync \
  -H "Content-Type: application/json" \
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
```

### Streaming Request
```bash
curl -X POST https://your-modelstudio-url/stream_async \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
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

## Environment Variables Reference

### Required Variables
```bash
# LLM Service
DASHSCOPE_API_KEY="your-dashscope-api-key"

# Alibaba Cloud
ALIBABA_CLOUD_ACCESS_KEY_ID="your-access-key-id"
ALIBABA_CLOUD_ACCESS_KEY_SECRET="your-access-key-secret"

# ModelStudio
MODELSTUDIO_WORKSPACE_ID="your-workspace-id"
```

### Optional Variables
```bash
# OSS-specific credentials (optional)
OSS_ACCESS_KEY_ID="your-oss-access-key-id"
OSS_ACCESS_KEY_SECRET="your-oss-access-key-secret"
```

## Troubleshooting

### Common Issues

1. **Missing Environment Variables**:
   The script will check for required variables and display missing ones:
   ```bash
   ❌ Missing required environment vars: MODELSTUDIO_WORKSPACE_ID, ALIBABA_CLOUD_ACCESS_KEY_ID
   ```

2. **Authentication Issues**:
   Verify your Alibaba Cloud credentials have proper permissions:
   - ModelStudio service access
   - OSS read/write permissions
   - DashScope API access

3. **Workspace Configuration**:
   Ensure your ModelStudio workspace is properly configured and active.

4. **Network Connectivity**:
   Check connectivity to Alibaba Cloud services from your deployment environment.

### Logs and Debugging

- Monitor deployment progress through script output
- Check ModelStudio console for deployment status
- Review error messages for specific configuration issues
- Verify all required environment variables are set

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

### Agent Configuration

The script automatically creates an AgentScopeAgent with:
- DashScope LLM integration (Qwen models)
- Custom tools support
- ReActAgent builder for reasoning capabilities

### Environment Variable Management

Using `python-dotenv` for convenient credential management:
```python
from dotenv import load_dotenv
load_dotenv(".env")
```

## Comparison with Other Deployment Methods

| Feature | Daemon | Detached Process | Kubernetes | ModelStudio |
|---------|--------|------------------|------------|-------------|
| Process Control | Blocking | Independent | Container | Cloud-managed |
| Scalability | Single | Single Node | Multi-node | Cloud-scale |
| Resource Isolation | Process-level | Process-level | Container-level | Container-level |
| Management | Manual | API-based | Orchestrated | Platform-managed |
| Monitoring | Manual | Limited | Full | Built-in Dashboard |
| Best For | Development | Production (single) | Enterprise | Cloud users |

## Files Structure

- `app_deploy_to_modelstudio.py`: Main deployment script with AgentApp and multiple endpoints
- `.env`: Environment variables configuration file (optional)

## Next Steps

After successful deployment:

1. **Access ModelStudio Console**: Use the provided URL to manage your deployment
2. **Configure Gateway**: Set up domain name and gateway if needed for external access
3. **Monitor Performance**: Use ModelStudio's built-in monitoring and analytics
4. **Scale Resources**: Adjust resources based on usage patterns through ModelStudio console

This example provides a complete workflow for deploying AgentScope Runtime agents to Alibaba Cloud ModelStudio with production-ready configurations.