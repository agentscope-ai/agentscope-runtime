---
jupytext:
  formats: md:myst
  text_representation:
    extension: .md
    format_name: myst
    format_version: 0.13
    jupytext_version: 1.11.5
kernelspec:
  display_name: Python 3
  language: python
  name: python3
---

# 高级部署指南

本指南演示了AgentScope Runtime中可用的四种高级部署方法，为不同场景提供生产就绪的解决方案：**本地守护进程**、**独立进程**、**Kubernetes部署**和**ModelStudio部署**。

## 部署方法概述

AgentScope Runtime提供四种不同的部署方式，每种都针对特定的使用场景：

| 部署类型 | 使用场景 | 扩展性 | 管理方式 | 资源隔离 |
|---------|---------|--------|---------|---------|
| **本地守护进程** | 开发与测试 | 单进程 | 手动 | 进程级 |
| **独立进程** | 生产服务 | 单节点 | 自动化 | 进程级 |
| **Kubernetes** | 企业与云端 | 单节点（将支持多节点） | 编排 | 容器级 |
| **ModelStudio** | 阿里云平台 | 云端管理 | 平台管理 | 容器级 |

## 前置条件

### 🔧 安装要求

安装包含所有部署依赖的AgentScope Runtime：

```bash
# 基础安装
pip install agentscope-runtime

# Kubernetes部署依赖
pip install "agentscope-runtime[deployment]"

# 沙箱工具（可选）
pip install "agentscope-runtime[sandbox]"
```

### 🔑 环境配置

配置您的API密钥和环境变量：

```bash
# LLM功能必需
export DASHSCOPE_API_KEY="your_qwen_api_key"

# 云部署可选
export DOCKER_REGISTRY="your_registry_url"
export KUBECONFIG="/path/to/your/kubeconfig"
```

### 📦 各部署类型的前置条件

#### 所有部署类型
- Python 3.10+
- 已安装AgentScope Runtime

#### Kubernetes部署
- 已安装并配置Docker
- Kubernetes集群访问权限
- 已配置kubectl
- 容器镜像仓库访问权限（用于推送镜像）

(zh-common-agent-setup)=

## 通用智能体配置

所有部署方法共享相同的智能体和端点配置。让我们首先创建基础智能体并定义端点：

```{code-cell}
# agent_app.py - 所有部署方法的共享配置
import os
import time

from agentscope.agent import ReActAgent
from agentscope.model import DashScopeChatModel
from agentscope.tool import Toolkit, view_text_file

from agentscope_runtime.engine.agents.agentscope_agent import AgentScopeAgent
from agentscope_runtime.engine.app import AgentApp
from agentscope_runtime.engine.schemas.agent_schemas import AgentRequest

# 1. 创建带工具包的智能体
toolkit = Toolkit()
toolkit.register_tool_function(view_text_file)

agent = AgentScopeAgent(
    name="Friday",
    model=DashScopeChatModel(
        "qwen-max",
        api_key=os.getenv("DASHSCOPE_API_KEY"),
    ),
    agent_config={
        "sys_prompt": "You're a helpful assistant named Friday.",
        "toolkit": toolkit,
    },
    agent_builder=ReActAgent,
)

# 2. 创建带有多个端点的 AgentApp
app = AgentApp(agent=agent)

@app.endpoint("/sync")
def sync_handler(request: AgentRequest):
    return {"status": "ok", "payload": request}

@app.endpoint("/async")
async def async_handler(request: AgentRequest):
    return {"status": "ok", "payload": request}

@app.endpoint("/stream_async")
async def stream_async_handler(request: AgentRequest):
    for i in range(5):
        yield f"async chunk {i}, with request payload {request}\n"

@app.endpoint("/stream_sync")
def stream_sync_handler(request: AgentRequest):
    for i in range(5):
        yield f"sync chunk {i}, with request payload {request}\n"

@app.task("/task", queue="celery1")
def task_handler(request: AgentRequest):
    time.sleep(30)
    return {"status": "ok", "payload": request}

@app.task("/atask")
async def atask_handler(request: AgentRequest):
    import asyncio
    await asyncio.sleep(15)
    return {"status": "ok", "payload": request}

print("✅ 智能体和端点配置成功")
```

**注意**：以上配置在下面所有部署方法中共享。每个方法只展示该方法特有的部署代码。

## 方法1：本地守护进程部署

**最适合**：开发、测试和需要手动控制的持久服务的单用户场景。

### 特性
- 主进程中的持久服务
- 手动生命周期管理
- 交互式控制和监控
- 直接资源共享

### 实现

使用 {ref}`通用智能体配置<zh-common-agent-setup>` 部分定义的智能体和端点：

```{code-cell}
# daemon_deploy.py
import asyncio
from agentscope_runtime.engine.deployers.local_deployer import LocalDeployManager
from agent_app import app  # 导入已配置的 app

# 以守护进程模式部署
async def main():
    await app.deploy(LocalDeployManager())

if __name__ == "__main__":
    asyncio.run(main())
    input("按 Enter 键停止服务器...")
```

