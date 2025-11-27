# AgentRun Deployment Example

This example demonstrates how to deploy an AgentScope Runtime agent to Alibaba Cloud AgentRun using the built-in AgentRun deployer.

## Overview

The `app_deploy_to_agentrun.py` script shows how to:
- Configure OSS (Object Storage Service) for storing deployment artifacts
- Set up AgentRun connection and configuration
- Deploy an LLM agent to Alibaba Cloud AgentRun
- Package and upload the agent application
- Access the deployed service through AgentRun console

## Prerequisites

Before running this example, ensure you have:

1. **Alibaba Cloud Account**: Active Alibaba Cloud account with AgentRun service enabled
2. **API Keys**: Required Alibaba Cloud credentials and DashScope API key
3. **Python environment**: Python 3.10+ with agentscope-runtime installed
4. **OSS Access**: Access to Alibaba Cloud Object Storage Service

## Setup

1. **Install dependencies**:
   ```bash
   pip install "agentscope-runtime[deployment]>=1.0.0"
   ```

2. **Set environment variables**:
   ```bash
   # Required: Alibaba Cloud Credentials
   export ALIBABA_CLOUD_ACCESS_KEY_ID="your-access-key-id"
   export ALIBABA_CLOUD_ACCESS_KEY_SECRET="your-access-key-secret"

   # Required: LLM API Key
   export DASHSCOPE_API_KEY="your-dashscope-api-key"

   # Optional: Region Configuration (default: cn-hangzhou)
   export AGENT_RUN_REGION_ID="cn-hangzhou"

   # Optional: OSS-specific keys (will fallback to Alibaba Cloud keys if not set)
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

### AgentRun Configuration

```python
agentrun_config = AgentRunConfig(
    access_key_id=os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_ID"),
    access_key_secret=os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_SECRET"),
    region_id=os.environ.get("AGENT_RUN_REGION_ID", "cn-hangzhou"),
    endpoint=os.environ.get("AGENT_RUN_ENDPOINT"),
)
```

- **`access_key_id/secret`**: Alibaba Cloud credentials for AgentRun API access
- **`region_id`**: Alibaba Cloud region (default: cn-hangzhou)
- **`endpoint`**: Custom endpoint URL (optional, defaults to agentrun.{region_id}.aliyuncs.com)

### Network Configuration

```python
# Network mode: PUBLIC, PRIVATE, or PUBLIC_AND_PRIVATE
network_mode = os.environ.get("AGENT_RUN_NETWORK_MODE", "PUBLIC")

# VPC Configuration (required if using PRIVATE network mode)
vpc_id = os.environ.get("AGENT_RUN_VPC_ID")
security_group_id = os.environ.get("AGENT_RUN_SECURITY_GROUP_ID")
vswitch_ids = os.environ.get("AGENT_RUN_VSWITCH_IDS")  # JSON array format
```

- **`network_mode`**: Defines network accessibility (PUBLIC/PRIVATE/PUBLIC_AND_PRIVATE)
- **`vpc_id`**: VPC identifier for private network deployment
- **`security_group_id`**: Security group for network access control
- **`vswitch_ids`**: List of vSwitch IDs for high availability

### Resource Configuration

```python
# CPU and Memory allocation
cpu = float(os.environ.get("AGENT_RUN_CPU", "2.0"))  # in cores
memory = int(os.environ.get("AGENT_RUN_MEMORY", "2048"))  # in MB
```

- **`cpu`**: CPU cores allocated to the agent (default: 2.0)
- **`memory`**: Memory in MB allocated to the agent (default: 2048)

### Log Configuration

```python
# Optional log configuration
log_store = os.environ.get("AGENT_RUN_LOG_STORE")
log_project = os.environ.get("AGENT_RUN_LOG_PROJECT")
```

- **`log_store`**: SLS log store name for application logs
- **`log_project`**: SLS log project name for log management

### Execution Configuration

```python
# Execution settings
execution_role_arn = os.environ.get("AGENT_RUN_EXECUTION_ROLE_ARN")
session_concurrency_limit = int(os.environ.get("AGENT_RUN_SESSION_CONCURRENCY_LIMIT", "1"))
session_idle_timeout_seconds = int(os.environ.get("AGENT_RUN_SESSION_IDLE_TIMEOUT_SECONDS", "600"))
```

- **`execution_role_arn`**: RAM role ARN for resource access
- **`session_concurrency_limit`**: Maximum concurrent sessions (default: 1)
- **`session_idle_timeout_seconds`**: Session idle timeout in seconds (default: 600)

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
        "PYTHONPATH": "/code",
        "LOG_LEVEL": "INFO",
        "DASHSCOPE_API_KEY": os.environ.get("DASHSCOPE_API_KEY"),
    },
}
```

