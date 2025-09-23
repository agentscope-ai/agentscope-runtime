# Kubernetes 部署示例

此示例演示如何使用内置的 Kubernetes 部署器将 AgentScope Runtime 智能体部署到 Kubernetes。

## 概述

`deploy_to_k8s.py` 脚本展示了如何：
- 配置容器镜像仓库以存储 Docker 镜像
- 设置 Kubernetes 连接和命名空间
- 部署具有适当资源管理的 LLM 智能体
- 测试已部署的服务
- 使用后清理资源

## 前置条件

运行此示例之前，请确保具备：

1. **Kubernetes 集群访问权限**：配置了 kubectl 的运行中的 Kubernetes 集群
2. **容器镜像仓库访问权限**：对容器镜像仓库的访问权限（Docker Hub、ACR 等）
3. **Python 环境**：已安装 agentscope-runtime 的 Python 3.10+
4. **API 密钥**：LLM 提供商所需的 API 密钥（例如 Qwen 的 DASHSCOPE_API_KEY）

## 设置

1. **安装依赖项**：
   ```bash
   pip install agentscope-runtime==0.1.5b1
   pip install "agentscope-runtime[deployment]==0.1.5b1"

   ```

2. **设置环境变量**：
   ```bash
   export DASHSCOPE_API_KEY="your-api-key"
   ```

3. **配置 Kubernetes 访问**：
   确保您的 `kubeconfig` 已正确配置：
   ```bash
   kubectl cluster-info
   ```

## 配置参数

### 镜像仓库配置

```python
registry_config = RegistryConfig(
    registry_url="your-resigstry-url",
    namespace="your-namespace",
)
```

- **`registry_url`**: Docker 镜像将推送到的容器镜像仓库 URL
  - 示例: `docker.io`, `gcr.io/project-id`, `your-registry.com`
- **`namespace`**: 镜像仓库内用于组织镜像的命名空间/仓库

### Kubernetes 配置

```python
k8s_config = K8sConfig(
    k8s_namespace="agentscope-runtime",
    kubeconfig_path="your-kubeconfig-local-path",
)
```

- **`k8s_namespace`**: 资源将部署到的 Kubernetes 命名空间
  - 如果命名空间不存在则会创建
- **`kubeconfig_path`**: kubeconfig 文件路径（None 使用默认的 kubectl 配置，需要本地运行 kubectl）

### 运行时配置

```python
runtime_config = {
    "resources": {
        "requests": {"cpu": "200m", "memory": "512Mi"},
        "limits": {"cpu": "1000m", "memory": "2Gi"},
    },
    "image_pull_policy": "IfNotPresent",
    # 可选配置:
    # "node_selector": {"node-type": "gpu"},
    # "tolerations": [...]
}
```

#### 资源管理
- **`requests`**: 容器的保证资源
  - `cpu`: CPU 单位（200m = 0.2 CPU 核心）
  - `memory`: 内存分配（512Mi = 512 兆字节）
- **`limits`**: 容器可以使用的最大资源
  - `cpu`: 最大 CPU（1000m = 1 CPU 核心）
  - `memory`: 最大内存（2Gi = 2 千兆字节）

#### 镜像拉取策略
- **`IfNotPresent`**: 仅在本地不存在镜像时拉取
- **`Always`**: 始终拉取最新镜像
- **`Never`**: 从不拉取镜像（仅使用本地）

#### 可选配置
- **`node_selector`**: 在具有匹配标签的特定节点上调度 Pod
- **`tolerations`**: 允许 Pod 在具有匹配污点的节点上运行

### 部署配置

```python
deployment_config = {
    # 基本设置
    "api_endpoint": "/process",
    "stream": True,
    "port": "8080",
    "replicas": 1,
    "image_tag": "linux-amd64",
    "image_name": "agent_llm",

    # 依赖项
    "requirements": [
        "agentscope",
        "fastapi",
        "uvicorn",
        "langgraph",
    ],
    "extra_packages": [
        os.path.join(os.path.dirname(__file__), "others", "other_project.py"),
    ],
    "base_image": "python:3.10-slim-bookworm",

    # 环境
    "environment": {
        "PYTHONPATH": "/app",
        "LOG_LEVEL": "INFO",
        "DASHSCOPE_API_KEY": os.environ.get("DASHSCOPE_API_KEY"),
    },

    # 部署设置
    "runtime_config": runtime_config,
    "deploy_timeout": 300,
    "health_check": True,
    "platform": "linux/amd64",
    "push_to_registry": True,
}
```