**关键点**：
- 服务在主进程中运行（阻塞式）
- 通过 Ctrl+C 或结束脚本手动停止
- 最适合开发和测试

### 测试部署的服务

部署后，您可以使用 curl 或 Python 测试端点：

**使用 curl：**

```bash
# 测试健康检查端点
curl http://localhost:8080/health

# 调用同步端点
curl -X POST http://localhost:8080/sync \
  -H "Content-Type: application/json" \
  -d '{"input": [{"role": "user", "content": [{"type": "text", "text": "杭州天气如何？"}]}], "session_id": "123"}'

# 调用流式端点
curl -X POST http://localhost:8080/stream_sync \
  -H "Content-Type: application/json" \
  -d '{"input": [{"role": "user", "content": [{"type": "text", "text": "杭州天气如何？"}]}], "session_id": "123"}'

# 提交任务
curl -X POST http://localhost:8080/task \
  -H "Content-Type: application/json" \
  -d '{"input": [{"role": "user", "content": [{"type": "text", "text": "杭州天气如何？"}]}], "session_id": "123"}'
```

**使用 OpenAI SDK：**

```python
from openai import OpenAI

client = OpenAI(base_url="http://0.0.0.0:8080/compatible-mode/v1")

response = client.responses.create(
  model="any_name",
  input="杭州天气如何？"
)

print(response)
```

## 方法2：独立进程部署

**最适合**：需要进程隔离、自动化管理和独立生命周期的生产服务。

### 特性
- 独立进程执行
- 自动化生命周期管理
- 远程关闭功能
- 主脚本退出后服务持续运行

### 实现

使用 {ref}`通用智能体配置<zh-common-agent-setup>` 部分定义的智能体和端点：

```{code-cell}
# detached_deploy.py
import asyncio
from agentscope_runtime.engine.deployers.local_deployer import LocalDeployManager
from agentscope_runtime.engine.deployers.utils.deployment_modes import DeploymentMode
from agent_app import app  # 导入已配置的 app

async def main():
    """以独立进程模式部署应用"""
    print("🚀 以独立进程模式部署 AgentApp...")

    # 以独立模式部署
    deployment_info = await app.deploy(
        LocalDeployManager(host="127.0.0.1", port=8080),
        mode=DeploymentMode.DETACHED_PROCESS,
    )

    print(f"✅ 部署成功：{deployment_info['url']}")
    print(f"📍 部署ID：{deployment_info['deploy_id']}")
    print(f"""
🎯 服务已启动，测试命令：
curl {deployment_info['url']}/health
curl -X POST {deployment_info['url']}/admin/shutdown  # 停止服务

⚠️ 注意：服务在独立进程中运行，直到被停止。
""")
    return deployment_info

if __name__ == "__main__":
    asyncio.run(main())
```

**关键点**：
- 服务在独立的分离进程中运行
- 脚本在部署后退出，服务继续运行
- 通过 `/admin/shutdown` 端点远程关闭

### 高级独立进程配置

对于生产环境，您可以配置外部服务：

```{code-cell}
from agentscope_runtime.engine.deployers.utils.service_utils import ServicesConfig

# 生产服务配置
production_services = ServicesConfig(
    # 使用Redis实现持久化
    memory_provider="redis",
    session_history_provider="redis",
    redis_config={
        "host": "redis.production.local",
        "port": 6379,
        "db": 0,
    }
)

# 使用生产服务进行部署
deployment_info = await runner.deploy(
    deploy_manager=deploy_manager,
    endpoint_path="/process",
    stream=True,
    mode=DeploymentMode.DETACHED_PROCESS,
    services_config=production_services,  # 使用生产配置
    protocol_adapters=[a2a_protocol],
)
```


## 方法3：Kubernetes部署

**最适合**：需要扩展性、高可用性和云原生编排的企业生产环境。

### 特性
- 基于容器的部署
- 水平扩展支持
- 云原生编排
- 资源管理和限制
- 健康检查和自动恢复

### Kubernetes部署前置条件

```bash
# 确保Docker正在运行
docker --version

# 验证Kubernetes访问
kubectl cluster-info

# 检查镜像仓库访问（以阿里云为例）
docker login your-registry
```

### 实现

使用 {ref}`通用智能体配置<zh-common-agent-setup>` 部分定义的智能体和端点：

