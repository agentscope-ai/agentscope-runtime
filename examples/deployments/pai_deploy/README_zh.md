# PAI 部署示例

本示例演示如何将 AgentScope agent 部署到 **阿里云 PAI (人工智能平台)**。

## 概述

PAI 部署允许您将 agent 部署为阿里云上的全托管服务。部署过程包括：

1. 打包项目并上传到 OSS（对象存储服务）
2. 创建 PAI LangStudio 项目和快照
3. 将快照部署为 EAS（弹性算法服务）服务

## 前置条件

### 1. 安装依赖

```bash
pip install 'agentscope-runtime[ext]'
```

### 2. 配置阿里云凭证

设置以下环境变量：

```bash
export ALIBABA_CLOUD_ACCESS_KEY_ID="your-access-key-id"
export ALIBABA_CLOUD_ACCESS_KEY_SECRET="your-access-key-secret"
```

可选配置：

```bash
export PAI_WORKSPACE_ID="your-workspace-id"
export REGION_ID="region-id-for-your-workspace"  # 或 ALIBABA_CLOUD_REGION_ID
```

### 3. PAI 工作空间

您需要一个 PAI 工作空间：

- 如果使用 RAM 用户账号，需要分配 PAI 开发者角色

- 需要配置 OSS 存储桶用于存储构建产物

- （可选）如果使用 DashScope 模型，需要配置可访问公网的 VPC

部署到 PAI EAS 的服务默认没有公网访问权限，如果使用 DashScope 模型，需要配置可访问公网的 VPC（<https://help.aliyun.com/zh/pai/user-guide/configure-network-connectivity>）。

## 项目结构

```

pai_deploy/
├── README.md                # 英文文档
├── README_zh.md             # 本文档
├── deploy_config.yaml       # 部署配置文件
└── my_agent/                # 示例 agent 项目
    └── agent.py             # Agent 实现

```

## 示例 Agent

`my_agent/agent.py` 演示了一个简单的 ReActAgent，包含：

- 工具集成（天气查询、Python 代码执行）
- 有状态的对话管理
- 流式响应支持

```python
from agentscope_runtime.engine import AgentApp

agent_app = AgentApp(
    app_name="SimpleAgent",
    app_description="A helpful assistant",
)

@agent_app.query(framework="agentscope")
async def query_func(runner, msgs, request, **kwargs):
    # 您的 agent 逻辑
    ...
```

## 配置

### 配置文件

参见本目录下的 `deploy_config.yaml`：

```yaml
context:
  workspace_id: "your-workspace-id"
  region: "cn-hangzhou"

spec:
  name: "my_agent_service"
  code:
    # 相对于配置文件位置的路径
    source_dir: "my_agent"
    entrypoint: "agent.py"
  resources:
    type: "public"
    instance_type: "ecs.c6.large"
    instance_count: 1
  env:
    DASHSCOPE_API_KEY: "your-dashscope-api-key"
```

> **注意**：`code.source_dir` 是相对于配置文件位置的路径。

### 配置结构

| 配置项 | 说明 |
|--------|------|
| `context` | 部署目标（工作空间、地域、存储） |
| `spec.name` | 服务名称（必填） |
| `spec.code` | 源代码目录和入口文件 |
| `spec.resources` | 资源配置 |
| `spec.vpc_config` | VPC 网络配置（可选） |
| `spec.identity` | RAM 角色配置（可选） |
| `spec.observability` | 链路追踪设置 |
| `spec.env` | 环境变量 |
| `spec.tags` | 部署标签 |

## 部署

### 方式一：使用配置文件（推荐）

```bash
# 进入示例目录
cd examples/deployments/pai_deploy

# 使用配置文件部署
agentscope deploy pai --config deploy_config.yaml

# 使用配置文件并覆盖部分参数
agentscope deploy pai --config deploy_config.yaml --name new-service-name
```

### 方式二：仅使用 CLI 参数

```bash
agentscope deploy pai ./my_agent \
  --name my-service \
  --workspace-id 12345 \
  --region cn-hangzhou \
  --instance-type ecs.c6.large \
  --env DASHSCOPE_API_KEY=your-key
```

### 完整 CLI 选项