#### 基本配置
- **`api_endpoint`**: 智能体请求的 HTTP 端点路径（默认: `/process`）
- **`stream`**: 启用流式响应以进行实时通信
- **`port`**: Web 服务的容器端口
- **`replicas`**: 要部署的 Pod 副本数量
- **`image_tag`**: Docker 镜像标签标识符
- **`image_name`**: Docker 镜像的基本名称

#### 依赖项配置
- **`requirements`**: 通过 pip 安装的 Python 包
- **`extra_packages`**: 要包含在镜像中的额外本地 Python 文件
- **`base_image`**: 基础 Docker 镜像（Python 运行时）

#### 将注入到镜像中的环境变量

#### 部署设置
- **`deploy_timeout`**: 等待部署完成的最大时间（秒）
- **`health_check`**: 启用健康检查端点
- **`platform`**: 目标平台架构
- **`push_to_registry`**: 是否将构建的镜像推送到镜像仓库

## 运行部署

1. **自定义配置**：
   编辑 `deploy_to_k8s.py` 以匹配您的环境：
   - 将 `registry_url` 更新为您的容器镜像仓库
   - 如需要，修改 `k8s_namespace`
   - 根据集群容量调整资源限制
   - 设置适当的环境变量

2. **运行部署**：
   ```bash
   cd examples/deployments/k8s_deploy
   python deploy_to_k8s.py
   ```

3. **监控部署**：
   脚本将输出：
   - 部署 ID 和状态
   - 访问智能体的服务 URL
   - Kubernetes 中的资源名称
   - 验证测试命令

4. **测试已部署的服务**：
   使用提供的 curl 命令或 kubectl 命令进行测试：
   ```bash
   # 健康检查
   curl http://your-service-url/health

   # 智能体请求
   curl -X POST http://your-service-url/process \
     -H "Content-Type: application/json" \
     -d '{"input": [{"role": "user", "content": [{"type": "text", "text": "Hello!"}]}], "session_id": "123"}'
   ```

5. **查看 Kubernetes 资源**：
   ```bash
   kubectl get pods -n agentscope-runtime
   kubectl get svc -n agentscope-runtime
   kubectl logs -l app=agent-llm -n agentscope-runtime
   ```

6. **清理**：
   脚本将提示您按 Enter 键自动清理资源。

## 故障排除

### 常见问题

1. **镜像仓库认证**：确保 Docker 已登录到您的镜像仓库：
   ```bash
   docker login your-registry-url
   ```

2. **Kubernetes 权限**：验证您是否有足够的权限：
   ```bash
   kubectl auth can-i create deployments --namespace=agentscope-runtime
   ```

3. **资源限制**：如果 Pod 启动失败，检查集群是否有足够的资源：
   ```bash
   kubectl describe nodes
   kubectl get resourcequota -n agentscope-runtime
   ```

4. **镜像拉取错误**：检查镜像是否成功推送：
   ```bash
   kubectl describe pod <pod-name> -n agentscope-runtime
   ```

### 日志和调试

- 查看 Pod 日志: `kubectl logs <pod-name> -n agentscope-runtime`
- 描述 Pod 状态: `kubectl describe pod <pod-name> -n agentscope-runtime`
- 检查服务端点: `kubectl get endpoints -n agentscope-runtime`


## 文件结构

- `deploy_to_k8s.py`: 主部署脚本
- `agent_run.py`: 使用 AgentScope-Runtime 引擎的基础智能体实现
- `others/other_project.py`: 额外的包依赖项

此示例提供了将 AgentScope Runtime 智能体部署到 Kubernetes 的完整工作流程，具备生产就绪配置。