#### Basic Configuration
- **`deploy_name`**: Name for the deployment in AgentRun
- **`telemetry_enabled`**: Enable telemetry and monitoring

#### Dependencies Configuration
- **`requirements`**: Python packages to install
- **`extra_packages`**: Additional local Python files to include

#### Environment Variables
- **Runtime environment**: Configuration injected into the deployed service

## Running the Deployment

1. **Customize the configuration**:
   Edit `app_deploy_to_agentrun.py` to match your environment:
   - Update deployment name if needed
   - Adjust dependencies based on your agent requirements
   - The script creates an AgentScopeAgent automatically

2. **Run the deployment**:
   ```bash
   cd examples/deployments/agentrun_deploy
   python app_deploy_to_agentrun.py
   ```

3. **Choose deployment method**:
   The script provides three deployment options:
   - **Option 1**: Deploy using AgentApp (Recommended)
   - **Option 2**: Deploy directly from project directory
   - **Option 3**: Deploy from existing Wheel file

4. **Monitor the deployment**:
   The script will output:
   - Deployment ID and status
   - Wheel package path
   - OSS artifact URL
   - Resource name and AgentRuntime ID
   - AgentRun console URL for management

5. **Access the deployed service**:
   After successful deployment, access your agent through AgentRun:
   - Check deployment status in AgentRun console
   - Use provided API endpoints for testing

## API Endpoints

After successful deployment, the service provides the following endpoints through AgentRun:

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

Once deployed, you can test using the provided URLs from AgentRun:

Hint: AgentRun is session affinity, add X-Agentrun-Session-Id: <session-id> to the headers, the request will be bounded to a fixed instance

### Health Check
```bash
curl https://your-agentrun-url/health
```

### Synchronous Request
```bash
curl -X POST https://your-agentrun-url/sync \
  -H "Content-Type: application/json" \
  -H "X-Agentrun-Session-Id: 123" \
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

### Asynchronous Request
```bash
curl -X POST https://your-agentrun-url/async \
  -H "Content-Type: application/json" \
  -H "X-Agentrun-Session-Id: 123" \
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
curl -X POST https://your-agentrun-url/stream_async \
  -H "Content-Type: application/json" \
  -H "X-Agentrun-Session-Id: 123" \
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
# Alibaba Cloud Credentials
ALIBABA_CLOUD_ACCESS_KEY_ID="your-access-key-id"
ALIBABA_CLOUD_ACCESS_KEY_SECRET="your-access-key-secret"

# LLM Service
DASHSCOPE_API_KEY="your-dashscope-api-key"
```

### Optional Variables

#### Region and Endpoint
```bash
# Region Configuration (default: cn-hangzhou)
AGENT_RUN_REGION_ID="cn-hangzhou"

# Endpoint Configuration (default: agentrun.{region_id}.aliyuncs.com)
AGENT_RUN_ENDPOINT="agentrun.cn-hangzhou.aliyuncs.com"
```

#### OSS Credentials
```bash
# OSS-specific credentials (optional, fallback to Alibaba Cloud credentials)
OSS_ACCESS_KEY_ID="your-oss-access-key-id"
OSS_ACCESS_KEY_SECRET="your-oss-access-key-secret"
```

#### Network Configuration
```bash
# Network mode: PUBLIC/PRIVATE/PUBLIC_AND_PRIVATE (default: PUBLIC)
AGENT_RUN_NETWORK_MODE="PUBLIC"

# VPC Configuration (required if network_mode is PRIVATE or PUBLIC_AND_PRIVATE)
AGENT_RUN_VPC_ID="vpc-xxxxxx"
AGENT_RUN_SECURITY_GROUP_ID="sg-xxxxxx"
AGENT_RUN_VSWITCH_IDS='["vsw-xxxxxx", "vsw-yyyyyy"]'
```

#### Resource Configuration
```bash
# CPU allocation in cores (default: 2.0)
AGENT_RUN_CPU="2.0"

# Memory allocation in MB (default: 2048)
AGENT_RUN_MEMORY="2048"
```

#### Log Configuration
```bash
# If both log_store and log_project are provided, log_config will be created
AGENT_RUN_LOG_STORE="your-log-store-name"
AGENT_RUN_LOG_PROJECT="your-log-project-name"
```

#### Execution Configuration
```bash
# Execution role ARN (optional)
AGENT_RUN_EXECUTION_ROLE_ARN="acs:ram::xxxxx:role/your-role-name"

