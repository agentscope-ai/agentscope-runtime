# FC Deployment Example

This example demonstrates how to deploy an AgentScope Runtime agent to Alibaba Cloud Function Compute (FC) using the built-in FC deployer.

## Overview

The `app_deploy_to_fc.py` script shows how to:
- Configure OSS (Object Storage Service) for storing deployment artifacts
- Set up FC connection and configuration
- Deploy an LLM agent to Alibaba Cloud Function Compute
- Package and upload the agent application
- Access the deployed service through FC HTTP trigger

## Prerequisites

Before running this example, ensure you have:

1. **Alibaba Cloud Account**: Active Alibaba Cloud account with Function Compute service enabled
2. **API Keys**: Required Alibaba Cloud credentials and DashScope API key
3. **Python environment**: Python 3.10+ with agentscope-runtime installed
4. **OSS Access**: Access to Alibaba Cloud Object Storage Service
5. **Docker**: Docker Desktop installed for building deployment packages

## Setup

1. **Install dependencies**:
   ```bash
   pip install "agentscope-runtime[ext]>=1.0.0"
   ```

2. **Set environment variables**:
   ```bash
   # Required: Alibaba Cloud Credentials
   export ALIBABA_CLOUD_ACCESS_KEY_ID="your-access-key-id"
   export ALIBABA_CLOUD_ACCESS_KEY_SECRET="your-access-key-secret"

   # Required: FC Account ID
   export FC_ACCOUNT_ID="your-fc-account-id"

   # Required: LLM API Key
   export DASHSCOPE_API_KEY="your-dashscope-api-key"

   # Optional: Region Configuration (default: cn-hangzhou)
   export FC_REGION_ID="cn-hangzhou"

   # Optional: OSS Configuration
   export OSS_REGION="cn-hangzhou"
   export OSS_BUCKET_NAME="tmp-fc-deploy"

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
    region=os.environ.get("OSS_REGION", "cn-hangzhou"),
    bucket_name=os.environ.get("OSS_BUCKET_NAME", "tmp-fc-deploy"),
)
```

- **OSS credentials**: Optional specific OSS credentials, falls back to Alibaba Cloud credentials
- **Automatic fallback**: Uses main Alibaba Cloud credentials if OSS-specific ones aren't provided

### FC Configuration

```python
fc_config = FCConfig(
    access_key_id=os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_ID"),
    access_key_secret=os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_SECRET"),
    account_id=os.environ.get("FC_ACCOUNT_ID"),
    region_id=os.environ.get("FC_REGION_ID", "cn-hangzhou"),
)
```

- **`access_key_id/secret`**: Alibaba Cloud credentials for FC API access
- **`account_id`**: Your Alibaba Cloud account ID for FC
- **`region_id`**: Alibaba Cloud region (default: cn-hangzhou)

### VPC Configuration

```python
# VPC Configuration (optional, for private network deployment)
vpc_id = os.environ.get("FC_VPC_ID")
security_group_id = os.environ.get("FC_SECURITY_GROUP_ID")
vswitch_ids = os.environ.get("FC_VSWITCH_IDS")  # JSON array format
```

- **`vpc_id`**: VPC identifier for private network deployment
- **`security_group_id`**: Security group for network access control
- **`vswitch_ids`**: List of vSwitch IDs for high availability

### Resource Configuration

```python
# CPU and Memory allocation
cpu = float(os.environ.get("FC_CPU", "2.0"))  # in cores
memory = int(os.environ.get("FC_MEMORY", "2048"))  # in MB
disk = int(os.environ.get("FC_DISK", "512"))  # in MB
```

- **`cpu`**: CPU cores allocated to the function (default: 2.0)
- **`memory`**: Memory in MB allocated to the function (default: 2048)
- **`disk`**: Disk size in MB allocated to the function (default: 512)

### Log Configuration

```python
# Optional log configuration
log_store = os.environ.get("FC_LOG_STORE")
log_project = os.environ.get("FC_LOG_PROJECT")
```

- **`log_store`**: SLS log store name for application logs
- **`log_project`**: SLS log project name for log management

### Session Configuration

```python
# Session settings
session_concurrency_limit = int(os.environ.get("FC_SESSION_CONCURRENCY_LIMIT", "200"))
session_idle_timeout_seconds = int(os.environ.get("FC_SESSION_IDLE_TIMEOUT_SECONDS", "3600"))
```

- **`session_concurrency_limit`**: Maximum concurrent sessions per instance (default: 200)
- **`session_idle_timeout_seconds`**: Session idle timeout in seconds (default: 3600)

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
- **`deploy_name`**: Name for the FC function
- **`telemetry_enabled`**: Enable telemetry and monitoring

#### Dependencies Configuration
- **`requirements`**: Python packages to install
- **`extra_packages`**: Additional local Python files to include

#### Environment Variables
- **Runtime environment**: Configuration injected into the deployed function

## Running the Deployment

1. **Customize the configuration**:
   Edit `app_deploy_to_fc.py` to match your environment:
   - Update deployment name if needed
   - Adjust dependencies based on your agent requirements
   - The script creates an AgentScopeAgent automatically

2. **Run the deployment**:
   ```bash
   cd examples/deployments/fc_deploy
   python app_deploy_to_fc.py
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
   - Resource name and Function Name
   - FC console URL for management
   - Endpoint URL for API access

5. **Access the deployed service**:
   After successful deployment, access your agent through FC HTTP trigger:
   - Check deployment status in FC console
   - Use provided API endpoints for testing

## API Endpoints

After successful deployment, the service provides the following endpoints through FC HTTP trigger:

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

Once deployed, you can test using the provided URLs from FC:

**Hint**: FC supports session affinity. Add `x-agentscope-runtime-session-id: <session-id>` to the headers, and the request will be routed to a fixed instance.

### Health Check
```bash
curl https://your-fc-endpoint-url/health
```

### Synchronous Request
```bash
curl -X POST https://your-fc-endpoint-url/sync \
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
```

### Asynchronous Request
```bash
curl -X POST https://your-fc-endpoint-url/async \
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
```

### Streaming Request
```bash
curl -X POST https://your-fc-endpoint-url/stream_async \
  -H "Content-Type: application/json" \
  -H "x-agentscope-runtime-session-id: 123" \
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