```{code-cell}
# k8s_deploy.py
import asyncio
import os
from agentscope_runtime.engine.deployers.kubernetes_deployer import (
    KubernetesDeployManager,
    RegistryConfig,
    K8sConfig,
)
from agent_app import app  # 导入已配置的 app

async def deploy_to_k8s():
    """将 AgentApp 部署到 Kubernetes"""

    # 配置镜像仓库和 K8s 连接
    deployer = KubernetesDeployManager(
        kube_config=K8sConfig(
            k8s_namespace="agentscope-runtime",
            kubeconfig_path=None,
        ),
        registry_config=RegistryConfig(
            registry_url="your-registry-url",
            namespace="agentscope-runtime",
        ),
        use_deployment=True,
    )

    # 执行部署
    result = await app.deploy(
        deployer,
        port="8080",
        replicas=1,
        image_name="agent_app",
        image_tag="v1.0",
        requirements=["agentscope", "fastapi", "uvicorn"],
        base_image="python:3.10-slim-bookworm",
        environment={
            "PYTHONPATH": "/app",
            "DASHSCOPE_API_KEY": os.environ.get("DASHSCOPE_API_KEY"),
        },
        runtime_config={
        "resources": {
            "requests": {"cpu": "200m", "memory": "512Mi"},
            "limits": {"cpu": "1000m", "memory": "2Gi"},
        },
        },
        platform="linux/amd64",
        push_to_registry=True,
    )

    print(f"✅ 部署成功：{result['url']}")
    return result, deployer

if __name__ == "__main__":
    asyncio.run(deploy_to_k8s())
```

**关键点**：
- 容器化部署，支持自动扩展
- 配置资源限制和健康检查
- 可使用 `kubectl scale deployment` 进行扩展


## 方法4：ModelStudio部署

**最适合**：阿里云用户，需要托管云部署，具有内置监控、扩展和与阿里云生态系统集成。

### 特性
- 阿里云上的托管云部署
- 与DashScope LLM服务集成
- 内置监控和分析
- 自动扩展和资源管理
- OSS集成用于制品存储
- Web控制台进行部署管理

### ModelStudio部署前置条件

```bash
# 确保设置环境变量
export DASHSCOPE_API_KEY="your-dashscope-api-key"
export ALIBABA_CLOUD_ACCESS_KEY_ID="your-access-key-id"
export ALIBABA_CLOUD_ACCESS_KEY_SECRET="your-access-key-secret"
export MODELSTUDIO_WORKSPACE_ID="your-workspace-id"

# 可选的OSS专用凭证
export OSS_ACCESS_KEY_ID="your-oss-access-key-id"
export OSS_ACCESS_KEY_SECRET="your-oss-access-key-secret"
```

### 实现

使用 {ref}`通用智能体配置<zh-common-agent-setup>` 部分定义的智能体和端点：

```{code-cell}
# modelstudio_deploy.py
import asyncio
import os
from agentscope_runtime.engine.deployers.modelstudio_deployer import (
    ModelstudioDeployManager,
    OSSConfig,
    ModelstudioConfig,
)
from agent_app import app  # 导入已配置的 app

async def deploy_to_modelstudio():
    """将 AgentApp 部署到阿里云 ModelStudio"""

    # 配置 OSS 和 ModelStudio
    deployer = ModelstudioDeployManager(
        oss_config=OSSConfig(
            access_key_id=os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_ID"),
            access_key_secret=os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_SECRET"),
        ),
        modelstudio_config=ModelstudioConfig(
            workspace_id=os.environ.get("MODELSTUDIO_WORKSPACE_ID"),
            access_key_id=os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_ID"),
            access_key_secret=os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_SECRET"),
            dashscope_api_key=os.environ.get("DASHSCOPE_API_KEY"),
        ),
    )

    # 执行部署
    result = await app.deploy(
        deployer,
        deploy_name="agent-app-example",
        telemetry_enabled=True,
        requirements=["agentscope", "fastapi", "uvicorn"],
        environment={
            "PYTHONPATH": "/app",
            "DASHSCOPE_API_KEY": os.environ.get("DASHSCOPE_API_KEY"),
        },
    )

    print(f"✅ 部署到 ModelStudio：{result['url']}")
    print(f"📦 制品：{result['artifact_url']}")
    return result

if __name__ == "__main__":
    asyncio.run(deploy_to_modelstudio())
```

**关键点**：
- 阿里云上的完全托管云部署
- 内置监控和自动扩展
- 与 DashScope LLM 服务集成


## 总结

本指南涵盖了AgentScope Runtime的四种部署方法：

### 🏃 **本地守护进程**：开发与测试
- 快速设置和直接控制
- 最适合开发和小规模使用
- 手动生命周期管理

### 🔧 **独立进程**：生产服务
- 进程隔离和自动化管理
- 适用于单节点生产部署
- 远程控制功能

### ☸️ **Kubernetes**：企业与云端
- 完整的容器编排和扩展
- 高可用性和云原生特性
- 企业级生产部署

### ☁️ **ModelStudio**：阿里云平台
- 完全托管的云部署
- 内置监控和自动扩展
- 与阿里云服务无缝集成

选择最适合您的用例、基础设施和扩展需求的部署方法。所有方法都使用相同的智能体代码，使得随着需求演变在部署类型之间迁移变得简单。

有关特定组件的更多详细信息，请参阅[管理器模块](manager.md)、[沙箱](sandbox.md)和[快速开始](quickstart.md)指南。
