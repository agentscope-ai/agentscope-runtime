# PAI Deployment Example

This example demonstrates how to deploy an agent to Alibaba Cloud PAI platform using the CLI.

## Prerequisites

1. Install required dependencies:
```bash
pip install alibabacloud-oss-v2 alibabacloud-pailangstudio20240710 alibabacloud-eas20210701
```

2. Set up environment variables:
```bash
export ALIBABA_CLOUD_ACCESS_KEY_ID="your-access-key-id"
export ALIBABA_CLOUD_ACCESS_KEY_SECRET="your-access-key-secret"
export PAI_WORKSPACE_ID="your-workspace-id"
export OSS_PATH="oss://your-bucket/your-path/"
export REGION_ID="cn-hangzhou"  # Optional, defaults to cn-hangzhou
```

## Deployment Methods

### Method 1: Deploy with CLI options

```bash
# Deploy a directory containing an agent
agentscope deploy pai ./my_agent_project \
  --name my-agent-service \
  --entrypoint app.py \
  --oss-path oss://my-bucket/agent-workspace/ \
  --workspace-id 12345 \
  --resource-type public \
  --instance-type ecs.c6.large \
  --enable-trace \
  --wait
```

### Method 2: Deploy with config file

```bash
# Deploy using a configuration file
agentscope deploy pai ./my_agent_project \
  --config pai_deploy_config.yaml
```

### Method 3: Deploy a single Python file

```bash
# Deploy a single Python file
agentscope deploy pai ./my_agent.py \
  --name my-agent-service \
  --oss-path oss://my-bucket/agent-workspace/ \
  --workspace-id 12345
```

## Advanced Options

### Using EAS Resource Group

```bash
agentscope deploy pai ./my_agent_project \
  --name my-agent-service \
  --resource-type eas_group \
  --resource-id eas-r-xxxxx \
  --cpu 4 \
  --memory 8192
```

### Using Quota Resource

```bash
agentscope deploy pai ./my_agent_project \
  --name my-agent-service \
  --resource-type quota \
  --quota-id quota-xxxxx \
  --cpu 4 \
  --memory 8192
```

### With Custom RAM Role

```bash
agentscope deploy pai ./my_agent_project \
  --name my-agent-service \
  --ram-role-mode custom \
  --ram-role-arn acs:ram::xxxxx:role/xxxxx
```

### With Environment Variables

```bash
agentscope deploy pai ./my_agent_project \
  --name my-agent-service \
  --env DASHSCOPE_API_KEY=sk-xxxx \
  --env MODEL_NAME=qwen-max \
  --env-file .env
```

### With Service Group

```bash
agentscope deploy pai ./my_agent_project \
  --name my-agent-service \
  --service-group my-service-group
```

### Without Auto Approval

```bash
# Deploy without auto approval (requires manual approval in console)
agentscope deploy pai ./my_agent_project \
  --name my-agent-service \
  --no-auto-approve
```

### Without Waiting

```bash
# Deploy without waiting for completion
agentscope deploy pai ./my_agent_project \
  --name my-agent-service \
  --no-wait
```

## Configuration File Format

See `pai_deploy_config.yaml` for a complete configuration example.

## Checking Deployment Status

After deployment, you can:

1. View the deployment in PAI console using the provided URL
2. Stop the deployment:
   ```bash
   agentscope stop <deployment-id>
   ```

3. List all deployments:
   ```bash
   agentscope list
   ```

## Resource Types

### Public Resource Pool
- Default option for most use cases
- Specify instance types using `--instance-type`
- Multiple instance types can be specified for fallback

### EAS Resource Group
- For dedicated resource groups
- Requires `--resource-id`
- Can specify `--cpu` and `--memory`

### Quota Resource
- For quota-based resource allocation
- Requires `--quota-id`
- Can specify `--cpu` and `--memory`

## Troubleshooting

### Missing Dependencies
If you see "PAI deployer is not available", install the required dependencies:
```bash
pip install alibabacloud-oss-v2 alibabacloud-pailangstudio20240710 alibabacloud-eas20210701
```

### Missing Configuration
Ensure all required environment variables are set:
- `ALIBABA_CLOUD_ACCESS_KEY_ID`
- `ALIBABA_CLOUD_ACCESS_KEY_SECRET`
- `PAI_WORKSPACE_ID` (or use `--workspace-id`)
- `OSS_PATH` (or use `--oss-path`)

### Region Configuration
If you're not in the cn-hangzhou region, set:
```bash
export REGION_ID="your-region"  # e.g., cn-beijing, cn-shanghai
```