# FC Account ID
FC_ACCOUNT_ID="your-fc-account-id"

# LLM Service
DASHSCOPE_API_KEY="your-dashscope-api-key"
```

### Optional Variables

#### Region Configuration
```bash
# FC Region (default: cn-hangzhou)
FC_REGION_ID="cn-hangzhou"
```

#### OSS Configuration
```bash
# OSS Region (default: cn-hangzhou)
OSS_REGION="cn-hangzhou"

# OSS Bucket Name
OSS_BUCKET_NAME="tmp-fc-deploy"

# OSS-specific credentials (optional, fallback to Alibaba Cloud credentials)
OSS_ACCESS_KEY_ID="your-oss-access-key-id"
OSS_ACCESS_KEY_SECRET="your-oss-access-key-secret"
```

#### VPC Configuration
```bash
# VPC Configuration (optional, for private network deployment)
FC_VPC_ID="vpc-xxxxxx"
FC_SECURITY_GROUP_ID="sg-xxxxxx"
FC_VSWITCH_IDS='["vsw-xxxxxx", "vsw-yyyyyy"]'
```

#### Resource Configuration
```bash
# CPU allocation in cores (default: 2.0)
FC_CPU="2.0"

# Memory allocation in MB (default: 2048)
FC_MEMORY="2048"

# Disk allocation in MB (default: 512)
FC_DISK="512"
```

#### Log Configuration
```bash
# If both log_store and log_project are provided, log_config will be created
FC_LOG_STORE="your-log-store-name"
FC_LOG_PROJECT="your-log-project-name"
```

#### Session Configuration
```bash
# Session concurrency limit per instance (default: 200)
FC_SESSION_CONCURRENCY_LIMIT="200"

# Session idle timeout in seconds (default: 3600)
FC_SESSION_IDLE_TIMEOUT_SECONDS="3600"
```

#### Execution Configuration
```bash
# Execution role ARN (optional)
FC_EXECUTION_ROLE_ARN="acs:ram::xxxxx:role/your-role-name"
```

## Troubleshooting

### Common Issues

1. **Missing Environment Variables**:
   The script will check for required variables and display missing ones:
   ```bash
   ❌ Missing required environment vars: ALIBABA_CLOUD_ACCESS_KEY_ID, FC_ACCOUNT_ID
   ```

2. **Docker Not Available**:
   FC deployment requires Docker for building packages:
   ```bash
   Docker is required for building. Install Docker Desktop: https://www.docker.com/products/docker-desktop
   ```

3. **Authentication Issues**:
   Verify your Alibaba Cloud credentials have proper permissions:
   - Function Compute service access
   - OSS read/write permissions
   - DashScope API access

4. **Region Configuration**:
   Ensure your selected region supports FC service. Common regions:
   - cn-hangzhou (default)
   - cn-shanghai
   - cn-beijing
   - cn-shenzhen

5. **Resource Limits**:
   Ensure your account has sufficient quota for:
   - CPU cores (default: 2.0)
   - Memory (default: 2048 MB)
   - Check with Alibaba Cloud console for current limits

### Logs and Debugging

- Monitor deployment progress through script output
- Check FC console for function status
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

| Feature | Daemon | Detached Process | Kubernetes | FC |
|---------|--------|------------------|------------|-----|
| Process Control | Blocking | Independent | Container | Serverless |
| Scalability | Single | Single Node | Multi-node | Auto-scaling |
| Resource Isolation | Process-level | Process-level | Container-level | Function-level |
| Management | Manual | API-based | Orchestrated | Fully-managed |
| Monitoring | Manual | Limited | Full | Built-in Dashboard |
| Cold Start | N/A | N/A | Fast | Optimized |
| Cost Model | Fixed | Fixed | Pay-per-use | Pay-per-request |
| Best For | Development | Production (single) | Enterprise | Serverless apps |

## Files Structure

- `app_deploy_to_fc.py`: Main deployment script with AgentApp and multiple endpoints
- `.env`: Environment variables configuration file (create from .env.example)
- `.env.example`: Template for environment variables
- `others/`: Additional project files to include in deployment

## Next Steps

After successful deployment:

1. **Access FC Console**: Use the provided URL to manage your function
2. **Test API Endpoints**: Use the curl commands provided in the deployment output
3. **Configure VPC**: Set up VPC access if needed for private deployment
4. **Monitor Performance**: Use FC's built-in monitoring and metrics
5. **Configure Logging**: Set up SLS log service for centralized logging
6. **Adjust Resources**: Modify CPU, memory, and disk allocation based on usage patterns
7. **Set Up Session Affinity**: Configure session settings for optimal performance

## Additional Resources

- **FC Console**: [https://fcnext.console.aliyun.com/](https://fcnext.console.aliyun.com/)
- **AgentScope Runtime**: [https://github.com/agentscope-ai/agentscope-runtime](https://github.com/agentscope-ai/agentscope-runtime)
- **DashScope API**: [https://dashscope.aliyun.com/](https://dashscope.aliyun.com/)

This example provides a complete workflow for deploying AgentScope Runtime agents to Alibaba Cloud Function Compute with serverless, production-ready configurations.