```bash
agentscope deploy pai [SOURCE] [OPTIONS]

参数:
  SOURCE                  源代码目录或文件（使用配置文件时可选）

选项:
  --config, -c PATH       部署配置文件路径 (.yaml)
  --name TEXT             服务名称（必填）
  --workspace-id TEXT     PAI 工作空间 ID
  --region TEXT           地域 ID（如 cn-hangzhou）
  --entrypoint TEXT       入口文件（默认：app.py, agent.py, main.py）
  --oss-path TEXT         OSS 工作目录
  --instance-type TEXT    实例类型（公共资源池模式）
  --instance-count INT    实例数量
  --resource-id TEXT      EAS 资源组 ID（资源组模式）
  --quota-id TEXT         PAI 配额 ID（配额模式）
  --cpu INT               CPU 核数
  --memory INT            内存大小（MB）
  --service-group TEXT    服务组名称
  --resource-type TEXT    资源类型：public, resource, quota
  --vpc-id TEXT           VPC ID
  --vswitch-id TEXT       交换机 ID
  --security-group-id TEXT  安全组 ID
  --ram-role-arn TEXT     RAM 角色 ARN
  --enable-trace/--no-trace  启用/禁用链路追踪
  --wait/--no-wait        等待部署完成
  --timeout INT           部署超时时间（秒）
  --auto-approve/--no-auto-approve  自动审批部署
  --env, -E TEXT          环境变量（KEY=VALUE，可重复）
  --env-file PATH         .env 文件路径
  --tag, -T TEXT          标签（KEY=VALUE，可重复）
```

## 资源类型

PAI 支持三种资源类型：

### 1. 公共资源池 (`type: "public"`)

部署到共享 ECS 实例：

```yaml
spec:
  resources:
    type: "public"
    instance_type: "ecs.c6.large"  # 必填
    instance_count: 1
```

### 2. 专属资源组 (`type: "resource"`)

部署到专属 EAS 资源组：

```yaml
spec:
  resources:
    type: "resource"
    resource_id: "eas-r-xxxxx"  # 必填
    cpu: 2
    memory: 4096
```

### 3. 配额模式 (`type: "quota"`)

使用 PAI 配额部署：

```yaml
spec:
  resources:
    type: "quota"
    quota_id: "quota-xxxxxxxx"  # 必填
    cpu: 2
    memory: 4096
```

## VPC 配置

私有网络部署配置：

```yaml
spec:
  vpc_config:
    vpc_id: "vpc-xxxxx"
    vswitch_id: "vsw-xxxxx"
    security_group_id: "sg-xxxxx"
```

## 环境变量

### 注入环境变量

方式一：在配置文件中

```yaml
spec:
  env:
    DASHSCOPE_API_KEY: "your-key"
    MY_CONFIG: "value"
```

方式二：通过 CLI

```bash
agentscope deploy pai ./my_agent \
  --env DASHSCOPE_API_KEY=your-key \
  --env MY_CONFIG=value
```

方式三：使用 .env 文件

```bash
agentscope deploy pai ./my_agent --env-file .env
```

### 自动生成的标签

以下标签会自动添加：

- `deployed-by: agentscope-runtime`
- `client-version: <版本号>`
- `deploy-method: cli`

## 管理部署

### 停止部署

```bash
agentscope stop <deploy-id>
```

### 查看部署状态

访问部署后提供的 PAI 控制台 URL。

## 故障排查

### 常见问题

1. **"PAI deployer is not available"**

   ```bash
   pip install 'agentscope-runtime[ext]'
   ```

2. **"Workspace ID is required"**
   - 设置 `PAI_WORKSPACE_ID` 环境变量，或
   - 使用 `--workspace-id` CLI 选项，或
   - 在配置文件中添加 `context.workspace_id`

3. **"Service name is owned by another user"**
   - 选择不同的服务名称（必须在地域内唯一）

4. **凭证错误**
   - 验证 `ALIBABA_CLOUD_ACCESS_KEY_ID` 和 `ALIBABA_CLOUD_ACCESS_KEY_SECRET`
   - 检查 RAM 权限是否包含 PAI/EAS/OSS 访问权限

5. **OSS 上传失败**
   - 确保 OSS 存储桶存在且可访问
   - 检查工作空间和 OSS 存储桶的地域是否一致

## 示例命令

```bash
# 先进入示例目录
cd examples/deployments/pai_deploy

# 使用配置文件部署
agentscope deploy pai --config deploy_config.yaml

# 不使用配置文件的简单部署
agentscope deploy pai ./my_agent --name my-service --workspace-id 12345

# 使用环境变量文件
agentscope deploy pai ./my_agent --name my-service \
  --workspace-id 12345 \
  --env-file .env

# 自定义资源配置
agentscope deploy pai ./my_agent --name my-service \
  --workspace-id 12345 \
  --resource-type quota \
  --quota-id quota-xxx \
  --cpu 4 \
  --memory 8192

# VPC 配置
agentscope deploy pai ./my_agent --name my-service \
  --workspace-id 12345 \
  --vpc-id vpc-xxx \
  --vswitch-id vsw-xxx \
  --security-group-id sg-xxx

# 手动审批流程
agentscope deploy pai --config deploy_config.yaml --no-auto-approve
```
