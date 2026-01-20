# PAI Deployment Example

This example demonstrates how to deploy an AgentScope agent to **Alibaba Cloud PAI (Platform for AI)**.

## Overview

PAI Deployment allows you to deploy your agent as a fully managed service on Alibaba Cloud. The deployment process:

1. Packages your project and uploads it to OSS (Object Storage Service)
2. Creates a PAI LangStudio project and snapshot
3. Deploys the snapshot as an EAS (Elastic Algorithm Service) service

## Prerequisites

### 1. Install Dependencies

```bash
pip install 'agentscope-runtime[ext]'
```

### 2. Configure Alibaba Cloud Credentials

Set the following environment variables:

```bash
export ALIBABA_CLOUD_ACCESS_KEY_ID="your-access-key-id"
export ALIBABA_CLOUD_ACCESS_KEY_SECRET="your-access-key-secret"
```

Optionally, you can also set:

```bash
export PAI_WORKSPACE_ID="your-workspace-id"
export REGION_ID="region-id-for-your-workspace"  # or ALIBABA_CLOUD_REGION_ID
```

### 3. PAI Workspace

You need a PAI workspace:

- Should have PAI Developer Role assigned if using a RAM User Account

- Should have OSS bucket for storing build artifacts

- (Optional) Has a VPC that has public network access if using DashScope models

The service deploy to PAI EAS has no public network access, so you need to use a VPC that has public network access if using DashScope models (<https://help.aliyun.com/zh/pai/user-guide/configure-network-connectivity>).

## Project Structure

```
pai_deploy/
├── README.md                # This file
├── README_zh.md             # Chinese version
├── deploy_config.yaml       # Deployment configuration
└── my_agent/                # Example agent project
    └── agent.py             # Agent implementation
```

## Example Agent

The `my_agent/agent.py` demonstrates a simple ReActAgent with:

- Tool integration (weather query, Python code execution)
- Stateful conversation management
- Streaming response support

```python
from agentscope_runtime.engine import AgentApp

agent_app = AgentApp(
    app_name="SimpleAgent",
    app_description="A helpful assistant",
)

@agent_app.query(framework="agentscope")
async def query_func(runner, msgs, request, **kwargs):
    # Your agent logic here
    ...
```

## Configuration

### Configuration File

See `deploy_config.yaml` in this directory:

```yaml
context:
  workspace_id: "your-workspace-id"
  region: "cn-hangzhou"

spec:
  name: "my_agent_service"
  code:
    # Path relative to config file location
    source_dir: "my_agent"
    entrypoint: "agent.py"
  resources:
    type: "public"
    instance_type: "ecs.c6.large"
    instance_count: 1
  env:
    DASHSCOPE_API_KEY: "your-dashscope-api-key"
```

> **Note**: The `code.source_dir` is resolved relative to the config file's location.

### Configuration Structure

| Section | Description |
|---------|-------------|
| `context` | Where to deploy (workspace, region, storage) |
| `spec.name` | Service name (required) |
| `spec.code` | Source directory and entrypoint |
| `spec.resources` | Resource allocation settings |
| `spec.vpc_config` | VPC networking (optional) |
| `spec.identity` | RAM role configuration (optional) |
| `spec.observability` | Tracing settings |
| `spec.env` | Environment variables |
| `spec.tags` | Custom tags for the deployment |

## Deployment

### Method 1: Using Configuration File (Recommended)

```bash
# Navigate to example directory
cd examples/deployments/pai_deploy

# Deploy using config file
agentscope deploy pai --config deploy_config.yaml

# Deploy with CLI overrides
agentscope deploy pai --config deploy_config.yaml --name new-service-name
```

### Method 2: Using CLI Only

```bash
agentscope deploy pai ./my_agent \
  --name my-service \
  --workspace-id 12345 \
  --region cn-hangzhou \
  --instance-type ecs.c6.large \
  --env DASHSCOPE_API_KEY=your-key
```

### Full CLI Options

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

## Resource Types

PAI supports three resource types:

### 1. Public Resource Pool (`type: "public"`)

Deploy on shared ECS instances:

```yaml
spec:
  resources:
    type: "public"
    instance_type: "ecs.c6.large"  # Required
    instance_count: 1
```

### 2. Dedicated Resource Group (`type: "resource"`)

Deploy on dedicated EAS resource group:

```yaml
spec:
  resources:
    type: "resource"
    resource_id: "eas-r-xxxxx"  # Required
    cpu: 2
    memory: 4096
```

### 3. Quota-based (`type: "quota"`)

Deploy using PAI quota:

```yaml
spec:
  resources:
    type: "quota"
    quota_id: "quota-xxxxxxxx"  # Required
    cpu: 2
    memory: 4096
```

## VPC Configuration

For private network deployment:

```yaml
spec:
  vpc_config:
    vpc_id: "vpc-xxxxx"
    vswitch_id: "vsw-xxxxx"
    security_group_id: "sg-xxxxx"
```

## Environment Variables

### Injecting Environment Variables

Method 1: In configuration file

```yaml
spec:
  env:
    DASHSCOPE_API_KEY: "your-key"
    MY_CONFIG: "value"
```

Method 2: Via CLI

```bash
agentscope deploy pai ./my_agent \
  --env DASHSCOPE_API_KEY=your-key \
  --env MY_CONFIG=value
```

Method 3: Using .env file

```bash
agentscope deploy pai ./my_agent --env-file .env
```

### Auto-Generated Tags

The following tags are automatically added:

- `deployed-by: agentscope-runtime`
- `client-version: <version>`
- `deploy-method: cli`

## Managing Deployments

### Stop a Deployment

```bash
agentscope stop <deploy-id>
```

### View Deployment Status

Check the PAI console URL provided after deployment.

## Troubleshooting

### Common Issues

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

## Example Commands

```bash
# Navigate to example directory first
cd examples/deployments/pai_deploy

# Deploy using config file
agentscope deploy pai --config deploy_config.yaml

# Simple deployment without config file
agentscope deploy pai ./my_agent --name my-service --workspace-id 12345

# With environment variables from file
agentscope deploy pai ./my_agent --name my-service \
  --workspace-id 12345 \
  --env-file .env

# With custom resources
agentscope deploy pai ./my_agent --name my-service \
  --workspace-id 12345 \
  --resource-type quota \
  --quota-id quota-xxx \
  --cpu 4 \
  --memory 8192

# With VPC configuration
agentscope deploy pai ./my_agent --name my-service \
  --workspace-id 12345 \
  --vpc-id vpc-xxx \
  --vswitch-id vsw-xxx \
  --security-group-id sg-xxx

# Manual approval workflow
agentscope deploy pai --config deploy_config.yaml --no-auto-approve
```
