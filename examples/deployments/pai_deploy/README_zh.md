# PAI 平台部署支持 - 中文说明

## 概述
已成功在 CLI 中添加对阿里云 PAI (Platform for AI) 平台的部署支持。

## 实现内容

### 1. CLI 命令实现

在 `src/agentscope_runtime/cli/commands/deploy.py` 中新增了 `pai` 子命令，提供完整的 PAI 部署功能。

### 2. 命令使用方法

**基本语法：**
```bash
agentscope deploy pai SOURCE [OPTIONS]
```

**SOURCE** 可以是：
- Python 文件（如：`agent.py`）
- 包含 agent 的项目目录

### 3. 主要选项

#### 必需选项：
- `--name`: 服务名称（必填）

#### 核心配置：
- `--oss-path`: OSS 工作目录路径（如：oss://bucket-name/path/）
- `--workspace-id`: PAI 工作空间 ID
- `--entrypoint`: 入口文件名（对于目录部署）

#### 资源配置：
- `--resource-type`: 资源类型（public/eas_group/quota）
- `--instance-count`: 实例数量（默认：1）
- `--instance-type`: 实例类型（可重复指定）
- `--cpu`: CPU 核心数
- `--memory`: 内存（MB）

#### 部署控制：
- `--enable-trace/--no-trace`: 启用/禁用追踪（默认：启用）
- `--wait/--no-wait`: 等待部署完成（默认：等待）
- `--auto-approve/--no-auto-approve`: 自动批准部署（默认：自动）

#### 环境配置：
- `-E, --env`: 环境变量（KEY=VALUE 格式，可重复）
- `--env-file`: 环境变量配置文件路径
- `-c, --config`: 部署配置文件路径（.json/.yaml/.yml）

## 环境变量

### 必需的环境变量：
```bash
export ALIBABA_CLOUD_ACCESS_KEY_ID="your-access-key-id"
export ALIBABA_CLOUD_ACCESS_KEY_SECRET="your-access-key-secret"
export PAI_WORKSPACE_ID="your-workspace-id"
export OSS_PATH="oss://your-bucket/your-path/"
```

### 可选的环境变量：
```bash
export REGION_ID="cn-hangzhou"  # 默认：cn-hangzhou
```

## 使用示例

### 示例 1: 基本部署
```bash
agentscope deploy pai ./my_agent \
  --name my-service \
  --oss-path oss://my-bucket/agent-workspace/ \
  --workspace-id 12345
```

### 示例 2: 使用配置文件
```bash
agentscope deploy pai ./my_agent \
  --config examples/deployments/pai_deploy_config.yaml
```

### 示例 3: 部署单个文件
```bash
agentscope deploy pai ./agent.py \
  --name my-service \
  --oss-path oss://my-bucket/workspace/
```

### 示例 4: 使用 EAS 资源组
```bash
agentscope deploy pai ./my_agent \
  --name my-service \
  --resource-type eas_group \
  --resource-id eas-r-xxxxx \
  --cpu 4 \
  --memory 8192
```

### 示例 5: 带环境变量
```bash
agentscope deploy pai ./my_agent \
  --name my-service \
  --env DASHSCOPE_API_KEY=sk-xxx \
  --env MODEL_NAME=qwen-max \
  --env-file .env
```

## 资源类型说明

### 1. Public（公共资源池）
- 默认选项，适合大多数场景
- 使用 `--instance-type` 指定实例类型
- 可指定多个实例类型作为后备选择

```bash
--resource-type public \
--instance-type ecs.c6.large \
--instance-type ecs.c6.xlarge
```

### 2. EAS Group（专属资源组）
- 适用于有专属资源组的场景
- 需要 `--resource-id` 参数
- 可指定 `--cpu` 和 `--memory`

```bash
--resource-type eas_group \
--resource-id eas-r-xxxxx \
--cpu 2 \
--memory 4096
```

### 3. Quota（配额资源）
- 基于配额的资源分配
- 需要 `--quota-id` 参数
- 可指定 `--cpu` 和 `--memory`

```bash
--resource-type quota \
--quota-id quota-xxxxx \
--cpu 2 \
--memory 4096
```

## 配置文件示例

参见 `examples/deployments/pai_deploy_config.yaml` 获取完整的配置示例。

配置文件可以包含所有的部署参数，CLI 选项会覆盖配置文件中的值。

## 查看和管理部署

### 查看部署列表：
```bash
agentscope list
```

### 停止部署：
```bash
agentscope stop <deployment-id>
```

### 查看部署状态：
```bash
agentscope status <deployment-id>
```

## 依赖安装

PAI 部署需要以下 Python 包：
```bash
pip install alibabacloud-oss-v2 \
            alibabacloud-pailangstudio20240710 \
            alibabacloud-eas20210701
```

如果缺少依赖，CLI 会提供清晰的安装提示。

## 查看帮助

查看 PAI 部署的完整帮助信息：
```bash
agentscope deploy pai --help
```

查看所有部署平台：
```bash
agentscope deploy --help
```

## 文档和示例

- **配置示例**: `examples/deployments/pai_deploy_config.yaml`
- **详细文档**: `examples/deployments/pai_deploy/README.md`
- **Agent 示例**: `examples/deployments/pai_deploy/simple_agent.py`
- **实现总结**: `examples/deployments/pai_deploy/IMPLEMENTATION_SUMMARY.md`

## 故障排除

### 问题：找不到 PAI deployer
**解决**：安装所需依赖
```bash
pip install alibabacloud-oss-v2 alibabacloud-pailangstudio20240710 alibabacloud-eas20210701
```

### 问题：缺少必需的配置
**解决**：确保设置了所有必需的环境变量
```bash
export ALIBABA_CLOUD_ACCESS_KEY_ID="..."
export ALIBABA_CLOUD_ACCESS_KEY_SECRET="..."
export PAI_WORKSPACE_ID="..."
export OSS_PATH="oss://..."
```

### 问题：区域配置错误
**解决**：如果不在杭州区域，设置 REGION_ID
```bash
export REGION_ID="cn-beijing"  # 或其他区域
```

## 功能特性

✅ 支持单文件和目录部署  
✅ 支持三种资源类型（public/eas_group/quota）  
✅ 支持配置文件和命令行选项  
✅ 支持环境变量配置  
✅ 自动打包和上传到 OSS  
✅ 自动创建快照和部署  
✅ 可选的部署等待和自动批准  
✅ 完整的错误处理和用户反馈  
✅ 与现有部署状态管理集成  
✅ 一致的 CLI 用户体验  

## 与其他平台对比

PAI 部署命令与其他部署平台（local、modelstudio、agentrun、k8s）保持一致的设计：
- 相同的参数命名约定
- 相同的配置文件格式支持
- 相同的环境变量处理方式
- 相同的错误处理模式
- 相同的状态管理机制