# Session concurrency limit (default: 1)
AGENT_RUN_SESSION_CONCURRENCY_LIMIT="1"

# Session idle timeout in seconds (default: 600)
AGENT_RUN_SESSION_IDLE_TIMEOUT_SECONDS="600"
```

## Troubleshooting

### Common Issues

1. **Missing Environment Variables**:
   The script will check for required variables and display missing ones:
   ```bash
   ❌ Missing required environment vars: ALIBABA_CLOUD_ACCESS_KEY_ID, ALIBABA_CLOUD_ACCESS_KEY_SECRET
   ```

2. **Authentication Issues**:
   Verify your Alibaba Cloud credentials have proper permissions:
   - AgentRun service access
   - OSS read/write permissions
   - DashScope API access

3. **Region Configuration**:
   Ensure your selected region supports AgentRun service. Common regions:
   - cn-hangzhou (default)
   - cn-shanghai
   - cn-beijing

4. **Network Connectivity**:
   - For PUBLIC mode: No additional configuration needed
   - For PRIVATE mode: Ensure VPC, security group, and vSwitch are properly configured
   - For PUBLIC_AND_PRIVATE mode: Both public and private endpoints will be available

5. **Resource Limits**:
   Ensure your account has sufficient quota for:
   - CPU cores (default: 2.0)
   - Memory (default: 2048 MB)
   - Check with Alibaba Cloud console for current limits

### Logs and Debugging

- Monitor deployment progress through script output
- Check AgentRun console for deployment status
- Review error messages for specific configuration issues
- Verify all required environment variables are set
- If log configuration is provided, check SLS logs for runtime issues

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

### Three Deployment Methods

#### Method 1: Deploy using AgentApp (Recommended)
```python
result = await agent_app.deploy(deployer, **deployment_config)
```
- Best for structured agent applications
- Automatic endpoint registration
- Built-in health checks and monitoring

#### Method 2: Deploy from Project Directory
```python
result = await deployer.deploy(
    project_dir=os.path.dirname(__file__),
    cmd="python agent_run.py",
    deploy_name="agent-app-project",
    telemetry_enabled=True,
)
```
- Deploy entire project directory
- Custom startup command
- Useful for complex projects with multiple files

#### Method 3: Deploy from Existing Wheel
```python
result = await deployer.deploy(
    external_whl_path="/path/to/your/agent-app.whl",
    deploy_name="agent-app-from-wheel",
    telemetry_enabled=True,
)
```
- Deploy pre-built wheel packages
- Fast deployment for tested artifacts
- Suitable for CI/CD pipelines

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

| Feature | Daemon | Detached Process | Kubernetes | AgentRun |
|---------|--------|------------------|------------|----------|
| Process Control | Blocking | Independent | Container | Serverless |
| Scalability | Single | Single Node | Multi-node | Auto-scaling |
| Resource Isolation | Process-level | Process-level | Container-level | Container-level |
| Management | Manual | API-based | Orchestrated | Fully-managed |
| Monitoring | Manual | Limited | Full | Built-in Dashboard |
| Cold Start | N/A | N/A | Fast | Optimized |
| Cost Model | Fixed | Fixed | Pay-per-use | Pay-per-request |
| Best For | Development | Production (single) | Enterprise | Serverless apps |

## Files Structure

- `app_deploy_to_agentrun.py`: Main deployment script with AgentApp and multiple endpoints
- `.env`: Environment variables configuration file (create from .env.example)
- `.env.example`: Template for environment variables

## Next Steps

After successful deployment:

1. **Access AgentRun Console**: Use the provided URL to manage your deployment
2. **Test API Endpoints**: Use the curl commands provided in the deployment output
3. **Configure Networking**: Set up VPC access if needed for private deployment
4. **Monitor Performance**: Use AgentRun's built-in monitoring and metrics
5. **Configure Logging**: Set up SLS log service for centralized logging
6. **Adjust Resources**: Modify CPU and memory allocation based on usage patterns
7. **Set Up Auto-scaling**: Configure session concurrency limits for optimal performance

## Additional Resources

- **AgentRun Console**: [https://functionai.console.aliyun.com/cn-hangzhou/agent/](https://functionai.console.aliyun.com/cn-hangzhou/agent/)
- **AgentScope Runtime**: [https://github.com/modelscope/agentscope](https://github.com/modelscope/agentscope)
- **DashScope API**: [https://dashscope.aliyun.com/](https://dashscope.aliyun.com/)

This example provides a complete workflow for deploying AgentScope Runtime agents to Alibaba Cloud AgentRun with serverless, production-ready configurations.

